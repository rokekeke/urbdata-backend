"""Bulk PostGIS layer and feature loading adapter."""

import uuid
from typing import Any

import geopandas as gpd
from geoalchemy2.shape import from_shape, to_shape
from shapely.geometry import shape as shapely_shape
from sqlalchemy.orm import Session

from app.domain.geospatial.layers import LoadedFeatureLayer
from app.infrastructure.database.models.feature import Feature
from app.infrastructure.database.models.layer import LayerStatus, LayerType, ProjectLayer


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
        `AttributeError`. Duplicate layers of the same type are not yet
        disambiguated (BT-011 is still open); the first match wins.
        """
        layer = (
            self._session.query(ProjectLayer)
            .filter(
                ProjectLayer.project_version_id == project_version_id,
                ProjectLayer.layer_type == LayerType(layer_type),
            )
            .first()
        )
        if layer is None:
            return None
        return self.load_layer(layer.id, layer_type=layer.layer_type.value)

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
