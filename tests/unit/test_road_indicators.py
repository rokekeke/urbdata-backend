import uuid

import pytest
from geopandas import GeoDataFrame
from pyproj import CRS
from shapely.geometry import LineString, Polygon

from app.domain.geospatial.context import GeospatialContext
from app.domain.geospatial.layers import LoadedFeatureLayer
from app.domain.indicators.catalog import build_registry
from app.domain.indicators.roads import calculate_max_boundary_gap_from_context

METRIC_CRS = CRS.from_epsg(32722)


def _layer(layer_type: str, gdf: GeoDataFrame) -> LoadedFeatureLayer:
    return LoadedFeatureLayer(
        layer_id=uuid.uuid4(), layer_type=layer_type, source_crs=METRIC_CRS, gdf=gdf
    )


SQUARE_PERIMETER = Polygon([(0, 0), (100, 0), (100, 100), (0, 100)])  # perimeter length 400


def _road_gdf(road_ids: list[uuid.UUID], geometries: list[LineString]) -> GeoDataFrame:
    return GeoDataFrame(
        {
            "feature_id": road_ids,
            "road_status": ["existente"] * len(road_ids),
            "geometry": geometries,
        },
        crs=METRIC_CRS,
    )


def _boundary_gap_context(road_geometries: list[LineString]) -> GeospatialContext:
    road_ids = [uuid.uuid4() for _ in road_geometries]
    perimeter = GeoDataFrame(
        {"feature_id": [uuid.uuid4()], "geometry": [SQUARE_PERIMETER]}, crs=METRIC_CRS
    )
    return GeospatialContext(
        project_version_id=uuid.uuid4(),
        metric_crs=METRIC_CRS,
        layers={
            "sistema_viario": _layer("sistema_viario", _road_gdf(road_ids, road_geometries)),
            "perimetro": _layer("perimetro", perimeter),
        },
    )


class TestMaxBoundaryGap:
    def test_no_road_reaches_the_boundary_reports_the_whole_perimeter(self) -> None:
        # Well inside the 100x100 square, touching no edge at all.
        context = _boundary_gap_context([LineString([(40, 40), (60, 60)])])

        result = calculate_max_boundary_gap_from_context(context)

        assert result.indicator_code == "road_network.max_boundary_gap"
        assert result.unit == "m"
        assert result.raw_value == pytest.approx(400.0)

    def test_four_evenly_spaced_crossings_report_a_quarter_of_the_perimeter(self) -> None:
        # One short road crosses the midpoint of each of the 4 sides:
        # (50,0), (100,50), (50,100), (0,50) - 100m apart along the ring
        # each way, including the wraparound.
        context = _boundary_gap_context(
            [
                LineString([(50, -10), (50, 10)]),
                LineString([(90, 50), (110, 50)]),
                LineString([(50, 90), (50, 110)]),
                LineString([(-10, 50), (10, 50)]),
            ]
        )

        result = calculate_max_boundary_gap_from_context(context)

        assert result.raw_value == pytest.approx(100.0)

    def test_wraparound_gap_is_reported_when_it_is_the_largest(self) -> None:
        # Three crossings bunched near the ring's start (distances 10, 20,
        # 30 along the bottom edge from (0,0)): the internal gaps are only
        # 10m each, but the gap closing the loop back to the first crossing
        # (400 - 30 + 10 = 380) is by far the largest - this would be
        # missed by code that only looks at consecutive pairs and forgets
        # the ring is closed.
        context = _boundary_gap_context(
            [
                LineString([(10, -10), (10, 10)]),
                LineString([(20, -10), (20, 10)]),
                LineString([(30, -10), (30, 10)]),
            ]
        )

        result = calculate_max_boundary_gap_from_context(context)

        assert result.raw_value == pytest.approx(380.0)


def test_road_theme_calculates_existing_proposed_and_connectivity_metrics() -> None:
    road_ids = [uuid.uuid4(), uuid.uuid4()]
    roads = GeoDataFrame(
        {
            "feature_id": road_ids,
            "road_status": ["existente", "proposta"],
            "geometry": [
                LineString([(-10, 0), (10, 0)]),
                LineString([(0, -10), (0, 10)]),
            ],
        },
        crs=METRIC_CRS,
    )
    perimeter = GeoDataFrame(
        {
            "feature_id": [uuid.uuid4()],
            "geometry": [
                Polygon([(-500, -500), (500, -500), (500, 500), (-500, 500)])
            ],
        },
        crs=METRIC_CRS,
    )
    context = GeospatialContext(
        project_version_id=uuid.uuid4(),
        metric_crs=METRIC_CRS,
        layers={
            "sistema_viario": _layer("sistema_viario", roads),
            "perimetro": _layer("perimetro", perimeter),
        },
        parameters={"road_snapping_tolerance_m": 2.0},
    )

    results = {
        definition.code: definition.calculator(context)
        for definition in build_registry().by_theme("road_network")
    }

    assert results["road_network.total_length"].raw_value == pytest.approx(40.0)
    assert results["road_network.existing_length"].raw_value == pytest.approx(20.0)
    assert results["road_network.proposed_length"].raw_value == pytest.approx(20.0)
    assert results["road_network.intersection_count"].raw_value == 1
    assert results["road_network.intersection_density"].raw_value == pytest.approx(1.0)
    assert results["road_network.link_node_ratio"].raw_value == pytest.approx(0.8)
    assert results["road_network.proposed_connection_count"].raw_value == 1
    assert results["road_network.total_length"].parameters == {"snapping_tolerance_m": 2.0}
    assert set(results["road_network.total_length"].contributing_feature_ids) == set(road_ids)
