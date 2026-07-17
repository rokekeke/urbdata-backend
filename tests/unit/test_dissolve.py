import uuid

import pytest
from geopandas import GeoDataFrame
from shapely.geometry import GeometryCollection, Polygon

from app.domain.analysis.exceptions import InvalidGeometryError
from app.domain.geospatial.geometry import dissolve


def _feature_ids(n: int) -> list[uuid.UUID]:
    return [uuid.uuid4() for _ in range(n)]


def test_dissolve_unions_touching_polygons_and_reports_contributors() -> None:
    left = Polygon([(0, 0), (10, 0), (10, 10), (0, 10)])
    right = Polygon([(10, 0), (20, 0), (20, 10), (10, 10)])
    ids = _feature_ids(2)
    gdf = GeoDataFrame({"feature_id": ids, "geometry": [left, right]}, crs="EPSG:31982")

    geometry, contributing, skipped = dissolve(gdf)

    assert geometry.area == pytest.approx(200.0)
    assert set(contributing) == set(ids)
    assert skipped == ()


def test_dissolve_skips_empty_and_null_geometries() -> None:
    square = Polygon([(0, 0), (10, 0), (10, 10), (0, 10)])
    ids = _feature_ids(3)
    gdf = GeoDataFrame(
        {"feature_id": ids, "geometry": [square, GeometryCollection(), None]},
        crs="EPSG:31982",
    )

    geometry, contributing, skipped = dissolve(gdf)

    assert geometry.area == pytest.approx(100.0)
    assert contributing == (ids[0],)
    assert set(skipped) == {ids[1], ids[2]}


def test_dissolve_raises_when_nothing_is_valid() -> None:
    ids = _feature_ids(1)
    gdf = GeoDataFrame({"feature_id": ids, "geometry": [None]}, crs="EPSG:31982")

    with pytest.raises(InvalidGeometryError):
        dissolve(gdf)
