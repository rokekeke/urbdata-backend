"""Bulk PostGIS layer and feature loading adapter."""

import uuid
from collections.abc import Callable
from typing import Any

import geopandas as gpd
from geoalchemy2 import Geography
from geoalchemy2.shape import from_shape, to_shape
from shapely.geometry import shape as shapely_shape
from sqlalchemy import cast, func
from sqlalchemy.orm import Session, aliased

from app.domain.geospatial.layers import LoadedFeatureLayer, resolve_single_layer_id
from app.domain.geospatial.spatial_relations import SpatialRelation
from app.infrastructure.database.models.feature import Feature
from app.infrastructure.database.models.layer import LayerStatus, LayerType, ProjectLayer

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

    def list_features(self, layer_id: uuid.UUID) -> list[Feature]:
        return list(self._session.query(Feature).filter(Feature.layer_id == layer_id).all())

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
        """
        rows = self.list_features(layer_id)
        gdf = gpd.GeoDataFrame(
            {
                "feature_id": [row.id for row in rows],
                "geometry": [to_shape(row.geom) for row in rows],
            },
            crs="EPSG:4326",
        )
        return LoadedFeatureLayer(
            layer_id=layer_id, layer_type=layer_type, source_crs=gdf.crs, gdf=gdf
        )
