"""Road-network indicators over uploaded centerlines and optional unlinks."""

from collections.abc import Callable

from app.config.road_hierarchy_mapping import RoadStatus
from app.domain.analysis.result import IndicatorCalculation
from app.domain.geospatial.context import GeospatialContext
from app.domain.geospatial.geometry import dissolve
from app.domain.geospatial.networks import RoadNetwork, build_road_network

ROAD_LAYER = "sistema_viario"
UNLINK_LAYER = "desconexoes_viarias"
PERIMETER_LAYER = "perimetro"
DEFAULT_SNAPPING_TOLERANCE_M = 2.0


def _road_network(context: GeospatialContext) -> RoadNetwork:
    tolerance = float(
        context.parameters.get("road_snapping_tolerance_m", DEFAULT_SNAPPING_TOLERANCE_M)
    )

    def build() -> RoadNetwork:
        unlinks = context.metric_gdf(UNLINK_LAYER) if UNLINK_LAYER in context.layers else None
        return build_road_network(
            context.metric_gdf(ROAD_LAYER),
            unlinks=unlinks,
            snapping_tolerance_m=tolerance,
        )

    return context.cached(f"road_network:{tolerance}", build)


def _source_layers(
    context: GeospatialContext, *, include_perimeter: bool = False
) -> tuple[str, ...]:
    source = [ROAD_LAYER]
    if UNLINK_LAYER in context.layers:
        source.append(UNLINK_LAYER)
    if include_perimeter:
        source.append(PERIMETER_LAYER)
    return tuple(source)


def _numeric_result(
    context: GeospatialContext,
    *,
    code: str,
    unit: str,
    value: float | int,
    include_perimeter: bool = False,
) -> IndicatorCalculation:
    network = _road_network(context)
    return IndicatorCalculation(
        indicator_code=code,
        theme="road_network",
        formula_version="1.0.0",
        raw_value=value,
        unit=unit,
        metric_crs=str(context.metric_crs_value()),
        source_layers=_source_layers(context, include_perimeter=include_perimeter),
        contributing_feature_ids=network.contributing_feature_ids,
        parameters={"snapping_tolerance_m": network.snapping_tolerance_m},
        warnings=network.warnings,
    )


def calculate_total_length_from_context(context: GeospatialContext) -> IndicatorCalculation:
    return _numeric_result(
        context,
        code="road_network.total_length",
        unit="m",
        value=_road_network(context).total_length_m,
    )


def _length_calculator(
    status: RoadStatus, code: str
) -> Callable[[GeospatialContext], IndicatorCalculation]:
    def calculate(context: GeospatialContext) -> IndicatorCalculation:
        return _numeric_result(
            context,
            code=code,
            unit="m",
            value=_road_network(context).length_by_status_m(status),
        )

    return calculate


calculate_existing_length_from_context = _length_calculator(
    RoadStatus.EXISTING, "road_network.existing_length"
)
calculate_proposed_length_from_context = _length_calculator(
    RoadStatus.PROPOSED, "road_network.proposed_length"
)


def calculate_intersection_count_from_context(context: GeospatialContext) -> IndicatorCalculation:
    return _numeric_result(
        context,
        code="road_network.intersection_count",
        unit="count",
        value=_road_network(context).intersection_count,
    )


def calculate_intersection_density_from_context(context: GeospatialContext) -> IndicatorCalculation:
    perimeter, _, _ = dissolve(context.metric_gdf(PERIMETER_LAYER))
    gross_area_km2 = perimeter.area / 1_000_000
    intersections_inside = _road_network(context).intersection_count_within(perimeter)
    density = intersections_inside / gross_area_km2 if gross_area_km2 else 0.0
    return _numeric_result(
        context,
        code="road_network.intersection_density",
        unit="count/km2",
        value=density,
        include_perimeter=True,
    )


def calculate_link_node_ratio_from_context(context: GeospatialContext) -> IndicatorCalculation:
    graph = _road_network(context).graph
    ratio = graph.number_of_edges() / graph.number_of_nodes() if graph.number_of_nodes() else 0.0
    return _numeric_result(
        context,
        code="road_network.link_node_ratio",
        unit="adimensional",
        value=ratio,
    )


def calculate_proposed_connection_count_from_context(
    context: GeospatialContext,
) -> IndicatorCalculation:
    return _numeric_result(
        context,
        code="road_network.proposed_connection_count",
        unit="count",
        value=_road_network(context).proposed_connection_count,
    )
