import uuid
from typing import Any

import pytest
from geopandas import GeoDataFrame
from pyproj import CRS
from shapely.geometry import LineString, box

from app.domain.geospatial.context import GeospatialContext
from app.domain.geospatial.layers import LoadedFeatureLayer
from app.domain.indicators.lots import (
    calculate_distance_to_green_area_from_context,
    calculate_distance_to_non_residential_use_from_context,
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


# --- Network-distance indicators (item 5, nota Obsidian 90) -----------------
#
# Road footprint (territorio, macroarea=sistema_viario) and road centerline
# (sistema_viario layer) both run along y=0 from x=0 to x=100 - a single
# straight edge, so the road graph has exactly two nodes, (0,0) and (100,0),
# 100m apart. Lots are 10x10 with their bottom edge exactly on the footprint's
# top edge (y=0), symmetric around their own center, so each one's frontage
# midpoint lands predictably at (center_x, 0) regardless of which direction
# Shapely happens to traverse the overlap ring in (see _frontage_geometry).
#
# Query lots snap to their nearest node, not the nearest point along the
# edge (confirmed simplification, nota 90 item 5) - a lot at x=5 is 5m from
# node (0,0), so R-to-C's expected distance is the sum of both "last mile"
# hops plus the full 100m edge: 5 + 100 + 5 = 110, not the 90m a straight
# reading of the two midpoints would suggest. That gap is the known,
# documented cost of the simplification, not a bug - it is largest exactly
# on long, node-sparse edges like this one, which is why this test fixture
# deliberately uses a single 100m edge instead of a finer grid.


def _territorio_gdf(rows: list[dict[str, Any]]) -> GeoDataFrame:
    return GeoDataFrame(
        {
            "feature_id": [row["feature_id"] for row in rows],
            "macroarea": [row["macroarea"] for row in rows],
            "land_use": [row.get("land_use") for row in rows],
            "reference_area_m2": [None] * len(rows),
            "geometry": [row["geometry"] for row in rows],
        },
        crs=METRIC_CRS,
    )


def _distance_context(rows: list[dict[str, Any]]) -> GeospatialContext:
    layers = {
        "territorio": LoadedFeatureLayer(
            layer_id=uuid.uuid4(),
            layer_type="territorio",
            source_crs=METRIC_CRS,
            gdf=_territorio_gdf(rows),
        ),
        "sistema_viario": LoadedFeatureLayer(
            layer_id=uuid.uuid4(),
            layer_type="sistema_viario",
            source_crs=METRIC_CRS,
            gdf=GeoDataFrame(
                {
                    "feature_id": [uuid.uuid4()],
                    "road_status": ["existente"],
                    "geometry": [LineString([(0, 0), (100, 0)])],
                },
                crs=METRIC_CRS,
            ),
        ),
    }
    return GeospatialContext(
        project_version_id=uuid.uuid4(), metric_crs=METRIC_CRS, layers=layers
    )


ROAD_FOOTPRINT = box(0, -2, 100, 0)


def _lot(
    feature_id: uuid.UUID, x0: float, macroarea: str = "lote", **kwargs: Any
) -> dict[str, Any]:
    return {
        "feature_id": feature_id,
        "macroarea": macroarea,
        "geometry": box(x0, 0, x0 + 10, 10),
        **kwargs,
    }


def _road_row(feature_id: uuid.UUID) -> dict[str, Any]:
    return {"feature_id": feature_id, "macroarea": "sistema_viario", "geometry": ROAD_FOOTPRINT}


class TestDistanceToNonResidentialUse:
    def test_residential_lot_reaches_the_nearby_commercial_lot(self) -> None:
        road_id, r_id, c_id = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
        context = _distance_context(
            [
                _road_row(road_id),
                _lot(r_id, 0, land_use="residencial"),
                _lot(c_id, 90, land_use="comercial"),
            ]
        )

        result = calculate_distance_to_non_residential_use_from_context(context)

        assert result.indicator_code == "lots.distance_to_non_residential_use"
        assert result.unit == "m"
        assert result.raw_value == {str(r_id): pytest.approx(110.0)}
        assert c_id in result.contributing_feature_ids

    def test_lot_without_street_frontage_is_excluded_not_nulled(self) -> None:
        road_id, r_id, c_id, isolated_id = uuid.uuid4(), uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
        context = _distance_context(
            [
                _road_row(road_id),
                _lot(r_id, 0, land_use="residencial"),
                _lot(c_id, 90, land_use="comercial"),
                {
                    "feature_id": isolated_id,
                    "macroarea": "lote",
                    "land_use": "residencial",
                    "geometry": box(500, 500, 510, 510),
                },
            ]
        )

        result = calculate_distance_to_non_residential_use_from_context(context)

        assert isinstance(result.raw_value, dict)
        assert str(isolated_id) not in result.raw_value
        assert str(r_id) in result.raw_value
        assert {w.code for w in result.warnings} == {"lot_without_street_frontage"}

    def test_no_non_residential_lot_degrades_to_none_with_a_warning(self) -> None:
        road_id, r_id = uuid.uuid4(), uuid.uuid4()
        context = _distance_context([_road_row(road_id), _lot(r_id, 0, land_use="residencial")])

        result = calculate_distance_to_non_residential_use_from_context(context)

        assert result.raw_value == {str(r_id): None}
        assert {w.code for w in result.warnings} == {"no_non_residential_target"}

    def test_misto_lot_counts_as_a_non_residential_target(self) -> None:
        road_id, r_id, misto_id = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
        context = _distance_context(
            [
                _road_row(road_id),
                _lot(r_id, 0, land_use="residencial"),
                _lot(misto_id, 90, land_use="residencial;comercial"),
            ]
        )

        result = calculate_distance_to_non_residential_use_from_context(context)

        # R reaches the Misto lot normally. Misto is *also* a query lot
        # (residencial+misto are both query categories) and the only
        # available target - but a lot must never count itself as its own
        # target, so once it excludes itself there is nothing left and it
        # correctly reports None, not a bogus near-zero self-distance.
        assert result.raw_value == {str(r_id): pytest.approx(110.0), str(misto_id): None}


class TestDistanceToGreenArea:
    def test_residential_lot_reaches_the_nearby_green_area(self) -> None:
        road_id, r_id, avl_id = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
        context = _distance_context(
            [
                _road_row(road_id),
                _lot(r_id, 0, land_use="residencial"),
                _lot(avl_id, 90, macroarea="avl"),
            ]
        )

        result = calculate_distance_to_green_area_from_context(context)

        assert result.indicator_code == "lots.distance_to_green_area"
        assert result.raw_value == {str(r_id): pytest.approx(110.0)}
        assert avl_id in result.contributing_feature_ids

    def test_no_green_area_degrades_to_none_with_a_warning(self) -> None:
        road_id, r_id = uuid.uuid4(), uuid.uuid4()
        context = _distance_context([_road_row(road_id), _lot(r_id, 0, land_use="residencial")])

        result = calculate_distance_to_green_area_from_context(context)

        assert result.raw_value == {str(r_id): None}
        assert {w.code for w in result.warnings} == {"no_green_area_target"}
