"""Runs the `square_perimeter` golden case end to end through the domain
layer only (no database): GeoJSON in, CRS selection, dissolve, and every
registered territorial calculator. See
tests/reference_cases/square_perimeter/calculation_notes.md for how each
expected value was derived independently.
"""

import json
import uuid
from collections.abc import Callable
from pathlib import Path

import pytest
from geopandas import GeoDataFrame
from pyproj import CRS
from shapely.geometry import shape

from app.domain.analysis.result import IndicatorCalculation
from app.domain.geospatial.context import GeospatialContext
from app.domain.geospatial.crs import select_metric_crs
from app.domain.geospatial.geometry import dissolve
from app.domain.geospatial.layers import LoadedFeatureLayer
from app.domain.indicators.territorial import (
    calculate_compactness_from_context,
    calculate_perimeter_from_context,
    calculate_total_area_from_context,
)

CASE_DIR = Path(__file__).parent.parent / "reference_cases" / "square_perimeter"

_CALCULATORS: dict[str, Callable[[GeospatialContext], IndicatorCalculation]] = {
    "territorial.total_area": calculate_total_area_from_context,
    "territorial.perimeter": calculate_perimeter_from_context,
    "territorial.compactness": calculate_compactness_from_context,
}


def _load_perimeter_layer() -> LoadedFeatureLayer:
    geojson = json.loads((CASE_DIR / "input.geojson").read_text(encoding="utf-8"))
    geometries = [shape(feature["geometry"]) for feature in geojson["features"]]
    gdf = GeoDataFrame(
        {"feature_id": [uuid.uuid4() for _ in geometries], "geometry": geometries},
        crs="EPSG:4326",
    )
    return LoadedFeatureLayer(
        layer_id=uuid.uuid4(), layer_type="perimetro", source_crs=CRS.from_epsg(4326), gdf=gdf
    )


def test_square_perimeter_golden_case() -> None:
    expected = json.loads((CASE_DIR / "expected_results.json").read_text(encoding="utf-8"))
    layer = _load_perimeter_layer()

    project_geometry_wgs84, _, _ = dissolve(layer.gdf)
    metric_crs = select_metric_crs(project_geometry_wgs84, layer.source_crs)
    assert metric_crs.to_epsg() == expected["metric_crs_epsg"]
    context = GeospatialContext(
        project_version_id=uuid.uuid4(), metric_crs=metric_crs, layers={"perimetro": layer}
    )

    for expected_indicator in expected["indicators"]:
        calculator = _CALCULATORS[expected_indicator["indicator_code"]]
        result = calculator(context)

        assert result.indicator_code == expected_indicator["indicator_code"]
        assert result.unit == expected_indicator["unit"]
        assert result.raw_value == pytest.approx(
            expected_indicator["value"], abs=expected_indicator["tolerance_abs"]
        )
        assert result.warnings == ()
