import math
import uuid

import pytest
from geopandas import GeoDataFrame
from pyproj import CRS
from shapely.geometry import GeometryCollection, Polygon

from app.domain.geospatial.context import GeospatialContext
from app.domain.geospatial.layers import LoadedFeatureLayer
from app.domain.indicators.territorial import (
    calculate_compactness,
    calculate_compactness_from_context,
    calculate_perimeter,
    calculate_perimeter_from_context,
    calculate_total_area,
    calculate_total_area_from_context,
)


def test_calculate_total_area_returns_the_geometry_area_in_metric_crs() -> None:
    square = Polygon([(0, 0), (100, 0), (100, 100), (0, 100)])
    feature_id = uuid.uuid4()

    result = calculate_total_area(
        square, metric_crs=31982, contributing_feature_ids=(feature_id,)
    )

    assert result.indicator_code == "territorial.total_area"
    assert result.theme == "territorial"
    assert result.unit == "m2"
    assert result.raw_value == pytest.approx(10_000.0)
    assert result.metric_crs == "31982"
    assert result.contributing_feature_ids == (feature_id,)
    assert result.warnings == ()


def test_calculate_total_area_from_context_dissolves_the_perimeter_layer() -> None:
    ok_id, skipped_id = uuid.uuid4(), uuid.uuid4()
    square = Polygon([(-52.0, -27.0), (-52.0, -26.999), (-51.999, -26.999), (-51.999, -27.0)])
    gdf = GeoDataFrame(
        {"feature_id": [ok_id, skipped_id], "geometry": [square, GeometryCollection()]},
        crs="EPSG:4326",
    )
    layer = LoadedFeatureLayer(
        layer_id=uuid.uuid4(), layer_type="perimetro", source_crs=CRS.from_epsg(4326), gdf=gdf
    )
    context = GeospatialContext(
        project_version_id=uuid.uuid4(),
        metric_crs=CRS.from_epsg(32722),
        layers={"perimetro": layer},
    )

    result = calculate_total_area_from_context(context)

    assert isinstance(result.raw_value, float) and result.raw_value > 0
    assert result.contributing_feature_ids == (ok_id,)
    assert len(result.warnings) == 1
    assert result.warnings[0].feature_ids == (skipped_id,)


def test_calculate_perimeter_returns_the_boundary_length_in_metric_crs() -> None:
    square = Polygon([(0, 0), (100, 0), (100, 100), (0, 100)])
    feature_id = uuid.uuid4()

    result = calculate_perimeter(square, metric_crs=31982, contributing_feature_ids=(feature_id,))

    assert result.indicator_code == "territorial.perimeter"
    assert result.theme == "territorial"
    assert result.unit == "m"
    assert result.raw_value == pytest.approx(400.0)
    assert result.metric_crs == "31982"
    assert result.contributing_feature_ids == (feature_id,)


def test_calculate_perimeter_from_context_dissolves_the_perimeter_layer() -> None:
    square = Polygon([(-52.0, -27.0), (-52.0, -26.999), (-51.999, -26.999), (-51.999, -27.0)])
    gdf = GeoDataFrame({"feature_id": [uuid.uuid4()], "geometry": [square]}, crs="EPSG:4326")
    layer = LoadedFeatureLayer(
        layer_id=uuid.uuid4(), layer_type="perimetro", source_crs=CRS.from_epsg(4326), gdf=gdf
    )
    context = GeospatialContext(
        project_version_id=uuid.uuid4(),
        metric_crs=CRS.from_epsg(32722),
        layers={"perimetro": layer},
    )

    result = calculate_perimeter_from_context(context)

    assert isinstance(result.raw_value, float) and result.raw_value > 0


def test_calculate_compactness_of_a_square_is_pi_over_four() -> None:
    square = Polygon([(0, 0), (100, 0), (100, 100), (0, 100)])

    result = calculate_compactness(square, metric_crs=31982)

    assert result.indicator_code == "territorial.compactness"
    assert result.unit == "adimensional"
    assert result.raw_value == pytest.approx(math.pi / 4)
    assert result.parameters["formula"] == "4*pi*area/perimeter^2"


def test_calculate_compactness_from_context_dissolves_the_perimeter_layer() -> None:
    square = Polygon([(-52.0, -27.0), (-52.0, -26.999), (-51.999, -26.999), (-51.999, -27.0)])
    gdf = GeoDataFrame({"feature_id": [uuid.uuid4()], "geometry": [square]}, crs="EPSG:4326")
    layer = LoadedFeatureLayer(
        layer_id=uuid.uuid4(), layer_type="perimetro", source_crs=CRS.from_epsg(4326), gdf=gdf
    )
    context = GeospatialContext(
        project_version_id=uuid.uuid4(),
        metric_crs=CRS.from_epsg(32722),
        layers={"perimetro": layer},
    )

    result = calculate_compactness_from_context(context)

    assert isinstance(result.raw_value, float)
    assert 0 < result.raw_value <= 1
