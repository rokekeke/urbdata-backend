import uuid

import pytest
from geopandas import GeoDataFrame
from pyproj import CRS
from shapely.geometry import Polygon

from app.domain.analysis.exceptions import RequiredLayerMissingError
from app.domain.geospatial.context import GeospatialContext
from app.domain.geospatial.layers import LoadedFeatureLayer


def _perimeter_layer() -> LoadedFeatureLayer:
    square = Polygon([(-52.0, -27.0), (-52.0, -26.999), (-51.999, -26.999), (-51.999, -27.0)])
    gdf = GeoDataFrame({"feature_id": [uuid.uuid4()], "geometry": [square]}, crs="EPSG:4326")
    return LoadedFeatureLayer(
        layer_id=uuid.uuid4(), layer_type="perimetro", source_crs=CRS.from_epsg(4326), gdf=gdf
    )


def test_metric_gdf_reprojects_to_the_selected_crs() -> None:
    context = GeospatialContext(
        project_version_id=uuid.uuid4(),
        metric_crs=CRS.from_epsg(32722),
        layers={"perimetro": _perimeter_layer()},
    )

    reprojected = context.metric_gdf("perimetro")

    assert reprojected.crs.to_epsg() == 32722


def test_metric_gdf_is_cached_across_calls() -> None:
    context = GeospatialContext(
        project_version_id=uuid.uuid4(),
        metric_crs=CRS.from_epsg(32722),
        layers={"perimetro": _perimeter_layer()},
    )

    first = context.metric_gdf("perimetro")
    second = context.metric_gdf("perimetro")

    assert first is second


def test_metric_gdf_raises_for_a_layer_type_outside_the_context() -> None:
    context = GeospatialContext(
        project_version_id=uuid.uuid4(), metric_crs=CRS.from_epsg(32722), layers={}
    )

    with pytest.raises(RequiredLayerMissingError):
        context.metric_gdf("perimetro")


def test_derived_object_is_built_only_once() -> None:
    context = GeospatialContext(
        project_version_id=uuid.uuid4(), metric_crs=CRS.from_epsg(32722), layers={}
    )
    calls = 0

    def build() -> object:
        nonlocal calls
        calls += 1
        return object()

    first = context.cached("road_network", build)
    second = context.cached("road_network", build)

    assert first is second
    assert calls == 1
