import json
import uuid
from typing import Any

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from geoalchemy2.shape import to_shape
from shapely.geometry import mapping
from sqlalchemy.orm import Session

from app.api.v1.errors import error_detail
from app.api.v1.schemas.error import BAD_REQUEST, NOT_FOUND, TOO_LARGE, UNPROCESSABLE
from app.api.v1.schemas.layer import (
    AttributeMappingWarningOut,
    GeoJSONFeatureCollectionOut,
    GeoJSONFeatureOut,
    LayerAttributeMappingIn,
    LayerAttributeMappingOut,
    LayerAttributesOut,
    LayerOut,
    QuadrasDeriveOut,
    RepresentationFieldOut,
)
from app.domain.analysis.exceptions import (
    DuplicateLayerError,
    ProjectNotFoundError,
    RequiredLayerMissingError,
)
from app.domain.attribute_suggestions import suggest_attribute_mapping
from app.domain.cartography.representation_options import (
    compatible_indicator_codes,
    recommend_mode,
)
from app.domain.csv_import import CSVParseError, parse_csv
from app.domain.layer_join import (
    AttributeJoinError,
    JoinResult,
    join_geometry_and_attributes,
    resolve_geometry_join_keys,
)
from app.domain.text_encoding import fix_geojson_feature_properties
from app.infrastructure.database.models.layer import ImportProfile, LayerType
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


@router.post(
    "",
    response_model=LayerOut,
    status_code=201,
    responses={**NOT_FOUND, **BAD_REQUEST, **TOO_LARGE},
)
def upload_layer(
    project_id: uuid.UUID,
    layer_type: LayerType = Form(...),
    file: UploadFile = File(...),
    import_profile: ImportProfile = Form(ImportProfile.COMBINED),
    attributes_file: UploadFile | None = File(None),
    attributes_join_key: str | None = Form(None),
    geometry_join_key: str | None = Form(None),
    db: Session = Depends(get_db),
) -> object:
    try:
        version_id = ProjectRepository(db).current_version_id(project_id)
    except ProjectNotFoundError as exc:
        raise HTTPException(
            status_code=404, detail=error_detail(exc.code, exc.message, exc.context)
        ) from exc

    # Nota 53/54 checkpoint: attributes_file/attributes_join_key are only
    # meaningful (and only required) when the CSV is separate from the
    # geometry file - geometry_join_key stays optional either way (null
    # means feature.id, not "unknown"). Validated before any file parsing.
    if import_profile is ImportProfile.COMBINED and attributes_file is not None:
        raise HTTPException(
            status_code=400,
            detail=error_detail(
                "invalid_import_profile",
                "attributes_file so e aceito quando import_profile='split'.",
            ),
        )
    if import_profile is ImportProfile.SPLIT and (
        attributes_file is None or not attributes_join_key
    ):
        raise HTTPException(
            status_code=400,
            detail=error_detail(
                "invalid_import_profile",
                "import_profile='split' exige attributes_file e attributes_join_key.",
            ),
        )

    raw = file.file.read()
    try:
        geojson: dict[str, Any] = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise HTTPException(
            status_code=400,
            detail=error_detail("invalid_geojson", "Arquivo nao e um GeoJSON valido."),
        ) from exc

    features: list[dict[str, Any]] = geojson.get("features", [])
    if not features:
        raise HTTPException(
            status_code=400,
            detail=error_detail("empty_layer", "O arquivo nao contem feicoes."),
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
            detail=error_detail(
                "geometry_mismatch",
                (
                    f"A camada '{layer_type.value}' espera "
                    f"{sorted(EXPECTED_GEOMETRY[layer_type])}, "
                    f"mas o arquivo contem {sorted(str(value) for value in geometry_types)}."
                ),
                {
                    "layer_type": layer_type.value,
                    "expected": sorted(EXPECTED_GEOMETRY[layer_type]),
                    "received": sorted(str(value) for value in geometry_types),
                },
            ),
        )
    geometry_type = next(iter(geometry_types))
    if not isinstance(geometry_type, str):
        raise HTTPException(
            status_code=400,
            detail=error_detail("geometry_mismatch", "Geometria ausente ou invalida."),
        )

    # Split profile: geometry and attributes arrive as two files, joined by
    # an explicit key (nota 53/54) - resolved from the already mojibake-fixed
    # properties above, since geometry_join_key names one of those fields.
    join_result: JoinResult | None = None
    if import_profile is ImportProfile.SPLIT:
        if attributes_file is None or not attributes_join_key:
            raise HTTPException(
                status_code=400,
                detail=error_detail(
                    "invalid_import_profile",
                    "import_profile='split' exige attributes_file e attributes_join_key.",
                ),
            )
        try:
            attribute_rows = parse_csv(attributes_file.file.read())
        except CSVParseError as exc:
            raise HTTPException(
                status_code=400, detail=error_detail(exc.code, exc.message, exc.context)
            ) from exc

        geometry_keys = resolve_geometry_join_keys(features, geometry_join_key)
        try:
            join_result = join_geometry_and_attributes(
                geometry_keys, attribute_rows, attributes_join_key
            )
        except AttributeJoinError as exc:
            raise HTTPException(
                status_code=400, detail=error_detail(exc.code, exc.message, exc.context)
            ) from exc

        # CSV attributes are the authoritative source in the split profile,
        # so they win on a key collision (e.g. the join key itself, which by
        # definition holds the same value on both sides already).
        for pair in join_result.matched:
            existing_properties = features[pair.geometry_index].get("properties")
            if not isinstance(existing_properties, dict):
                existing_properties = {}
            features[pair.geometry_index]["properties"] = {
                **existing_properties,
                **pair.attribute_row,
            }

    # Preserve the original upload(s) unmodified before any parsing-derived data
    # is persisted (README invariant: never silently lose the source file) -
    # both files in the split profile (nota 53: "preservar os dois arquivos
    # originais sem alteracao"), not just the geometry.
    file.file.seek(0)
    LocalStorage().save(
        file.file, filename=file.filename or "layer.geojson", subpath=str(project_id)
    )
    if attributes_file is not None:
        attributes_file.file.seek(0)
        LocalStorage().save(
            attributes_file.file,
            filename=attributes_file.filename or "attributes.csv",
            subpath=str(project_id),
        )

    layer = FeatureRepository(db).create_layer_with_features(
        project_version_id=version_id,
        layer_type=layer_type,
        source_filename=file.filename,
        geometry_type=geometry_type,
        raw_features=features,
        import_profile=import_profile,
        attributes_filename=attributes_file.filename if attributes_file else None,
        attributes_join_key=attributes_join_key,
        geometry_join_key=geometry_join_key,
        join_summary=join_result.summary.to_dict() if join_result is not None else None,
    )
    return layer


@router.get("", response_model=list[LayerOut], responses={**NOT_FOUND})
def list_layers(project_id: uuid.UUID, db: Session = Depends(get_db)) -> object:
    try:
        version_id = ProjectRepository(db).current_version_id(project_id)
    except ProjectNotFoundError as exc:
        raise HTTPException(
            status_code=404, detail=error_detail(exc.code, exc.message, exc.context)
        ) from exc
    return FeatureRepository(db).list_layers(version_id)


@router.get(
    "/{layer_id}/attributes", response_model=LayerAttributesOut, responses={**NOT_FOUND}
)
def get_layer_attributes(
    project_id: uuid.UUID, layer_id: uuid.UUID, db: Session = Depends(get_db)
) -> LayerAttributesOut:
    repository = FeatureRepository(db)
    layer = repository.get_layer(layer_id)
    sample = repository.list_features(layer_id)[:20]
    if layer is None or not sample:
        raise HTTPException(
            status_code=404,
            detail=error_detail(
                "layer_empty", "Camada sem feicoes.", {"layer_id": str(layer_id)}
            ),
        )

    fields: set[str] = set()
    values: dict[str, list[str]] = {}
    for feature in sample:
        for key, value in (feature.source_properties or {}).items():
            fields.add(key)
            values.setdefault(key, [])
            if str(value) not in values[key] and len(values[key]) < 5:
                values[key].append(str(value))

    # DOC-BE-004: aggregated in SQL, never scanning the layer in Python.
    field_stats = repository.aggregate_representation_stats(layer_id)
    representation_fields = []
    for stats in field_stats:
        recommendation = recommend_mode(stats)
        representation_fields.append(
            RepresentationFieldOut(
                field=stats.field,
                origin=stats.origin,
                detected_type=recommendation.detected_type,
                present_count=stats.present_count,
                empty_count=stats.empty_count,
                cardinality=stats.cardinality,
                distinct_values=(
                    list(stats.distinct_values) if stats.distinct_values is not None else None
                ),
                min_value=stats.min_value,
                max_value=stats.max_value,
                recommended_mode=recommendation.recommended_mode,
                unsuitable_reason=recommendation.unsuitable_reason,
            )
        )

    return LayerAttributesOut(
        layer_id=layer_id,
        source_fields=sorted(fields),
        sample_values=values,
        suggested_mapping=suggest_attribute_mapping(fields),
        feature_count=layer.feature_count,
        fields=representation_fields,
        compatible_indicators=list(compatible_indicator_codes(layer.layer_type.value)),
    )


@router.patch("/{layer_id}/attributes", response_model=LayerAttributeMappingOut)
def map_layer_attributes(
    project_id: uuid.UUID,
    layer_id: uuid.UUID,
    payload: LayerAttributeMappingIn,
    db: Session = Depends(get_db),
) -> LayerAttributeMappingOut:
    result = FeatureRepository(db).apply_attribute_mapping(layer_id, payload.mappings)
    return LayerAttributeMappingOut(
        layer_id=layer_id,
        status="mapped",
        features_updated=result.features_updated,
        warnings=[
            AttributeMappingWarningOut(feature_id=warning.feature_id, message=warning.message)
            for warning in result.warnings
        ],
    )


@router.post(
    "/quadras/derive",
    response_model=QuadrasDeriveOut,
    responses={**NOT_FOUND, **UNPROCESSABLE},
)
def derive_quadras_layer(project_id: uuid.UUID, db: Session = Depends(get_db)) -> object:
    """Dissolve Lote features sharing a `quadra_id` into a QUADRAS layer
    (ADR 009), toggleable/hideable like any other layer via the existing
    GET /layers and GET /layers/{id}/geojson routes - no new read endpoints
    needed. Replaces any previously derived QUADRAS layer for this version.
    """
    try:
        version_id = ProjectRepository(db).current_version_id(project_id)
    except ProjectNotFoundError as exc:
        raise HTTPException(
            status_code=404, detail=error_detail(exc.code, exc.message, exc.context)
        ) from exc

    try:
        result = FeatureRepository(db).derive_quadras_layer(version_id)
    except RequiredLayerMissingError as exc:
        raise HTTPException(
            status_code=422, detail=error_detail(exc.code, exc.message, exc.context)
        ) from exc
    except DuplicateLayerError as exc:
        raise HTTPException(
            status_code=422, detail=error_detail(exc.code, exc.message, exc.context)
        ) from exc

    return result


@router.delete("/{layer_id}", status_code=204, responses={**NOT_FOUND})
def delete_layer(
    project_id: uuid.UUID, layer_id: uuid.UUID, db: Session = Depends(get_db)
) -> None:
    """Hard delete (Frente 3, nota 52): remove a camada e suas feicoes.
    Feicoes de outras camadas que apontavam para estas (quadra/lote) sao
    desvinculadas, nunca removidas em cascata; resultados ja persistidos e
    documentos cartograficos ficam intactos - referencias orfas viram
    `integrity_warnings` na leitura (ADR 014, Decisao 8)."""
    repository = FeatureRepository(db)
    layer = repository.get_layer_for_project(project_id, layer_id)
    if layer is None:
        raise HTTPException(
            status_code=404,
            detail=error_detail(
                "layer_not_found",
                "Camada nao encontrada neste projeto.",
                {"layer_id": str(layer_id)},
            ),
        )
    repository.delete_layer(layer)


@router.get("/{layer_id}/geojson", response_model=GeoJSONFeatureCollectionOut)
def get_layer_geojson(
    project_id: uuid.UUID, layer_id: uuid.UUID, db: Session = Depends(get_db)
) -> GeoJSONFeatureCollectionOut:
    """`feature.id` is the persisted feature UUID - the join key for
    per-feature indicator values (`feature_key: feature_id` in the
    catalog, ADR 014)."""
    features = FeatureRepository(db).list_features(layer_id)
    return GeoJSONFeatureCollectionOut(
        features=[
            GeoJSONFeatureOut(
                id=str(feature.id),
                geometry=dict(mapping(to_shape(feature.geom))),
                properties={
                    **(feature.source_properties or {}),
                    **(feature.mapped_properties or {}),
                },
            )
            for feature in features
        ]
    )
