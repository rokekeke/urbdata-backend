from dataclasses import dataclass, field
from uuid import UUID

from geopandas import GeoDataFrame
from pyproj import CRS

from app.domain.analysis.exceptions import RequiredLayerMissingError
from app.domain.geospatial.layers import LoadedFeatureLayer


@dataclass(slots=True)
class GeospatialContext:
    """Concentrates the layers and metric CRS shared by one analysis run.

    Indicator calculators read from this instead of the database. Each
    layer is reprojected to `metric_crs` at most once per execution: the
    reprojected GeoDataFrame is cached, never the source geometry, so the
    persisted feature geometries are never touched (ADR 001, BT-013).
    """

    project_version_id: UUID
    metric_crs: CRS
    layers: dict[str, LoadedFeatureLayer]
    _metric_cache: dict[str, GeoDataFrame] = field(default_factory=dict, init=False, repr=False)

    def metric_gdf(self, layer_type: str) -> GeoDataFrame:
        try:
            layer = self.layers[layer_type]
        except KeyError as exc:
            raise RequiredLayerMissingError(
                "Required layer is not available in this analysis context.",
                context={"layer_type": layer_type},
            ) from exc
        if layer_type not in self._metric_cache:
            self._metric_cache[layer_type] = layer.gdf.to_crs(self.metric_crs)
        return self._metric_cache[layer_type]

    def metric_crs_value(self) -> str | int:
        """The metric CRS as an EPSG code (or WKT string fallback), for
        recording on an `IndicatorCalculation` - shared by every calculator
        instead of each re-deriving it from `self.metric_crs`."""
        epsg = self.metric_crs.to_epsg()
        return epsg if epsg is not None else self.metric_crs.to_string()
