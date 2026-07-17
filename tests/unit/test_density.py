import uuid

import pytest
from geopandas import GeoDataFrame
from pyproj import CRS
from shapely.geometry import Polygon

from app.domain.geospatial.context import GeospatialContext
from app.domain.geospatial.layers import LoadedFeatureLayer
from app.domain.indicators.density import (
    calculate_ca_coverage_from_context,
    calculate_lot_count_with_ca_from_context,
    calculate_max_computable_area_from_context,
)

METRIC_CRS = CRS.from_epsg(32722)


def _square(x: float, size: float = 10) -> Polygon:
    return Polygon([(x, 0), (x + size, 0), (x + size, size), (x, size)])


def _context() -> tuple[GeospatialContext, list[uuid.UUID]]:
    feature_ids = [uuid.uuid4() for _ in range(4)]
    gdf = GeoDataFrame(
        {
            "feature_id": feature_ids,
            "macroarea": ["lote", "lote", "lote", "avl"],
            "ca_max": [2.0, None, 0.0, 99.0],
            "reference_area_m2": [80.0, None, 100.0, None],
            "geometry": [_square(0), _square(20), _square(40), _square(60)],
        },
        crs=METRIC_CRS,
    )
    layer = LoadedFeatureLayer(
        layer_id=uuid.uuid4(),
        layer_type="territorio",
        source_crs=METRIC_CRS,
        gdf=gdf,
    )
    return (
        GeospatialContext(
            project_version_id=uuid.uuid4(),
            metric_crs=METRIC_CRS,
            layers={"territorio": layer},
        ),
        feature_ids,
    )


def test_max_computable_area_uses_geometry_times_ca_and_ignores_non_lots() -> None:
    context, feature_ids = _context()

    result = calculate_max_computable_area_from_context(context)

    assert result.raw_value == pytest.approx(200.0)
    assert set(result.contributing_feature_ids) == {feature_ids[0], feature_ids[2]}
    assert result.parameters["area_source"] == "imported_geometry"
    assert {warning.code for warning in result.warnings} == {
        "area_reference_divergence",
        "lot_ca_missing",
    }


def test_zero_ca_is_valid_and_missing_ca_is_not_counted() -> None:
    context, _ = _context()

    result = calculate_lot_count_with_ca_from_context(context)

    assert result.raw_value == 2


def test_ca_coverage_is_weighted_by_geometric_lot_area() -> None:
    context, _ = _context()

    result = calculate_ca_coverage_from_context(context)

    assert result.raw_value == pytest.approx(2 / 3)
    assert result.unit == "ratio"
