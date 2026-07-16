import pytest
from shapely.geometry import Polygon

from app.domain.analysis.exceptions import MetricCRSSelectionError
from app.domain.geospatial.geometry import area_m2, length_m


def test_metric_operations_accept_projected_metric_crs() -> None:
    square = Polygon([(0, 0), (100, 0), (100, 100), (0, 100)])

    assert area_m2(square, crs=31982) == pytest.approx(10_000.0)
    assert length_m(square, crs=31982) == pytest.approx(400.0)


def test_metric_operations_reject_epsg_4326() -> None:
    square = Polygon([(0, 0), (1, 0), (1, 1), (0, 1)])

    with pytest.raises(MetricCRSSelectionError):
        area_m2(square, crs=4326)
