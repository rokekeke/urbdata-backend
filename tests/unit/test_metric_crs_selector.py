import pytest
from pyproj import CRS, Transformer
from shapely.geometry import GeometryCollection, box
from shapely.ops import transform

from app.domain.analysis.exceptions import MetricCRSSelectionError
from app.domain.geospatial.crs import DEFAULT_METRIC_CRS, select_metric_crs


def test_approved_wkt_is_epsg_32722() -> None:
    assert DEFAULT_METRIC_CRS.to_epsg() == 32722
    assert DEFAULT_METRIC_CRS.is_projected


def test_zone_22s_is_the_preferred_default() -> None:
    project = box(-52.0, -27.0, -51.9, -26.9)

    selected = select_metric_crs(project, 4326)

    assert selected.to_epsg() == 32722


def test_another_brazilian_zone_is_selected_from_pyproj_database() -> None:
    project = box(-47.1, -23.1, -47.0, -23.0)

    selected = select_metric_crs(project, 4326)

    assert selected.to_epsg() == 32723


def test_projected_source_is_transformed_before_selection() -> None:
    project_wgs84 = box(-52.0, -27.0, -51.9, -26.9)
    transformer = Transformer.from_crs(4326, 3857, always_xy=True)
    project_web_mercator = transform(transformer.transform, project_wgs84)

    selected = select_metric_crs(project_web_mercator, 3857)

    assert selected.to_epsg() == 32722


def test_project_crossing_utm_zones_fails_explicitly() -> None:
    project = box(-48.1, -25.0, -47.9, -24.9)

    with pytest.raises(MetricCRSSelectionError, match="No single WGS 84 UTM zone"):
        select_metric_crs(project, CRS.from_epsg(4326))


def test_missing_crs_and_empty_geometry_are_rejected() -> None:
    with pytest.raises(MetricCRSSelectionError, match="source CRS"):
        select_metric_crs(box(-52.0, -27.0, -51.9, -26.9), None)

    with pytest.raises(MetricCRSSelectionError, match="non-empty"):
        select_metric_crs(GeometryCollection(), 4326)
