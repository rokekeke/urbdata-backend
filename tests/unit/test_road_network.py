import uuid

import pytest
from geopandas import GeoDataFrame
from shapely.geometry import LineString, Point, Polygon

from app.config.road_hierarchy_mapping import RoadStatus
from app.domain.geospatial.networks import build_road_network

METRIC_CRS = "EPSG:32722"


def _roads(*rows: tuple[LineString, str | None]) -> GeoDataFrame:
    return GeoDataFrame(
        {
            "feature_id": [uuid.uuid4() for _ in rows],
            "road_status": [status for _, status in rows],
            "geometry": [geometry for geometry, _ in rows],
        },
        crs=METRIC_CRS,
    )


def _unlinks(*points: Point) -> GeoDataFrame:
    return GeoDataFrame(
        {"feature_id": [uuid.uuid4() for _ in points], "geometry": list(points)},
        crs=METRIC_CRS,
    )


def test_crossing_centerlines_are_noded() -> None:
    roads = _roads(
        (LineString([(-10, 0), (10, 0)]), RoadStatus.EXISTING.value),
        (LineString([(0, -10), (0, 10)]), RoadStatus.PROPOSED.value),
    )

    network = build_road_network(roads)

    assert network.graph.number_of_nodes() == 5
    assert network.graph.number_of_edges() == 4
    assert network.intersection_count == 1
    assert network.proposed_connection_count == 1
    assert network.total_length_m == pytest.approx(40.0)


def test_unlink_prevents_planar_crossing_from_becoming_a_connection() -> None:
    roads = _roads(
        (LineString([(-10, 0), (10, 0)]), RoadStatus.EXISTING.value),
        (LineString([(0, -10), (0, 10)]), RoadStatus.EXISTING.value),
    )

    network = build_road_network(roads, unlinks=_unlinks(Point(0, 0)))

    assert network.graph.number_of_nodes() == 4
    assert network.graph.number_of_edges() == 2
    assert network.intersection_count == 0
    assert "disconnected_road_network" in {warning.code for warning in network.warnings}


def test_close_endpoints_snap_and_connect_proposed_to_existing() -> None:
    roads = _roads(
        (LineString([(0, 0), (10, 0)]), RoadStatus.EXISTING.value),
        (LineString([(10.8, 0), (20, 0)]), RoadStatus.PROPOSED.value),
    )

    network = build_road_network(roads, snapping_tolerance_m=1.0)

    assert network.graph.number_of_nodes() == 3
    assert network.graph.number_of_edges() == 2
    assert network.proposed_connection_count == 1
    assert "proposed_roads_not_connected_to_existing" not in {
        warning.code for warning in network.warnings
    }


def test_disconnected_proposed_component_is_reported_but_kept() -> None:
    roads = _roads(
        (LineString([(0, 0), (10, 0)]), RoadStatus.EXISTING.value),
        (LineString([(100, 0), (110, 0)]), RoadStatus.PROPOSED.value),
    )

    network = build_road_network(roads)

    assert network.total_length_m == pytest.approx(20.0)
    assert {
        "disconnected_road_network",
        "proposed_roads_not_connected_to_existing",
    } <= {warning.code for warning in network.warnings}


def test_invalid_unlink_is_reported_instead_of_guessing() -> None:
    roads = _roads((LineString([(0, 0), (10, 0)]), RoadStatus.EXISTING.value))

    network = build_road_network(roads, unlinks=_unlinks(Point(100, 100)))

    assert "invalid_road_unlink" in {warning.code for warning in network.warnings}


def test_unknown_status_remains_unclassified_with_warning() -> None:
    roads = _roads((LineString([(0, 0), (10, 0)]), "desconhecida"))

    network = build_road_network(roads)

    assert network.length_by_status_m(RoadStatus.EXISTING) == 0
    assert network.length_by_status_m(RoadStatus.PROPOSED) == 0
    assert "road_status_missing" in {warning.code for warning in network.warnings}


def test_external_intersections_remain_in_graph_but_can_be_excluded_from_density() -> None:
    roads = _roads(
        (LineString([(-10, 0), (10, 0)]), RoadStatus.EXISTING.value),
        (LineString([(0, -10), (0, 10)]), RoadStatus.EXISTING.value),
        (LineString([(90, 100), (110, 100)]), RoadStatus.EXISTING.value),
        (LineString([(100, 90), (100, 110)]), RoadStatus.EXISTING.value),
    )
    project_boundary = Polygon([(-20, -20), (20, -20), (20, 20), (-20, 20)])

    network = build_road_network(roads)

    assert network.intersection_count == 2
    assert network.intersection_count_within(project_boundary) == 1
