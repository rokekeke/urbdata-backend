import uuid

import pytest
from geopandas import GeoDataFrame
from pyproj import CRS
from shapely.geometry import Polygon

from app.domain.analysis.exceptions import IndicatorCalculationError
from app.domain.geospatial.context import GeospatialContext
from app.domain.geospatial.layers import LoadedFeatureLayer
from app.domain.indicators.density import (
    calculate_built_open_ratio_from_context,
    calculate_ca_coverage_from_context,
    calculate_lot_count_with_ca_from_context,
    calculate_max_computable_area_from_context,
    calculate_non_residential_ca_from_context,
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
            "parcelavel": [True, True, True, False],
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


def test_max_computable_area_uses_resolved_area_times_ca_and_ignores_non_lots() -> None:
    # Feature 0 has a valid reference_area_m2 (80.0) that diverges from its
    # 100 m2 geometry by 25% - the project invariant says the reference wins
    # when present (see geometry.py::resolve_feature_area), so the expected
    # total is 80*2.0 + 100*0.0 = 160.0, not 100*2.0 + 100*0.0 = 200.0.
    context, feature_ids = _context()

    result = calculate_max_computable_area_from_context(context)

    assert result.raw_value == pytest.approx(160.0)
    assert set(result.contributing_feature_ids) == {feature_ids[0], feature_ids[2]}
    assert {warning.code for warning in result.warnings} == {
        "area_reference_divergence",
        "lot_ca_missing",
    }


def test_zero_ca_is_valid_and_missing_ca_is_not_counted() -> None:
    context, _ = _context()

    result = calculate_lot_count_with_ca_from_context(context)

    assert result.raw_value == 2


def test_ca_coverage_is_weighted_by_resolved_lot_area() -> None:
    # Resolved areas: feature 0 = 80.0 (reference wins), feature 1 = 100.0
    # (no reference, geometric fallback), feature 2 = 100.0 (reference,
    # matches geometry). Covered (ca_max not None) = feature 0 + feature 2.
    context, _ = _context()

    result = calculate_ca_coverage_from_context(context)

    assert result.raw_value == pytest.approx((80.0 + 100.0) / (80.0 + 100.0 + 100.0))
    assert result.unit == "ratio"


def test_built_open_ratio_divides_built_potential_by_non_lot_territory() -> None:
    # Built potential (same fixture as the max_computable_area test): 160.0.
    # Non-Lote territory here is just the single AVL feature, 100 m2
    # (geometric area, no reference_area_m2 override) - so ratio = 1.6.
    context, _ = _context()

    result = calculate_built_open_ratio_from_context(context)

    assert result.raw_value == pytest.approx(1.6)
    assert result.unit == "ratio"
    assert {warning.code for warning in result.warnings} == {
        "area_reference_divergence",
        "lot_ca_missing",
    }


def test_built_open_ratio_fails_hard_when_no_open_space_exists() -> None:
    feature_ids = [uuid.uuid4() for _ in range(2)]
    gdf = GeoDataFrame(
        {
            "feature_id": feature_ids,
            "macroarea": ["lote", "lote"],
            "parcelavel": [True, True],
            "ca_max": [1.0, 2.0],
            "reference_area_m2": [None, None],
            "geometry": [_square(0), _square(20)],
        },
        crs=METRIC_CRS,
    )
    layer = LoadedFeatureLayer(
        layer_id=uuid.uuid4(),
        layer_type="territorio",
        source_crs=METRIC_CRS,
        gdf=gdf,
    )
    context = GeospatialContext(
        project_version_id=uuid.uuid4(),
        metric_crs=METRIC_CRS,
        layers={"territorio": layer},
    )

    with pytest.raises(IndicatorCalculationError):
        calculate_built_open_ratio_from_context(context)


def _non_residential_context(
    land_uses: list[str], ca_values: list[float | None]
) -> tuple[GeospatialContext, list[uuid.UUID]]:
    n = len(land_uses)
    feature_ids = [uuid.uuid4() for _ in range(n)]
    gdf = GeoDataFrame(
        {
            "feature_id": feature_ids,
            "macroarea": ["lote"] * n,
            "parcelavel": [True] * n,
            "land_use": land_uses,
            "ca_max": ca_values,
            "reference_area_m2": [None] * n,
            "geometry": [_square(20 * i) for i in range(n)],
        },
        crs=METRIC_CRS,
    )
    layer = LoadedFeatureLayer(
        layer_id=uuid.uuid4(),
        layer_type="territorio",
        source_crs=METRIC_CRS,
        gdf=gdf,
    )
    context = GeospatialContext(
        project_version_id=uuid.uuid4(),
        metric_crs=METRIC_CRS,
        layers={"territorio": layer},
    )
    return context, feature_ids


def test_non_residential_ca_excludes_residential_and_misto_lots() -> None:
    # lot 0: comercial, area 100, ca 2.0 -> built 200 (counts)
    # lot 1: servicos, area 100, ca 1.5 -> built 150 (counts)
    # lot 2: residencial, area 100, ca 3.0 -> excluded (wrong use)
    # lot 3: comercial, area 100, ca None -> excluded (missing CA, warned)
    # lot 4: "comercial;servicos" -> resolves to Misto -> excluded
    context, feature_ids = _non_residential_context(
        ["comercial", "servicos", "residencial", "comercial", "comercial;servicos"],
        [2.0, 1.5, 3.0, None, 5.0],
    )

    result = calculate_non_residential_ca_from_context(context)

    assert result.raw_value == pytest.approx((100 * 2.0 + 100 * 1.5) / (100 + 100))
    assert result.unit == "ratio"
    assert set(result.contributing_feature_ids) == {feature_ids[0], feature_ids[1]}
    assert {warning.code for warning in result.warnings} == {"lot_ca_missing"}
    assert result.warnings[0].feature_ids == (feature_ids[3],)


def test_non_residential_ca_degrades_gracefully_for_all_residential_project() -> None:
    context, _ = _non_residential_context(["residencial", "residencial"], [1.0, 2.0])

    result = calculate_non_residential_ca_from_context(context)

    assert result.raw_value is None
    assert result.contributing_feature_ids == ()
    assert {warning.code for warning in result.warnings} == {"no_non_residential_lot"}
