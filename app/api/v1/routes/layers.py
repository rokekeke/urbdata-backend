import json
import uuid
from typing import Any

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from geoalchemy2.shape import to_shape
from shapely.geometry import mapping
from sqlalchemy.orm import Session

from app.api.v1.schemas.layer import (
    LayerAttributeMappingIn,
    LayerAttributesOut,
    LayerOut,
    QuadrasDeriveOut,
)
from app.domain.analysis.exceptions import (
    DuplicateLayerError,
    ProjectNotFoundError,
    RequiredLayerMissingError,
)
from app.domain.text_encoding import fix_geojson_feature_properties
from app.infrastructure.database.models.layer import LayerType
from app.infrastructure.database.repositories.feature_repository import FeatureRepository
from app.infrastructure.database.repositories.project_repository import ProjectRepository
from app.infrastructure.database.session import get_db
from app.infrastructure.storage.local import LocalStorage

router = APIRouter(prefix="/projects/{project_id}/layers", tags=["layers"])

# Geometries accepted per layer slot (mirrors the tolerance/precedence rules in
# docs/escopo-motor-calculo.md).
EXPECTED_GEOMETRY: dict[LayerType, set[str]] = {
    LayerType.PERIMETRO: {"Polygon", "MultiPolygon"},
    LayerType.QUADRAS: {"Polygon", "MultiPolygon"},
    LayerType.LOTES: {"Polygon", "MultiPolygon"},
    LayerType.SISTEMA_VIARIO: {"LineString", "MultiLineString"},
    LayerType.USO_SOLO: {"Polygon", "MultiPolygon"},
    LayerType.AREAS_VERDES: {"Polygon", "MultiPolygon"},
    LayerType.EQUIPAMENTOS: {"Point", "Polygon", "MultiPolygon"},
    LayerType.EDIFICACOES: {"Polygon", "MultiPolygon"},
    LayerType.DESCONEXOES_VIARIAS: {"Point", "MultiPoint"},
    # Single upload with every territorial subdivision, tagged per-feature
    # via the `macroarea` attribute (ADR 008) - the polygon footprint of
    # sistema_viario lives here too, distinct from the future LineString
    # road-network axis under LayerType.SISTEMA_VIARIO.
    LayerType.TERRITORIO: {"Polygon", "MultiPolygon"},
}


@router.post("", response_model=LayerOut, status_code=201)
def upload_layer(
    project_id: uuid.UUID,
    layer_type: LayerType = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
) -> object:
    try:
        version_id = ProjectRepository(db).current_version_id(project_id)
    except ProjectNotFoundError as exc:
        raise HTTPException(status_code=404, detail=exc.message) from exc

    raw = file.file.read()
    try:
        geojson: dict[str, Any] = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise HTTPException(
            status_code=400,
            detail={"error": "invalid_geojson", "message": "Arquivo nao e um GeoJSON valido."},
        ) from exc

    features: list[dict[str, Any]] = geojson.get("features", [])
    if not features:
        raise HTTPException(
            status_code=400,
            detail={"error": "empty_layer", "message": "O arquivo nao contem feicoes."},
        )

    # Some exporters double-encode UTF-8 (see docs/adr or Obsidian note 10).
    # This is a deterministic byte round-trip, not a domain judgment call,
    # so it is safe to correct automatically - unlike geometry, properties
    # are never silently altered otherwise.
    for feature in features:
        properties = feature.get("properties")
        if isinstance(properties, dict):
            feature["properties"] = fix_geojson_feature_properties(properties)

    geometry_types = {
        feature.get("geometry", {}).get("type")
        if isinstance(feature.get("geometry"), dict)
        else None
        for feature in features
    }
    invalid_geometry_types = geometry_types - EXPECTED_GEOMETRY[layer_type]
    if len(geometry_types) != 1 or invalid_geometry_types:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "geometry_mismatch",
                "message": (
                    f"A camada '{layer_type.value}' espera "
                    f"{sorted(EXPECTED_GEOMETRY[layer_type])}, "
                    f"mas o arquivo contem {sorted(str(value) for value in geometry_types)}."
                ),
            },
        )
    geometry_type = next(iter(geometry_types))
    if not isinstance(geometry_type, str):
        raise HTTPException(
            status_code=400,
            detail={"error": "geometry_mismatch", "message": "Geometria ausente ou invalida."},
        )

    # Preserve the original upload unmodified before any parsing-derived data is
    # persisted (README invariant: never silently lose the source file).
    file.file.seek(0)
    LocalStorage().save(
        file.file, filename=file.filename or "layer.geojson", subpath=str(project_id)
    )

    layer = FeatureRepository(db).create_layer_with_features(
        project_version_id=version_id,
        layer_type=layer_type,
        source_filename=file.filename,
        geometry_type=geometry_type,
        raw_features=features,
    )
    return layer


@router.get("", response_model=list[LayerOut])
def list_layers(project_id: uuid.UUID, db: Session = Depends(get_db)) -> object:
    try:
        version_id = ProjectRepository(db).current_version_id(project_id)
    except ProjectNotFoundError as exc:
        raise HTTPException(status_code=404, detail=exc.message) from exc
    return FeatureRepository(db).list_layers(version_id)


@router.get("/{layer_id}/attributes", response_model=LayerAttributesOut)
def get_layer_attributes(
    project_id: uuid.UUID, layer_id: uuid.UUID, db: Session = Depends(get_db)
) -> LayerAttributesOut:
    sample = FeatureRepository(db).list_features(layer_id)[:20]
    if not sample:
        raise HTTPException(status_code=404, detail="Camada sem feicoes.")

    fields: set[str] = set()
    values: dict[str, list[str]] = {}
    for feature in sample:
        for key, value in (feature.source_properties or {}).items():
            fields.add(key)
            values.setdefault(key, [])
            if str(value) not in values[key] and len(values[key]) < 5:
                values[key].append(str(value))

    return LayerAttributesOut(
        layer_id=layer_id,
        source_fields=sorted(fields),
        sample_values=values,
        suggested_mapping={},
    )


@router.patch("/{layer_id}/attributes")
def map_layer_attributes(
    project_id: uuid.UUID,
    layer_id: uuid.UUID,
    payload: LayerAttributeMappingIn,
    db: Session = Depends(get_db),
) -> dict[str, object]:
    updated = FeatureRepository(db).apply_attribute_mapping(layer_id, payload.mappings)
    return {"layer_id": str(layer_id), "status": "mapped", "features_updated": updated}


@router.post("/quadras/derive", response_model=QuadrasDeriveOut)
def derive_quadras_layer(project_id: uuid.UUID, db: Session = Depends(get_db)) -> object:
    """Dissolve Lote features sharing a `quadra_id` into a QUADRAS layer
    (ADR 009), toggleable/hideable like any other layer via the existing
    GET /layers and GET /layers/{id}/geojson routes - no new read endpoints
    needed. Replaces any previously derived QUADRAS layer for this version.
    """
    try:
        version_id = ProjectRepository(db).current_version_id(project_id)
    except ProjectNotFoundError as exc:
        raise HTTPException(status_code=404, detail=exc.message) from exc

    try:
        result = FeatureRepository(db).derive_quadras_layer(version_id)
    except RequiredLayerMissingError as exc:
        raise HTTPException(
            status_code=422, detail={"error": exc.code, "message": exc.message}
        ) from exc
    except DuplicateLayerError as exc:
        raise HTTPException(
            status_code=422, detail={"error": exc.code, "message": exc.message}
        ) from exc

    return result


@router.get("/{layer_id}/geojson")
def get_layer_geojson(
    project_id: uuid.UUID, layer_id: uuid.UUID, db: Session = Depends(get_db)
) -> dict[str, Any]:
    features = FeatureRepository(db).list_features(layer_id)
    return {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "id": str(feature.id),
                "geometry": mapping(to_shape(feature.geom)),
                "properties": {
                    **(feature.source_properties or {}),
                    **(feature.mapped_properties or {}),
                },
            }
            for feature in features
        ],
    }
