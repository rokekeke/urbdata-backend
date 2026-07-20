"""Bulk PostGIS layer and feature loading adapter."""

import uuid
from collections.abc import Callable
from decimal import Decimal, InvalidOperation
from typing import Any

import geopandas as gpd
from geoalchemy2 import Geography
from geoalchemy2.shape import from_shape, to_shape
from shapely.geometry import shape as shapely_shape
from sqlalchemy import cast, func, text
from sqlalchemy.orm import Session, aliased

from app.config.macroarea_mapping import Macroarea, resolve_macroarea
from app.config.road_hierarchy_mapping import resolve_road_status
from app.domain.analysis.exceptions import RequiredLayerMissingError
from app.domain.cartography.representation_options import FieldOrigin, FieldStats
from app.domain.geospatial.geometry import dissolve_by_group
from app.domain.geospatial.layers import (
    DerivedQuadrasLayerResult,
    LoadedFeatureLayer,
    resolve_single_layer_id,
)
from app.domain.geospatial.spatial_relations import SpatialRelation
from app.domain.text_encoding import normalize_key
from app.infrastructure.database.models.feature import Feature, RelationMethod
from app.infrastructure.database.models.layer import (
    LayerAttributeMapping,
    LayerStatus,
    LayerType,
    ProjectLayer,
)
from app.infrastructure.database.models.validation import ValidationIssue
from app.infrastructure.database.models.version import ProjectVersion

_TRUE_TOKENS = {"1", "true", "sim", "yes"}
_FALSE_TOKENS = {"0", "false", "nao", "no"}


def _coerce_bool(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    if isinstance(value, int | float):
        return bool(value)
    if isinstance(value, str):
        normalized = normalize_key(value)
        if normalized in _TRUE_TOKENS:
            return True
        if normalized in _FALSE_TOKENS:
            return False
    return None


def _coerce_decimal(value: Any) -> Decimal | None:
    if value is None:
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None


def _coerce_nonnegative_decimal(value: Any) -> Decimal | None:
    parsed = _coerce_decimal(value)
    if parsed is None or parsed < 0:
        return None
    return parsed


def _coerce_grouping_key(value: Any) -> str | None:
    """Normalize a raw attribute value into a grouping key (`quadra_id`):
    `None`/empty stays `None`, everything else becomes a stripped string."""
    if value is None:
        return None
    text = str(value).strip()
    return text or None

# Topological relations (intersects/contains/within) compare geometries as
# stored (SRID 4326); they don't depend on projection. DWITHIN is metric, so
# both sides are cast to `geography` to get a meter-based distance without
# picking a metric CRS per request (ADR 007).
_SPATIAL_PREDICATES: dict[SpatialRelation, Callable[[Any, Any, float | None], Any]] = {
    SpatialRelation.INTERSECTS: lambda a, b, _distance: func.ST_Intersects(a, b),
    SpatialRelation.CONTAINS: lambda a, b, _distance: func.ST_Contains(a, b),
    SpatialRelation.WITHIN: lambda a, b, _distance: func.ST_Within(a, b),
    SpatialRelation.DWITHIN: lambda a, b, distance: func.ST_DWithin(
        cast(a, Geography), cast(b, Geography), distance
    ),
}


class FeatureRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def create_layer_with_features(
        self,
        *,
        project_version_id: uuid.UUID,
        layer_type: LayerType,
        source_filename: str | None,
        geometry_type: str,
        raw_features: list[dict[str, Any]],
    ) -> ProjectLayer:
        layer = ProjectLayer(
            project_version_id=project_version_id,
            layer_type=layer_type,
            source_filename=source_filename,
            geometry_type=geometry_type,
            feature_count=len(raw_features),
            status=LayerStatus.UPLOADED,
        )
        self._session.add(layer)
        self._session.flush()

        for raw_feature in raw_features:
            geom = shapely_shape(raw_feature["geometry"])
            source_id = raw_feature.get("id")
            self._session.add(
                Feature(
                    layer_id=layer.id,
                    project_version_id=project_version_id,
                    external_id=str(source_id) if source_id is not None else None,
                    geom=from_shape(geom, srid=4326),
                    source_properties=raw_feature.get("properties") or {},
                    mapped_properties={},
                )
            )

        self._session.commit()
        self._session.refresh(layer)
        return layer

    def list_layers(self, project_version_id: uuid.UUID) -> list[ProjectLayer]:
        return list(
            self._session.query(ProjectLayer)
            .filter(ProjectLayer.project_version_id == project_version_id)
            .all()
        )

    def get_layer(self, layer_id: uuid.UUID) -> ProjectLayer | None:
        return self._session.get(ProjectLayer, layer_id)

    def get_layer_for_project(
        self, project_id: uuid.UUID, layer_id: uuid.UUID
    ) -> ProjectLayer | None:
        """`None` when the layer doesn't exist or belongs to another
        project - same cross-tenant-blind pattern as
        `MapDocumentRepository.get_for_project`."""
        return (
            self._session.query(ProjectLayer)
            .join(ProjectVersion, ProjectLayer.project_version_id == ProjectVersion.id)
            .filter(ProjectLayer.id == layer_id, ProjectVersion.project_id == project_id)
            .first()
        )

    def delete_layer(self, layer: ProjectLayer) -> None:
        """Hard delete of a layer and its features (Frente 3, nota 52).

        Same unlink discipline `derive_quadras_layer` already applies when
        replacing a derived QUADRAS layer, generalized: features in OTHER
        layers pointing at this layer's features via
        `parent_quadra_feature_id`/`parent_lote_feature_id` are unlinked
        (never cascade-deleted - removing quadras must not remove lots),
        and `validation_issues` rows keep their run history with the
        layer/feature reference nulled. Already-persisted indicator
        results and MapDocument configs are untouched by design:
        `indicator_results.source_layers` stores names, not FKs, and a
        stale `layer_id` in a document surfaces as an `integrity_warnings`
        diagnostic on read (ADR 014, Decisao 8) instead of breaking.
        """
        feature_ids = self._session.query(Feature.id).filter(Feature.layer_id == layer.id)
        self._session.query(Feature).filter(
            Feature.parent_quadra_feature_id.in_(feature_ids)
        ).update(
            {"parent_quadra_feature_id": None, "relation_method": RelationMethod.UNRESOLVED},
            synchronize_session=False,
        )
        self._session.query(Feature).filter(
            Feature.parent_lote_feature_id.in_(feature_ids)
        ).update({"parent_lote_feature_id": None}, synchronize_session=False)
        self._session.query(ValidationIssue).filter(
            ValidationIssue.feature_id.in_(feature_ids)
        ).update({"feature_id": None}, synchronize_session=False)
        self._session.query(ValidationIssue).filter(
            ValidationIssue.layer_id == layer.id
        ).update({"layer_id": None}, synchronize_session=False)
        self._session.query(LayerAttributeMapping).filter(
            LayerAttributeMapping.layer_id == layer.id
        ).delete(synchronize_session=False)
        self._session.query(Feature).filter(Feature.layer_id == layer.id).delete(
            synchronize_session=False
        )
        self._session.delete(layer)
        self._session.commit()

    def list_features(self, layer_id: uuid.UUID) -> list[Feature]:
        return list(self._session.query(Feature).filter(Feature.layer_id == layer_id).all())

    # Representation metadata (DOC-BE-004, ADR 014): everything aggregated
    # in SQL - the layer is never scanned in Python. 33 = block limit (32)
    # + 1, so a client can detect categorical overflow from the list itself.
    _DISTINCT_LIMIT = 33
    _NUMERIC_REGEX = r"^-?[0-9]+(\.[0-9]+)?$"

    _SOURCE_STATS_SQL = text(
        """
        SELECT kv.key AS field,
               count(*) AS present_count,
               count(*) FILTER (WHERE kv.value IS NULL OR btrim(kv.value) = '')
                   AS empty_count,
               count(DISTINCT kv.value)
                   FILTER (WHERE kv.value IS NOT NULL AND btrim(kv.value) <> '')
                   AS cardinality,
               count(*) FILTER (WHERE kv.value ~ :numeric_regex) AS numeric_count,
               min(kv.value::numeric) FILTER (WHERE kv.value ~ :numeric_regex)
                   AS min_value,
               max(kv.value::numeric) FILTER (WHERE kv.value ~ :numeric_regex)
                   AS max_value
        FROM features f
        CROSS JOIN LATERAL jsonb_each_text(f.source_properties) AS kv(key, value)
        WHERE f.layer_id = :layer_id
        GROUP BY kv.key
        ORDER BY kv.key
        """
    )

    _SOURCE_DISTINCT_SQL = text(
        """
        SELECT field, value
        FROM (
            SELECT kv.key AS field, kv.value AS value,
                   row_number() OVER (PARTITION BY kv.key ORDER BY kv.value)
                       AS position
            FROM features f
            CROSS JOIN LATERAL jsonb_each_text(f.source_properties) AS kv(key, value)
            WHERE f.layer_id = :layer_id
              AND kv.key = ANY(:fields)
              AND kv.value IS NOT NULL AND btrim(kv.value) <> ''
            GROUP BY kv.key, kv.value
        ) ranked
        WHERE position <= :distinct_limit
        ORDER BY field, value
        """
    )

    def aggregate_representation_stats(self, layer_id: uuid.UUID) -> list[FieldStats]:
        """Per-field aggregates for the representation editor (DOC-BE-004)."""
        source_rows = self._session.execute(
            self._SOURCE_STATS_SQL,
            {"layer_id": str(layer_id), "numeric_regex": self._NUMERIC_REGEX},
        ).all()

        low_cardinality = [
            row.field for row in source_rows if 0 < row.cardinality <= self._DISTINCT_LIMIT
        ]
        distinct_by_field: dict[str, list[str]] = {}
        if low_cardinality:
            for field, value in self._session.execute(
                self._SOURCE_DISTINCT_SQL,
                {
                    "layer_id": str(layer_id),
                    "fields": low_cardinality,
                    "distinct_limit": self._DISTINCT_LIMIT,
                },
            ):
                distinct_by_field.setdefault(field, []).append(value)

        stats = [
            FieldStats(
                field=row.field,
                origin=FieldOrigin.SOURCE,
                present_count=row.present_count,
                empty_count=row.empty_count,
                cardinality=row.cardinality,
                numeric_count=row.numeric_count,
                min_value=float(row.min_value) if row.min_value is not None else None,
                max_value=float(row.max_value) if row.max_value is not None else None,
                distinct_values=(
                    tuple(distinct_by_field[row.field])
                    if row.field in distinct_by_field
                    else None
                ),
            )
            for row in source_rows
        ]
        stats.extend(self._mapped_column_stats(layer_id))
        return stats

    def _mapped_column_stats(self, layer_id: uuid.UUID) -> list[FieldStats]:
        """Aggregates for the typed internal columns fed by attribute
        mapping. Only columns with at least one value are reported."""
        total = (
            self._session.query(func.count(Feature.id))
            .filter(Feature.layer_id == layer_id)
            .scalar()
            or 0
        )
        stats: list[FieldStats] = []
        if total == 0:
            return stats

        text_columns = {
            "macroarea": Feature.macroarea,
            "land_use": Feature.land_use,
            "quadra_id": Feature.quadra_id,
            "road_status": Feature.road_status,
        }
        for name, column in text_columns.items():
            filled, cardinality = (
                self._session.query(func.count(column), func.count(func.distinct(column)))
                .filter(Feature.layer_id == layer_id)
                .one()
            )
            if not filled:
                continue
            distinct_values: tuple[str, ...] | None = None
            if cardinality <= self._DISTINCT_LIMIT:
                distinct_values = tuple(
                    value
                    for (value,) in self._session.query(func.distinct(column))
                    .filter(Feature.layer_id == layer_id, column.isnot(None))
                    .order_by(column)
                    .limit(self._DISTINCT_LIMIT)
                )
            stats.append(
                FieldStats(
                    field=name,
                    origin=FieldOrigin.MAPPED,
                    present_count=total,
                    empty_count=total - filled,
                    cardinality=cardinality,
                    numeric_count=0,
                    min_value=None,
                    max_value=None,
                    distinct_values=distinct_values,
                )
            )

        numeric_columns = {
            "ca_max": Feature.ca_max,
            "reference_area_m2": Feature.reference_area_m2,
        }
        for name, numeric_column in numeric_columns.items():
            filled, cardinality, min_value, max_value = (
                self._session.query(
                    func.count(numeric_column),
                    func.count(func.distinct(numeric_column)),
                    func.min(numeric_column),
                    func.max(numeric_column),
                )
                .filter(Feature.layer_id == layer_id)
                .one()
            )
            if not filled:
                continue
            stats.append(
                FieldStats(
                    field=name,
                    origin=FieldOrigin.MAPPED,
                    present_count=total,
                    empty_count=total - filled,
                    cardinality=cardinality,
                    numeric_count=filled,
                    min_value=float(min_value) if min_value is not None else None,
                    max_value=float(max_value) if max_value is not None else None,
                    distinct_values=None,
                )
            )

        filled_bool = (
            self._session.query(func.count(Feature.parcelavel))
            .filter(Feature.layer_id == layer_id)
            .scalar()
            or 0
        )
        if filled_bool:
            cardinality_bool = (
                self._session.query(func.count(func.distinct(Feature.parcelavel)))
                .filter(Feature.layer_id == layer_id)
                .scalar()
                or 0
            )
            stats.append(
                FieldStats(
                    field="parcelavel",
                    origin=FieldOrigin.MAPPED,
                    present_count=total,
                    empty_count=total - filled_bool,
                    cardinality=cardinality_bool,
                    numeric_count=0,
                    min_value=None,
                    max_value=None,
                    distinct_values=None,
                    boolean=True,
                )
            )
        return stats

    def apply_attribute_mapping(self, layer_id: uuid.UUID, mappings: dict[str, str | None]) -> int:
        features = self.list_features(layer_id)
        for feature in features:
            mapped: dict[str, Any] = {}
            for internal_field, source_field in mappings.items():
                if source_field:
                    mapped[internal_field] = (feature.source_properties or {}).get(source_field)
            feature.mapped_properties = mapped
            if "land_use" in mapped:
                feature.land_use = mapped["land_use"]
            if "macroarea" in mapped:
                resolved = resolve_macroarea(mapped["macroarea"])
                feature.macroarea = resolved.value if resolved is not None else None
            if "parcelavel" in mapped:
                feature.parcelavel = _coerce_bool(mapped["parcelavel"])
            if "reference_area_m2" in mapped:
                feature.reference_area_m2 = _coerce_decimal(mapped["reference_area_m2"])
            if "quadra_id" in mapped:
                feature.quadra_id = _coerce_grouping_key(mapped["quadra_id"])
            if "road_status" in mapped:
                resolved_status = resolve_road_status(mapped["road_status"])
                feature.road_status = resolved_status.value if resolved_status is not None else None
            if "ca_max" in mapped:
                feature.ca_max = _coerce_nonnegative_decimal(mapped["ca_max"])

        layer = self.get_layer(layer_id)
        if layer is not None:
            layer.status = LayerStatus.MAPPED

        self._session.commit()
        return len(features)

    def load_layer_by_type(
        self, project_version_id: uuid.UUID, layer_type: str
    ) -> LoadedFeatureLayer | None:
        """Resolve and bulk-load the layer of *layer_type* for one version.

        Returns `None` when the version has no such layer, so callers can
        raise a domain-level `RequiredLayerMissingError` instead of a bare
        `AttributeError`. Raises `DuplicateLayerError` (BT-011) when more
        than one layer of the same type exists - it is never silently
        resolved by picking one.
        """
        candidates = (
            self._session.query(ProjectLayer)
            .filter(
                ProjectLayer.project_version_id == project_version_id,
                ProjectLayer.layer_type == LayerType(layer_type),
            )
            .all()
        )
        resolved_id = resolve_single_layer_id(
            [candidate.id for candidate in candidates], layer_type=layer_type
        )
        if resolved_id is None:
            return None
        layer = next(candidate for candidate in candidates if candidate.id == resolved_id)
        return self.load_layer(layer.id, layer_type=layer.layer_type.value)

    def derive_quadras_layer(self, project_version_id: uuid.UUID) -> DerivedQuadrasLayerResult:
        """Dissolve Lote features sharing a `quadra_id` into a persisted
        QUADRAS layer (ADR 009), replacing any existing one for this version
        so the result never collides with BT-011's duplicate-layer check.

        Dissolves on the territorio layer's native SRID 4326 geometry -
        `Feature.geom` is always stored as 4326, so there is no reason to
        round-trip through a metric CRS just to persist straight back to it.
        """
        territorio = self.load_layer_by_type(project_version_id, "territorio")
        if territorio is None:
            raise RequiredLayerMissingError(
                "A territorio layer is required to derive quadras.",
                context={"layer_type": "territorio"},
            )

        lots = territorio.gdf[territorio.gdf["macroarea"] == Macroarea.LOTE.value]
        grouped = dissolve_by_group(lots, group_column="quadra_id")

        existing_layers = (
            self._session.query(ProjectLayer)
            .filter(
                ProjectLayer.project_version_id == project_version_id,
                ProjectLayer.layer_type == LayerType.QUADRAS,
            )
            .all()
        )
        for existing in existing_layers:
            old_quadra_feature_ids = self._session.query(Feature.id).filter(
                Feature.layer_id == existing.id
            )
            self._session.query(Feature).filter(
                Feature.parent_quadra_feature_id.in_(old_quadra_feature_ids)
            ).update(
                {
                    "parent_quadra_feature_id": None,
                    "relation_method": RelationMethod.UNRESOLVED,
                },
                synchronize_session=False,
            )
            self._session.query(Feature).filter(Feature.layer_id == existing.id).delete(
                synchronize_session=False
            )
            self._session.delete(existing)
        self._session.flush()

        layer = ProjectLayer(
            project_version_id=project_version_id,
            layer_type=LayerType.QUADRAS,
            source_filename=None,
            geometry_type="Polygon",
            feature_count=len(grouped),
            status=LayerStatus.VALIDATED,
        )
        self._session.add(layer)
        self._session.flush()

        lot_count = 0
        for quadra_id, (geometry, contributing_lot_ids, _skipped) in grouped.items():
            quadra_feature = Feature(
                layer_id=layer.id,
                project_version_id=project_version_id,
                external_id=quadra_id,
                geom=from_shape(geometry, srid=4326),
                source_properties={},
                mapped_properties={
                    "quadra_id": quadra_id,
                    "quantidade_lotes": len(contributing_lot_ids),
                },
            )
            self._session.add(quadra_feature)
            self._session.flush()

            self._session.query(Feature).filter(Feature.id.in_(contributing_lot_ids)).update(
                {
                    "parent_quadra_feature_id": quadra_feature.id,
                    "relation_method": RelationMethod.ATTRIBUTE,
                },
                synchronize_session=False,
            )
            lot_count += len(contributing_lot_ids)

        self._session.commit()
        self._session.refresh(layer)
        return DerivedQuadrasLayerResult(
            layer_id=layer.id, quadra_count=len(grouped), lot_count=lot_count
        )

    def select_related_feature_ids(
        self,
        *,
        project_version_id: uuid.UUID,
        target_layer_type: str,
        relation: SpatialRelation | None,
        source_feature_ids: tuple[uuid.UUID, ...] | None,
        distance_m: float | None,
        attribute_filters: dict[str, str] | None,
    ) -> tuple[uuid.UUID, ...]:
        """Answer "which features of *target_layer_type* satisfy *relation*
        against *source_feature_ids* (and/or the attribute filters)?" using
        PostGIS directly, over the spatial index on `features.geom`, for the
        sub-second interactive selection endpoint (ADR 007).

        A project with no layer of *target_layer_type* yet is a valid "no
        matches" state, not an error: this returns an empty tuple rather
        than raising. More than one layer of *target_layer_type* still
        raises `DuplicateLayerError` (BT-011) - same rule as `load_layer_by_type`.
        """
        target_candidates = (
            self._session.query(ProjectLayer)
            .filter(
                ProjectLayer.project_version_id == project_version_id,
                ProjectLayer.layer_type == LayerType(target_layer_type),
            )
            .all()
        )
        target_layer_id = resolve_single_layer_id(
            [candidate.id for candidate in target_candidates], layer_type=target_layer_type
        )
        if target_layer_id is None:
            return ()

        query = self._session.query(Feature.id).filter(Feature.layer_id == target_layer_id)

        if relation is not None and source_feature_ids:
            source = aliased(Feature)
            predicate = _SPATIAL_PREDICATES[relation](Feature.geom, source.geom, distance_m)
            query = query.filter(
                self._session.query(source.id)
                .filter(
                    source.project_version_id == project_version_id,
                    source.id.in_(source_feature_ids),
                    predicate,
                )
                .exists()
            )

        for key, value in (attribute_filters or {}).items():
            if key == "land_use":
                query = query.filter(Feature.land_use == value)
            else:
                query = query.filter(Feature.mapped_properties[key].astext == value)

        return tuple(row[0] for row in query.all())

    def load_layer(self, layer_id: uuid.UUID, *, layer_type: str) -> LoadedFeatureLayer:
        """Bulk-load a layer as a GeoDataFrame for the analysis engine.

        `feature_id` is this table's own primary key, never the GeoDataFrame's
        positional index and never `external_id` (ADR 005).

        Always includes `macroarea`/`parcelavel`/`land_use`/`quadra_id`/
        `reference_area_m2`/`road_status`/`ca_max` as columns (ADR 008, ADR 009), even for layer
        types that don't use them - they are simply `None` there. This lets
        a calculator filter and group a single `TERRITORIO` layer's
        GeoDataFrame (e.g. `gdf[gdf["macroarea"] == "lote"]`, or dissolve it
        `by="quadra_id"`) without a dedicated layer per category.
        """
        rows = self.list_features(layer_id)
        gdf = gpd.GeoDataFrame(
            {
                "feature_id": [row.id for row in rows],
                "geometry": [to_shape(row.geom) for row in rows],
                "macroarea": [row.macroarea for row in rows],
                "parcelavel": [row.parcelavel for row in rows],
                "land_use": [row.land_use for row in rows],
                "quadra_id": [row.quadra_id for row in rows],
                "road_status": [row.road_status for row in rows],
                "ca_max": [float(row.ca_max) if row.ca_max is not None else None for row in rows],
                "reference_area_m2": [
                    float(row.reference_area_m2) if row.reference_area_m2 is not None else None
                    for row in rows
                ],
            },
            crs="EPSG:4326",
        )
        return LoadedFeatureLayer(
            layer_id=layer_id, layer_type=layer_type, source_crs=gdf.crs, gdf=gdf
        )
