import uuid

import pytest
from geopandas import GeoDataFrame
from pyproj import CRS
from shapely.geometry import LineString, Polygon

from app.domain.geospatial.context import GeospatialContext
from app.domain.geospatial.layers import LoadedFeatureLayer
from app.domain.indicators.catalog import build_registry

METRIC_CRS = CRS.from_epsg(32722)


def _layer(layer_type: str, gdf: GeoDataFrame) -> LoadedFeatureLayer:
    return LoadedFeatureLayer(
        layer_id=uuid.uuid4(), layer_type=layer_type, source_crs=METRIC_CRS, gdf=gdf
    )


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
