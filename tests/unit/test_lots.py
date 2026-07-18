import uuid

import pytest
from geopandas import GeoDataFrame
from pyproj import CRS
from shapely.geometry import box

from app.domain.geospatial.context import GeospatialContext
from app.domain.geospatial.layers import LoadedFeatureLayer
from app.domain.indicators.lots import (
    calculate_lot_frontage_from_context,
    calculate_parceling_efficiency_from_context,
)

METRIC_CRS = CRS.from_epsg(32722)


def _context(gdf: GeoDataFrame) -> GeospatialContext:
    layer = LoadedFeatureLayer(
        layer_id=uuid.uuid4(), layer_type="territorio", source_crs=METRIC_CRS, gdf=gdf
    )
    return GeospatialContext(
        project_version_id=uuid.uuid4(), metric_crs=METRIC_CRS, layers={"territorio": layer}
    )


class TestLotFrontage:
    def test_lot_touching_the_road_gets_its_full_perimeter_as_frontage(self) -> None:
        # Road: a 100x2m strip. Lot: a 10x1m strip sitting right on top of
        # it - short enough that its whole boundary (not just the shared
        # edge) stays within the 3m tolerance buffer, so the expected
        # frontage is the lot's exact perimeter: 2*(10+1) = 22.
        road_id, lot_id = uuid.uuid4(), uuid.uuid4()
        gdf = GeoDataFrame(
            {
                "feature_id": [road_id, lot_id],
                "macroarea": ["sistema_viario", "lote"],
                "reference_area_m2": [None, None],
                "geometry": [box(0, -1, 100, 1), box(0, 1, 10, 2)],
            },
            crs=METRIC_CRS,
        )

        result = calculate_lot_frontage_from_context(_context(gdf))

        assert result.indicator_code == "lots.frontage_length"
        assert result.raw_value == {str(lot_id): pytest.approx(22.0)}
        assert result.warnings == ()

    def test_lot_far_from_any_road_gets_zero_frontage(self) -> None:
        road_id, lot_id = uuid.uuid4(), uuid.uuid4()
        gdf = GeoDataFrame(
            {
                "feature_id": [road_id, lot_id],
                "macroarea": ["sistema_viario", "lote"],
                "reference_area_m2": [None, None],
                "geometry": [box(0, -1, 100, 1), box(200, 200, 210, 210)],
            },
            crs=METRIC_CRS,
        )

        result = calculate_lot_frontage_from_context(_context(gdf))

        assert result.raw_value == {str(lot_id): 0.0}
        assert result.warnings == ()

    def test_no_road_layer_warns_and_zeroes_every_lot(self) -> None:
        lot_id = uuid.uuid4()
        gdf = GeoDataFrame(
            {
                "feature_id": [lot_id],
                "macroarea": ["lote"],
                "reference_area_m2": [None],
                "geometry": [box(0, 0, 10, 10)],
            },
            crs=METRIC_CRS,
        )

        result = calculate_lot_frontage_from_context(_context(gdf))

        assert result.raw_value == {str(lot_id): 0.0}
        assert {w.code for w in result.warnings} == {"no_road_footprint_for_frontage"}


class TestParcelingEfficiency:
    def test_lots_fully_covering_the_quadra_score_one(self) -> None:
        # Two adjacent 10x10 lots with no internal gap dissolve into exactly
        # their combined footprint, so efficiency is exactly 1.0.
        lot_a, lot_b = uuid.uuid4(), uuid.uuid4()
        gdf = GeoDataFrame(
            {
                "feature_id": [lot_a, lot_b],
                "macroarea": ["lote", "lote"],
                "quadra_id": ["Q1", "Q1"],
                "reference_area_m2": [None, None],
                "geometry": [box(0, 0, 10, 10), box(10, 0, 20, 10)],
            },
            crs=METRIC_CRS,
        )

        result = calculate_parceling_efficiency_from_context(_context(gdf))

        assert result.indicator_code == "lots.parceling_efficiency"
        assert result.raw_value == {"Q1": pytest.approx(1.0)}
        assert set(result.contributing_feature_ids) == {lot_a, lot_b}

    def test_reference_area_wins_over_geometry_in_the_numerator(self) -> None:
        # Single-lot quadra: geometric area is 100, but a valid
        # reference_area_m2 (70) must be the one used - per the project's
        # area-resolution invariant, not the geometry.
        lot_id = uuid.uuid4()
        gdf = GeoDataFrame(
            {
                "feature_id": [lot_id],
                "macroarea": ["lote"],
                "quadra_id": ["Q1"],
                "reference_area_m2": [70.0],
                "geometry": [box(0, 0, 10, 10)],
            },
            crs=METRIC_CRS,
        )

        result = calculate_parceling_efficiency_from_context(_context(gdf))

        assert result.raw_value == {"Q1": pytest.approx(0.7)}
        assert any(w.code == "area_reference_divergence" for w in result.warnings)

    def test_lot_without_quadra_id_is_excluded_and_warned(self) -> None:
        lot_id = uuid.uuid4()
        gdf = GeoDataFrame(
            {
                "feature_id": [lot_id],
                "macroarea": ["lote"],
                "quadra_id": [None],
                "reference_area_m2": [None],
                "geometry": [box(0, 0, 10, 10)],
            },
            crs=METRIC_CRS,
        )

        result = calculate_parceling_efficiency_from_context(_context(gdf))

        assert result.raw_value == {}
        assert {w.code for w in result.warnings} == {"lot_without_quadra"}
