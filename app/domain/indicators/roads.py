"""Road-network indicators over uploaded centerlines and optional unlinks."""

from collections.abc import Callable, Sequence
from itertools import pairwise

from shapely.geometry import GeometryCollection, LineString, MultiLineString, MultiPoint, Point
from shapely.geometry.base import BaseGeometry

from app.config.road_hierarchy_mapping import RoadStatus
from app.domain.analysis.result import IndicatorCalculation
from app.domain.geospatial.context import GeospatialContext
from app.domain.geospatial.geometry import dissolve
from app.domain.geospatial.networks import RoadNetwork, build_road_network

ROAD_LAYER = "sistema_viario"
UNLINK_LAYER = "desconexoes_viarias"
PERIMETER_LAYER = "perimetro"
DEFAULT_SNAPPING_TOLERANCE_M = 2.0


def road_network_from_context(context: GeospatialContext) -> RoadNetwork:
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
    network = road_network_from_context(context)
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
        value=road_network_from_context(context).total_length_m,
    )


def _length_calculator(
    status: RoadStatus, code: str
) -> Callable[[GeospatialContext], IndicatorCalculation]:
    def calculate(context: GeospatialContext) -> IndicatorCalculation:
        return _numeric_result(
            context,
            code=code,
            unit="m",
            value=road_network_from_context(context).length_by_status_m(status),
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
        value=road_network_from_context(context).intersection_count,
    )


def calculate_intersection_density_from_context(context: GeospatialContext) -> IndicatorCalculation:
    perimeter, _, _ = dissolve(context.metric_gdf(PERIMETER_LAYER))
    gross_area_km2 = perimeter.area / 1_000_000
    intersections_inside = road_network_from_context(context).intersection_count_within(perimeter)
    density = intersections_inside / gross_area_km2 if gross_area_km2 else 0.0
    return _numeric_result(
        context,
        code="road_network.intersection_density",
        unit="count/km2",
        value=density,
        include_perimeter=True,
    )


def calculate_link_node_ratio_from_context(context: GeospatialContext) -> IndicatorCalculation:
    graph = road_network_from_context(context).graph
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
        value=road_network_from_context(context).proposed_connection_count,
    )


def _boundary_rings(geometry: BaseGeometry) -> tuple[LineString, ...]:
    """Decompose a (Multi)Polygon's boundary into its constituent rings -
    the exterior ring plus any interior/hole rings, for every part of a
    MultiPolygon. A simple Polygon's `.boundary` is already a single
    LineString; a MultiPolygon or a polygon with holes gives a
    MultiLineString instead."""
    boundary = geometry.boundary
    if isinstance(boundary, LineString):
        return (boundary,)
    if isinstance(boundary, MultiLineString):
        return tuple(boundary.geoms)
    return ()


def _crossing_points(ring: LineString, road_geometries: Sequence[LineString]) -> list[Point]:
    """Every point where a road geometry touches or crosses *ring*.

    Uploaded projects rarely have road geometry on both sides of the
    boundary (the platform only ever receives the project's own layers,
    never off-site context), so the common case is a road *ending* right
    on the boundary rather than passing through it - Shapely's
    intersection already reports that correctly as a single Point, no
    special-casing needed. A road that runs along the boundary for a
    stretch (a degenerate case) intersects as a (Multi)LineString instead;
    its two endpoints are taken as the crossing points, same as a winding
    road that touches the boundary more than once resolves to a MultiPoint.
    """
    points: list[Point] = []
    for road in road_geometries:
        intersection = ring.intersection(road)
        if intersection.is_empty:
            continue
        if isinstance(intersection, Point):
            points.append(intersection)
        elif isinstance(intersection, MultiPoint):
            points.extend(intersection.geoms)
        elif isinstance(intersection, LineString):
            points.append(Point(intersection.coords[0]))
            points.append(Point(intersection.coords[-1]))
        elif isinstance(intersection, MultiLineString | GeometryCollection):
            for part in intersection.geoms:
                if isinstance(part, Point):
                    points.append(part)
                elif isinstance(part, LineString):
                    points.append(Point(part.coords[0]))
                    points.append(Point(part.coords[-1]))
    return points


def _max_gap_along_ring(ring: LineString, points: Sequence[Point]) -> float:
    """Largest gap, in meters, between consecutive road crossings around a
    closed ring - including the wraparound gap between the last and first
    crossing, since a ring has no start or end for this purpose. Zero
    crossings on this ring means the whole ring is a single gap."""
    ring_length = float(ring.length)
    if not points:
        return ring_length
    positions = sorted(float(ring.project(point)) for point in points)
    gaps = [later - earlier for earlier, later in pairwise(positions)]
    gaps.append(ring_length - positions[-1] + positions[0])
    return max(gaps)


def calculate_max_boundary_gap_from_context(context: GeospatialContext) -> IndicatorCalculation:
    """LEED-ND / LEED for Cities "Conectividade viaria": maior intervalo,
    em metros, entre cruzamentos consecutivos da rede viaria com o limite
    do projeto, percorrendo todo o perimetro (incluindo o intervalo entre
    o ultimo e o primeiro cruzamento - o limite e um anel fechado, sem
    inicio nem fim).

    Reaproveita os mesmos segmentos ja processados pela rede viaria
    (`road_network_from_context(context).graph`), a mesma representacao canonica que
    os demais indicadores road_network.* ja usam, em vez de voltar para a
    camada bruta. Conta vias existentes e propostas igualmente - a
    certificacao fala em conectar a rede externa, o que uma via proposta
    tambem serve, entao nao ha razao de domino para filtrar por status
    aqui (diferente de existing_length/proposed_length, que existem
    justamente para separar os dois).

    Guarda o intervalo maximo bruto, nao um sim/nao ja comparado com os
    245m (pre-requisito) ou 180m (credito) da certificacao - mesmo
    espirito dos demais indicadores desta leva (notas Obsidian 88/90): o
    numero bruto serve para qualquer limiar que uma certificacao pedir.

    Zero cruzamentos com o limite (nenhuma via alcanca o perimetro) nao e
    erro - o intervalo maximo passa a ser o perimetro inteiro, um
    resultado legitimo (mesmo espirito de degradacao gracil que os demais
    indicadores road_network.* ja usam para rede viaria vazia).
    """
    perimeter, _, _ = dissolve(context.metric_gdf(PERIMETER_LAYER))
    rings = _boundary_rings(perimeter)
    network_edges = road_network_from_context(context).graph.edges(data=True)
    road_geometries = [data["geometry"] for _, _, data in network_edges]

    max_gap = max(
        (_max_gap_along_ring(ring, _crossing_points(ring, road_geometries)) for ring in rings),
        default=0.0,
    )

    return _numeric_result(
        context,
        code="road_network.max_boundary_gap",
        unit="m",
        value=max_gap,
        include_perimeter=True,
    )
