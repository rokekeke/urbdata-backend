"""Temporary road topology and graph construction in a projected metric CRS.

Uploaded centerlines remain untouched. Noding, endpoint snapping and
space-syntax unlink handling happen only in this per-analysis representation.
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

import networkx as nx
from geopandas import GeoDataFrame
from shapely.geometry import (
    GeometryCollection,
    LineString,
    MultiLineString,
    MultiPoint,
    Point,
)
from shapely.geometry.base import BaseGeometry
from shapely.ops import nearest_points, split
from shapely.strtree import STRtree

from app.config.road_hierarchy_mapping import RoadStatus
from app.domain.analysis.warnings import AnalysisWarning, WarningSeverity
from app.domain.geospatial.crs import require_metric_crs

NodeKey = tuple[float, float]


@dataclass(frozen=True, slots=True)
class RoadLine:
    feature_id: UUID
    geometry: LineString
    status: RoadStatus | None


@dataclass(frozen=True, slots=True)
class RoadNetwork:
    graph: nx.MultiGraph[NodeKey]
    warnings: tuple[AnalysisWarning, ...]
    contributing_feature_ids: tuple[UUID, ...]
    snapping_tolerance_m: float

    @property
    def total_length_m(self) -> float:
        return float(sum(data["length_m"] for _, _, data in self.graph.edges(data=True)))

    def length_by_status_m(self, status: RoadStatus) -> float:
        return float(
            sum(
                data["length_m"]
                for _, _, data in self.graph.edges(data=True)
                if data["road_status"] == status.value
            )
        )

    @property
    def intersection_count(self) -> int:
        return sum(1 for node in self.graph.nodes if self.graph.degree(node) >= 3)

    def intersection_count_within(self, boundary: BaseGeometry) -> int:
        """Count real intersections inside or on an analysis boundary.

        External roads remain in the graph for connectivity, but do not
        inflate a density whose denominator is only the project area.
        """
        return sum(
            1
            for node in self.graph.nodes
            if self.graph.degree(node) >= 3 and boundary.covers(Point(node))
        )

    @property
    def proposed_connection_count(self) -> int:
        """Nodes where at least one proposed and one existing edge meet."""
        count = 0
        for node in self.graph.nodes:
            statuses = {
                data["road_status"]
                for _, _, data in self.graph.edges(node, data=True)
                if data["road_status"] is not None
            }
            if {RoadStatus.EXISTING.value, RoadStatus.PROPOSED.value} <= statuses:
                count += 1
        return count


def _node_key(point: Point) -> NodeKey:
    # Micrometre precision is ample for a metric urban network and removes
    # floating noise from GEOS split/intersection operations.
    return (round(point.x, 6), round(point.y, 6))


def _line_parts(geometry: BaseGeometry) -> tuple[LineString, ...]:
    if isinstance(geometry, LineString):
        return (geometry,)
    if isinstance(geometry, MultiLineString):
        return tuple(geometry.geoms)
    if isinstance(geometry, GeometryCollection):
        return tuple(part for part in geometry.geoms if isinstance(part, LineString))
    return ()


def _point_parts(geometry: BaseGeometry) -> tuple[Point, ...]:
    if isinstance(geometry, Point):
        return (geometry,)
    if isinstance(geometry, MultiPoint):
        return tuple(geometry.geoms)
    if isinstance(geometry, GeometryCollection):
        return tuple(part for part in geometry.geoms if isinstance(part, Point))
    return ()


def _intersection_points(geometry: BaseGeometry) -> tuple[Point, ...]:
    if geometry.is_empty:
        return ()
    if isinstance(geometry, Point):
        return (geometry,)
    if isinstance(geometry, MultiPoint):
        return tuple(geometry.geoms)
    if isinstance(geometry, LineString):
        return (Point(geometry.coords[0]), Point(geometry.coords[-1]))
    if isinstance(geometry, MultiLineString | GeometryCollection):
        points: list[Point] = []
        for part in geometry.geoms:
            points.extend(_intersection_points(part))
        return tuple(points)
    return ()


def _snap_endpoints(lines: list[RoadLine], tolerance_m: float) -> list[RoadLine]:
    """Move only line endpoints to the nearest other centerline.

    This connects almost-touching T junctions while avoiding the broad vertex
    displacement caused by snapping whole geometries. Source geometries are
    immutable and never persisted back.
    """
    coordinate_sets = [list(line.geometry.coords) for line in lines]
    endpoint_refs = [
        (line_index, endpoint_index)
        for line_index in range(len(lines))
        for endpoint_index in (0, -1)
    ]
    parents = list(range(len(endpoint_refs)))

    def find(index: int) -> int:
        while parents[index] != index:
            parents[index] = parents[parents[index]]
            index = parents[index]
        return index

    def union(left: int, right: int) -> None:
        left_root, right_root = find(left), find(right)
        if left_root != right_root:
            parents[right_root] = left_root

    endpoint_points = [
        Point(coordinate_sets[line_index][endpoint_index])
        for line_index, endpoint_index in endpoint_refs
    ]
    endpoint_tree = STRtree(endpoint_points)
    for left, left_point in enumerate(endpoint_points):
        for right_value in endpoint_tree.query(left_point.buffer(tolerance_m)):
            right = int(right_value)
            if right <= left:
                continue
            if left_point.distance(endpoint_points[right]) <= tolerance_m:
                union(left, right)

    clusters: dict[int, list[tuple[int, int]]] = {}
    for index, reference in enumerate(endpoint_refs):
        clusters.setdefault(find(index), []).append(reference)
    for references in clusters.values():
        if len(references) < 2:
            continue
        xs = [
            coordinate_sets[line_index][endpoint_index][0]
            for line_index, endpoint_index in references
        ]
        ys = [
            coordinate_sets[line_index][endpoint_index][1]
            for line_index, endpoint_index in references
        ]
        target = (sum(xs) / len(xs), sum(ys) / len(ys))
        for line_index, endpoint_index in references:
            coordinate_sets[line_index][endpoint_index] = target

    clustered_lines = [
        RoadLine(line.feature_id, LineString(coordinates), line.status)
        for line, coordinates in zip(lines, coordinate_sets, strict=True)
    ]
    line_tree = STRtree([line.geometry for line in clustered_lines])
    snapped: list[RoadLine] = []
    for index, line in enumerate(clustered_lines):
        coordinates = list(line.geometry.coords)
        for endpoint_index in (0, -1):
            endpoint = Point(coordinates[endpoint_index])
            best_point: Point | None = None
            best_distance = tolerance_m
            candidates = line_tree.query(endpoint.buffer(tolerance_m))
            for other_value in candidates:
                other_index = int(other_value)
                if other_index == index:
                    continue
                other = clustered_lines[other_index]
                _, candidate = nearest_points(endpoint, other.geometry)
                distance = endpoint.distance(candidate)
                if distance <= best_distance:
                    best_distance = distance
                    best_point = candidate
            if best_point is not None:
                coordinates[endpoint_index] = (best_point.x, best_point.y)
        snapped.append(
            RoadLine(
                feature_id=line.feature_id,
                geometry=LineString(coordinates),
                status=line.status,
            )
        )
    return snapped


def _load_lines(centerlines: GeoDataFrame) -> tuple[list[RoadLine], list[AnalysisWarning]]:
    lines: list[RoadLine] = []
    warnings: list[AnalysisWarning] = []
    for row in centerlines.itertuples(index=False):
        feature_id: UUID = row.feature_id
        geometry: BaseGeometry = row.geometry
        status_value: str | None = getattr(row, "road_status", None)
        try:
            status = RoadStatus(status_value) if status_value is not None else None
        except ValueError:
            status = None
        parts = tuple(
            part for part in _line_parts(geometry) if not part.is_empty and part.length > 0
        )
        if not parts:
            warnings.append(
                AnalysisWarning(
                    code="invalid_road_geometry",
                    message="Uma feicao viaria nao possui geometria linear utilizavel.",
                    feature_ids=(feature_id,),
                )
            )
            continue
        if status is None:
            warnings.append(
                AnalysisWarning(
                    code="road_status_missing",
                    message="Uma via nao foi classificada como existente ou proposta.",
                    feature_ids=(feature_id,),
                    severity=WarningSeverity.INFO,
                )
            )
        lines.extend(RoadLine(feature_id, part, status) for part in parts)
    return lines, warnings


def _resolve_unlinks(
    unlinks: GeoDataFrame | None,
    lines: list[RoadLine],
    tolerance_m: float,
) -> tuple[dict[frozenset[int], tuple[Point, ...]], list[AnalysisWarning]]:
    rules: dict[frozenset[int], list[Point]] = {}
    warnings: list[AnalysisWarning] = []
    if unlinks is None:
        return {}, warnings

    line_tree = STRtree([line.geometry for line in lines])
    for row in unlinks.itertuples(index=False):
        feature_id: UUID = row.feature_id
        geometry: BaseGeometry = row.geometry
        for point in _point_parts(geometry):
            matched = [
                int(index)
                for index in line_tree.query(point.buffer(tolerance_m))
                if lines[int(index)].geometry.distance(point) <= tolerance_m
            ]
            if len(matched) != 2:
                warnings.append(
                    AnalysisWarning(
                        code="invalid_road_unlink",
                        message=(
                            "Um unlink deve identificar exatamente duas linhas viarias; "
                            f"foram encontradas {len(matched)}."
                        ),
                        feature_ids=(feature_id,),
                    )
                )
                continue
            rules.setdefault(frozenset(matched), []).append(point)
    return {pair: tuple(points) for pair, points in rules.items()}, warnings


def _is_unlinked(
    pair: frozenset[int],
    intersection: Point,
    rules: dict[frozenset[int], tuple[Point, ...]],
    tolerance_m: float,
) -> bool:
    return any(point.distance(intersection) <= tolerance_m for point in rules.get(pair, ()))


def _noding_points(
    lines: list[RoadLine],
    unlink_rules: dict[frozenset[int], tuple[Point, ...]],
    tolerance_m: float,
) -> tuple[list[list[Point]], list[AnalysisWarning]]:
    points_by_line: list[list[Point]] = [[] for _ in lines]
    warnings: list[AnalysisWarning] = []
    line_tree = STRtree([line.geometry for line in lines])
    for left_index, left in enumerate(lines):
        for right_value in line_tree.query(left.geometry, predicate="intersects"):
            right_index = int(right_value)
            if right_index <= left_index:
                continue
            right = lines[right_index]
            intersection = left.geometry.intersection(right.geometry)
            if intersection.is_empty:
                continue
            if isinstance(intersection, LineString | MultiLineString):
                warnings.append(
                    AnalysisWarning(
                        code="overlapping_road_centerlines",
                        message="Duas linhas viarias possuem trecho sobreposto.",
                        feature_ids=(left.feature_id, right.feature_id),
                    )
                )
            for point in _intersection_points(intersection):
                pair = frozenset((left_index, right_index))
                if _is_unlinked(pair, point, unlink_rules, tolerance_m):
                    continue
                points_by_line[left_index].append(point)
                points_by_line[right_index].append(point)
    return points_by_line, warnings


def _split_line(line: LineString, points: list[Point]) -> tuple[LineString, ...]:
    unique_points = {_node_key(point): point for point in points}
    interior = [
        point
        for point in unique_points.values()
        if point.distance(Point(line.coords[0])) > 1e-7
        and point.distance(Point(line.coords[-1])) > 1e-7
    ]
    if not interior:
        return (line,)
    pieces = split(line, MultiPoint(interior))
    return tuple(
        part
        for part in pieces.geoms
        if isinstance(part, LineString) and not part.is_empty and part.length > 1e-7
    )


def _connectivity_warnings(graph: nx.MultiGraph[NodeKey]) -> list[AnalysisWarning]:
    warnings: list[AnalysisWarning] = []
    components = list(nx.connected_components(graph))
    if len(components) > 1:
        disconnected_ids = {
            data["source_feature_id"]
            for component in components
            for _, _, data in graph.subgraph(component).edges(data=True)
        }
        warnings.append(
            AnalysisWarning(
                code="disconnected_road_network",
                message=f"A rede viaria possui {len(components)} componentes desconectados.",
                feature_ids=tuple(sorted(disconnected_ids, key=str)),
                severity=WarningSeverity.INFO,
            )
        )

    for component in components:
        component_graph = graph.subgraph(component)
        statuses = {
            data["road_status"]
            for _, _, data in component_graph.edges(data=True)
            if data["road_status"] is not None
        }
        if RoadStatus.PROPOSED.value in statuses and RoadStatus.EXISTING.value not in statuses:
            proposed_ids = {
                data["source_feature_id"]
                for _, _, data in component_graph.edges(data=True)
                if data["road_status"] == RoadStatus.PROPOSED.value
            }
            warnings.append(
                AnalysisWarning(
                    code="proposed_roads_not_connected_to_existing",
                    message=(
                        "Um componente de vias propostas nao se conecta a nenhuma via existente."
                    ),
                    feature_ids=tuple(sorted(proposed_ids, key=str)),
                )
            )
    return warnings


def build_road_network(
    centerlines: GeoDataFrame,
    *,
    unlinks: GeoDataFrame | None = None,
    snapping_tolerance_m: float = 2.0,
) -> RoadNetwork:
    """Build an auditable undirected MultiGraph from uploaded centerlines."""
    if centerlines.crs is None:
        raise ValueError("Road centerlines must have an explicit CRS.")
    require_metric_crs(centerlines.crs)
    if unlinks is not None:
        if unlinks.crs is None:
            raise ValueError("Road unlinks must have an explicit CRS.")
        require_metric_crs(unlinks.crs)
    if snapping_tolerance_m <= 0:
        raise ValueError("snapping_tolerance_m must be positive.")

    lines, warnings = _load_lines(centerlines)
    lines = _snap_endpoints(lines, snapping_tolerance_m)
    unlink_rules, unlink_warnings = _resolve_unlinks(unlinks, lines, snapping_tolerance_m)
    warnings.extend(unlink_warnings)
    points_by_line, noding_warnings = _noding_points(
        lines, unlink_rules, snapping_tolerance_m
    )
    warnings.extend(noding_warnings)

    graph: nx.MultiGraph[NodeKey] = nx.MultiGraph()
    for line, noding_points in zip(lines, points_by_line, strict=True):
        for segment in _split_line(line.geometry, noding_points):
            start = _node_key(Point(segment.coords[0]))
            end = _node_key(Point(segment.coords[-1]))
            graph.add_edge(
                start,
                end,
                length_m=float(segment.length),
                geometry=segment,
                source_feature_id=line.feature_id,
                road_status=line.status.value if line.status is not None else None,
            )

    warnings.extend(_connectivity_warnings(graph))
    contributing_ids = tuple(sorted({line.feature_id for line in lines}, key=str))
    return RoadNetwork(
        graph=graph,
        warnings=tuple(warnings),
        contributing_feature_ids=contributing_ids,
        snapping_tolerance_m=snapping_tolerance_m,
    )
