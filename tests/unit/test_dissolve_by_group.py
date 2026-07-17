import uuid

import pytest
from geopandas import GeoDataFrame
from shapely.geometry import GeometryCollection, Polygon

from app.domain.geospatial.geometry import dissolve_by_group


def _square(west: float, south: float, east: float, north: float) -> Polygon:
    return Polygon([(west, south), (east, south), (east, north), (west, north)])


def test_groups_and_dissolves_each_quadra_separately() -> None:
    q1_a, q1_b, q2_a = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    gdf = GeoDataFrame(
        {
            "feature_id": [q1_a, q1_b, q2_a],
            "geometry": [
                _square(0, 0, 10, 10),
                _square(10, 0, 20, 10),
                _square(0, 20, 5, 25),
            ],
            "quadra_id": ["Q1", "Q1", "Q2"],
        },
        crs="EPSG:31982",
    )

    result = dissolve_by_group(gdf, group_column="quadra_id")

    assert set(result) == {"Q1", "Q2"}
    q1_geometry, q1_contributing, q1_skipped = result["Q1"]
    assert q1_geometry.area == pytest.approx(200.0)
    assert set(q1_contributing) == {q1_a, q1_b}
    assert q1_skipped == ()
    q2_geometry, q2_contributing, _ = result["Q2"]
    assert q2_geometry.area == pytest.approx(25.0)
    assert q2_contributing == (q2_a,)


def test_rows_with_no_group_value_are_excluded_entirely() -> None:
    grouped, ungrouped = uuid.uuid4(), uuid.uuid4()
    gdf = GeoDataFrame(
        {
            "feature_id": [grouped, ungrouped],
            "geometry": [_square(0, 0, 10, 10), _square(50, 50, 60, 60)],
            "quadra_id": ["Q1", None],
        },
        crs="EPSG:31982",
    )

    result = dissolve_by_group(gdf, group_column="quadra_id")

    assert set(result) == {"Q1"}
    assert ungrouped not in result["Q1"][1]


def test_a_group_where_every_geometry_is_invalid_is_skipped_not_raised() -> None:
    gdf = GeoDataFrame(
        {
            "feature_id": [uuid.uuid4()],
            "geometry": [GeometryCollection()],
            "quadra_id": ["Q1"],
        },
        crs="EPSG:31982",
    )

    result = dissolve_by_group(gdf, group_column="quadra_id")

    assert result == {}
