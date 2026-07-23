"""Quadra (block) indicators, derived by dissolving lots that share a
`quadra_id` (ADR 009) - no quadra geometry is ever uploaded directly.
"""

import math
from collections.abc import Sequence
from dataclasses import dataclass
from uuid import UUID

from shapely.geometry.base import BaseGeometry

from app.config.macroarea_mapping import Macroarea
from app.domain.analysis.result import IndicatorCalculation
from app.domain.analysis.warnings import AnalysisWarning, WarningSeverity
from app.domain.geospatial.context import GeospatialContext
from app.domain.geospatial.geometry import area_m2, dissolve_by_group, length_m

TERRITORIO_LAYER = "territorio"

# BT-053/054: short-block floor (Jane Jacobs) and local legal maximum for a
# quadra face, confirmed by the responsible urbanist 17/07/2026 - see
# Obsidian note 15. The score never reaches zero at the legal limit itself
# (0.1) - zero is reserved for signaling "no data"/invalid cases elsewhere
# in the domain, not "at the boundary of compliance".
FACE_LENGTH_IDEAL_M = 120.0
FACE_LENGTH_LEGAL_LIMIT_M = 250.0
FACE_LENGTH_SCORE_FLOOR = 0.1


@dataclass(frozen=True, slots=True)
class QuadraGeometry:
    quadra_id: str
    geometry: BaseGeometry
    lot_feature_ids: tuple[UUID, ...]


def _min_rotated_rectangle_dimensions(geometry: BaseGeometry) -> tuple[float, float]:
    """(comprimento, largura) - the two distinct edge lengths of the minimum
    rotated rectangle bounding *geometry*, longer edge first. *geometry* is
    assumed already in a metric CRS, so adjacent-corner distances are
    already meters - no separate CRS argument needed."""
    rectangle = geometry.minimum_rotated_rectangle
    corners = list(rectangle.exterior.coords)
    edge_a = math.dist(corners[0], corners[1])
    edge_b = math.dist(corners[1], corners[2])
    return (max(edge_a, edge_b), min(edge_a, edge_b))


def quadras_from_context(
    context: GeospatialContext,
) -> tuple[tuple[QuadraGeometry, ...], tuple[AnalysisWarning, ...]]:
    """Filter the TERRITORIO layer to Lote features and dissolve them by
    `quadra_id`. A lot without a `quadra_id` (or whose whole group turned
    out invalid) is excluded and reported via an info warning - it simply
    doesn't participate in any block-level indicator, rather than being
    silently dropped."""
    gdf = context.metric_gdf(TERRITORIO_LAYER)
    lots = gdf[gdf["macroarea"] == Macroarea.LOTE.value]
    grouped = dissolve_by_group(lots, group_column="quadra_id")

    quadras = tuple(
        QuadraGeometry(quadra_id=quadra_id, geometry=geometry, lot_feature_ids=contributing)
        for quadra_id, (geometry, contributing, _skipped) in grouped.items()
    )

    grouped_ids = {feature_id for quadra in quadras for feature_id in quadra.lot_feature_ids}
    ungrouped_ids = tuple(
        feature_id for feature_id in lots["feature_id"] if feature_id not in grouped_ids
    )
    warnings = (
        (
            AnalysisWarning(
                code="lot_without_quadra",
                message=(
                    "Um ou mais lotes nao tem quadra_id definido e ficaram de fora "
                    "da analise por quadra."
                ),
                feature_ids=ungrouped_ids,
                severity=WarningSeverity.INFO,
            ),
        )
        if ungrouped_ids
        else ()
    )
    return quadras, warnings


def _quadra_contributing_ids(quadras: Sequence[QuadraGeometry]) -> tuple[UUID, ...]:
    return tuple(feature_id for quadra in quadras for feature_id in quadra.lot_feature_ids)


def calculate_quadra_stats(
    quadras: Sequence[QuadraGeometry],
    *,
    metric_crs: str | int,
    warnings: tuple[AnalysisWarning, ...] = (),
) -> IndicatorCalculation:
    """BT-050: area, perimeter, and lot count per quadra. `unit="composto"`
    because the value nests three different units per quadra - see
    `parameters` for what each key means."""
    stats = {
        quadra.quadra_id: {
            "area_m2": area_m2(quadra.geometry, crs=metric_crs),
            "perimetro_m": length_m(quadra.geometry, crs=metric_crs),
            "quantidade_lotes": len(quadra.lot_feature_ids),
        }
        for quadra in quadras
    }
    return IndicatorCalculation(
        indicator_code="quadras.stats",
        theme="quadras",
        formula_version="1.0.0",
        raw_value=stats,
        unit="composto",
        metric_crs=str(metric_crs),
        source_layers=(TERRITORIO_LAYER,),
        contributing_feature_ids=_quadra_contributing_ids(quadras),
        parameters={"metric_crs": str(metric_crs)},
        warnings=warnings,
    )


def calculate_quadra_stats_from_context(context: GeospatialContext) -> IndicatorCalculation:
    """BT-050: `IndicatorDefinition.calculator` for `quadras.stats`."""
    quadras, quadra_warnings = quadras_from_context(context)
    return calculate_quadra_stats(
        quadras, metric_crs=context.metric_crs_value(), warnings=quadra_warnings
    )


def calculate_quadra_compactness(
    quadras: Sequence[QuadraGeometry],
    *,
    metric_crs: str | int,
    warnings: tuple[AnalysisWarning, ...] = (),
) -> IndicatorCalculation:
    """BT-051: Polsby-Popper isoperimetric quotient per quadra outline -
    same formula and interpretation as `territorial.compactness`."""
    compactness = {}
    for quadra in quadras:
        area = area_m2(quadra.geometry, crs=metric_crs)
        perimeter = length_m(quadra.geometry, crs=metric_crs)
        compactness[quadra.quadra_id] = (4 * math.pi * area) / (perimeter**2)
    return IndicatorCalculation(
        indicator_code="quadras.compactness",
        theme="quadras",
        formula_version="1.0.0",
        raw_value=compactness,
        unit="adimensional",
        metric_crs=str(metric_crs),
        source_layers=(TERRITORIO_LAYER,),
        contributing_feature_ids=_quadra_contributing_ids(quadras),
        parameters={"metric_crs": str(metric_crs), "formula": "4*pi*area/perimeter^2"},
        warnings=warnings,
    )


def calculate_quadra_compactness_from_context(context: GeospatialContext) -> IndicatorCalculation:
    """BT-051: `IndicatorDefinition.calculator` for `quadras.compactness`."""
    quadras, quadra_warnings = quadras_from_context(context)
    return calculate_quadra_compactness(
        quadras, metric_crs=context.metric_crs_value(), warnings=quadra_warnings
    )


def calculate_quadra_min_rotated_rectangle(
    quadras: Sequence[QuadraGeometry],
    *,
    metric_crs: str | int,
    warnings: tuple[AnalysisWarning, ...] = (),
) -> IndicatorCalculation:
    """BT-052: dimensions (comprimento/largura, in m) of the minimum
    rotated rectangle bounding each quadra's outline - standard
    computational geometry (`shapely.minimum_rotated_rectangle`), no domain
    ambiguity."""
    dimensions: dict[str, dict[str, float]] = {}
    for quadra in quadras:
        comprimento, largura = _min_rotated_rectangle_dimensions(quadra.geometry)
        dimensions[quadra.quadra_id] = {"comprimento_m": comprimento, "largura_m": largura}
    return IndicatorCalculation(
        indicator_code="quadras.min_rotated_rectangle",
        theme="quadras",
        formula_version="1.0.0",
        raw_value=dimensions,
        unit="composto",
        metric_crs=str(metric_crs),
        source_layers=(TERRITORIO_LAYER,),
        contributing_feature_ids=_quadra_contributing_ids(quadras),
        parameters={"metric_crs": str(metric_crs), "metodo": "shapely.minimum_rotated_rectangle"},
        warnings=warnings,
    )


def calculate_quadra_min_rotated_rectangle_from_context(
    context: GeospatialContext,
) -> IndicatorCalculation:
    """BT-052: `IndicatorDefinition.calculator` for `quadras.min_rotated_rectangle`."""
    quadras, quadra_warnings = quadras_from_context(context)
    return calculate_quadra_min_rotated_rectangle(
        quadras, metric_crs=context.metric_crs_value(), warnings=quadra_warnings
    )


def _face_length_score(comprimento_m: float) -> float:
    """1.0 at or below the short-block floor (120m), decaying linearly to
    0.1 at the local legal maximum (250m) and beyond - never all the way to
    zero, since the legal-limit boundary still represents a real, if poor,
    outcome. Values beyond the legal limit are flagged via a separate
    warning, not by driving the score any lower."""
    if comprimento_m <= FACE_LENGTH_IDEAL_M:
        return 1.0
    if comprimento_m >= FACE_LENGTH_LEGAL_LIMIT_M:
        return FACE_LENGTH_SCORE_FLOOR
    span = FACE_LENGTH_LEGAL_LIMIT_M - FACE_LENGTH_IDEAL_M
    decay = (comprimento_m - FACE_LENGTH_IDEAL_M) / span
    return 1.0 - (1.0 - FACE_LENGTH_SCORE_FLOOR) * decay


def calculate_quadra_face_length_score(
    quadras: Sequence[QuadraGeometry],
    *,
    metric_crs: str | int,
    warnings: tuple[AnalysisWarning, ...] = (),
) -> IndicatorCalculation:
    """BT-053/054: quality score for block face length, linear from 1.0 at
    120m (Jane Jacobs' short-block floor) down to 0.1 at 250m (local legal
    maximum for a quadra face). Reuses the longer edge of each quadra's
    minimum rotated rectangle (`quadras.min_rotated_rectangle`) as the face
    length proxy - a documented approximation, not a literal
    crossing-to-crossing measurement. Any quadra above the legal limit also
    gets an explicit non-conformity warning, not just a floored score."""
    scores: dict[str, float] = {}
    compliance_warnings: list[AnalysisWarning] = []
    for quadra in quadras:
        comprimento, _largura = _min_rotated_rectangle_dimensions(quadra.geometry)
        scores[quadra.quadra_id] = _face_length_score(comprimento)
        if comprimento > FACE_LENGTH_LEGAL_LIMIT_M:
            compliance_warnings.append(
                AnalysisWarning(
                    code="block_face_out_of_compliance",
                    message=(
                        f"Quadra '{quadra.quadra_id}' tem face de "
                        f"{comprimento:.1f}m, acima do limite legal de "
                        f"{FACE_LENGTH_LEGAL_LIMIT_M:.0f}m."
                    ),
                    feature_ids=quadra.lot_feature_ids,
                    severity=WarningSeverity.WARNING,
                )
            )
    return IndicatorCalculation(
        indicator_code="quadras.face_length_score",
        theme="quadras",
        formula_version="1.0.0",
        raw_value=scores,
        unit="adimensional",
        metric_crs=str(metric_crs),
        source_layers=(TERRITORIO_LAYER,),
        contributing_feature_ids=_quadra_contributing_ids(quadras),
        parameters={
            "metric_crs": str(metric_crs),
            "comprimento_ideal_m": FACE_LENGTH_IDEAL_M,
            "comprimento_limite_legal_m": FACE_LENGTH_LEGAL_LIMIT_M,
            "nota_minima": FACE_LENGTH_SCORE_FLOOR,
            "metodo": "interpolacao linear sobre o maior lado do retangulo minimo rotacionado",
        },
        warnings=(*warnings, *compliance_warnings),
    )


def calculate_quadra_face_length_score_from_context(
    context: GeospatialContext,
) -> IndicatorCalculation:
    """BT-053/054: `IndicatorDefinition.calculator` for `quadras.face_length_score`."""
    quadras, quadra_warnings = quadras_from_context(context)
    return calculate_quadra_face_length_score(
        quadras, metric_crs=context.metric_crs_value(), warnings=quadra_warnings
    )


def _min_rotated_rectangle_orientation_deg(geometry: BaseGeometry) -> float:
    """Deviation, in degrees, of the minimum rotated rectangle's longer
    edge (the same "comprimento" `_min_rotated_rectangle_dimensions`
    reports) from the geographic East-West axis. 0 = perfectly aligned
    with East-West, 90 = perpendicular (aligned with North-South instead).

    A line has no inherent direction, so the raw azimuth (which ranges
    -180..180 depending on which end of the edge is read first) is folded
    twice: once mod 180 to collapse the two opposite directions of the
    same line onto one value, then again onto the shorter arc to 90 to
    express "how far from the East-West line" rather than "how far from
    East specifically" - a rectangle whose edge sits at 170 degrees from
    east is really just 10 degrees off from lying along the west
    direction of that same line.

    For a near-square quadra the two edges are nearly the same length, so
    which one gets picked as "the longer edge" (and therefore which
    orientation gets reported) is unstable - a documented approximation
    (same spirit as `_face_length_score`'s face-length proxy), not a data
    problem worth a runtime warning.

    Treats the metric CRS's grid axes as true East-West/North-South (no
    correction for grid convergence) - negligible at the scale of a single
    loteamento, and consistent with the rest of the engine not correcting
    for it either.
    """
    rectangle = geometry.minimum_rotated_rectangle
    corners = list(rectangle.exterior.coords)
    edge_a = (corners[1][0] - corners[0][0], corners[1][1] - corners[0][1])
    edge_b = (corners[2][0] - corners[1][0], corners[2][1] - corners[1][1])
    edge_a_length = math.dist(corners[0], corners[1])
    edge_b_length = math.dist(corners[1], corners[2])
    major_axis = edge_a if edge_a_length >= edge_b_length else edge_b
    angle_deg = math.degrees(math.atan2(major_axis[1], major_axis[0])) % 180.0
    return min(angle_deg, 180.0 - angle_deg)


def calculate_quadra_orientation(
    quadras: Sequence[QuadraGeometry],
    *,
    metric_crs: str | int,
    warnings: tuple[AnalysisWarning, ...] = (),
) -> IndicatorCalculation:
    """CTE/Methafora + LEED-ND "Conforto termico": desvio, em graus, do
    eixo maior de cada quadra em relacao ao eixo Leste-Oeste geografico (0
    = alinhado, 90 = perpendicular). Reaproveita o mesmo retangulo minimo
    rotacionado de `quadras.min_rotated_rectangle`
    (`_min_rotated_rectangle_orientation_deg`), sem alterar o contrato
    daquele indicador ja registrado - mesmo padrao de reuso independente
    que `calculate_quadra_face_length_score` ja usa para "comprimento".

    Guarda o angulo bruto, nao um sim/nao ja comparado contra um limiar: a
    certificacao pede 75% das quadras a ate 15 graus, mas esse corte e uma
    leitura de relatorio sobre o angulo, nao parte da formula - mesmo
    espirito de guardar o valor bruto e deixar a interpretacao para a
    apresentacao (nota Obsidian 88/90), assim o mesmo numero serve mesmo
    se outra certificacao pedir um limiar diferente.
    """
    orientation = {
        quadra.quadra_id: _min_rotated_rectangle_orientation_deg(quadra.geometry)
        for quadra in quadras
    }
    return IndicatorCalculation(
        indicator_code="quadras.orientation",
        theme="quadras",
        formula_version="1.0.0",
        raw_value=orientation,
        unit="graus",
        metric_crs=str(metric_crs),
        source_layers=(TERRITORIO_LAYER,),
        contributing_feature_ids=_quadra_contributing_ids(quadras),
        parameters={
            "metric_crs": str(metric_crs),
            "metodo": (
                "desvio do eixo maior do retangulo minimo rotacionado em "
                "relacao ao eixo Leste-Oeste, dobrado para a faixa 0-90"
            ),
            "referencia": (
                "CTE/Methafora e LEED-ND: 75% das quadras a ate 15 graus do eixo Leste-Oeste"
            ),
        },
        warnings=warnings,
    )


def calculate_quadra_orientation_from_context(
    context: GeospatialContext,
) -> IndicatorCalculation:
    """`IndicatorDefinition.calculator` for `quadras.orientation`."""
    quadras, quadra_warnings = quadras_from_context(context)
    return calculate_quadra_orientation(
        quadras, metric_crs=context.metric_crs_value(), warnings=quadra_warnings
    )
