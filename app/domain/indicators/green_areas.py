"""Green-area indicators.

Two readings coexist by parecer da revisao teorica (nota Obsidian 66/67,
22/07/2026): AVL only (the original, unambiguous "area verde de lazer") and
AVL+APP (showing the landscaping potential APP can add to a project). Both
are exposed as separate, additive indicator codes - neither replaces the
other.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from uuid import UUID

from app.config.macroarea_mapping import Macroarea
from app.domain.analysis.exceptions import IndicatorCalculationError
from app.domain.analysis.result import IndicatorCalculation
from app.domain.analysis.warnings import AnalysisWarning
from app.domain.geospatial.context import GeospatialContext
from app.domain.geospatial.geometry import resolve_feature_area
from app.domain.indicators.territorial import calculate_total_area_from_context

TERRITORIO_LAYER = "territorio"
GREEN_AREA_LAYER = Macroarea.AVL.value
GREEN_AREA_MACROAREAS = (Macroarea.AVL.value,)
GREEN_AREA_WITH_APP_MACROAREAS = (Macroarea.AVL.value, Macroarea.APP.value)


@dataclass(frozen=True, slots=True)
class GreenAreaRecord:
    feature_id: UUID
    area_m2: float


def _green_area_records_from_context(
    context: GeospatialContext, *, macroareas: Sequence[str]
) -> tuple[tuple[GreenAreaRecord, ...], tuple[AnalysisWarning, ...]]:
    """Filter the TERRITORIO layer down to features whose `macroarea` is in
    *macroareas* and resolve each one's area (geometric vs.
    reference_area_m2 - ADR 008 / note 11)."""
    gdf = context.metric_gdf(TERRITORIO_LAYER)
    metric_crs = context.metric_crs_value()
    macroarea_set = set(macroareas)
    records: list[GreenAreaRecord] = []
    area_warnings: list[AnalysisWarning] = []
    for row in gdf.itertuples():
        if row.macroarea not in macroarea_set:
            continue
        resolved = resolve_feature_area(
            row.feature_id, row.geometry, row.reference_area_m2, crs=metric_crs
        )
        if resolved.warning is not None:
            area_warnings.append(resolved.warning)
        records.append(GreenAreaRecord(feature_id=row.feature_id, area_m2=resolved.area_m2))
    return tuple(records), tuple(area_warnings)


def calculate_total_green_area(
    records: Sequence[GreenAreaRecord],
    *,
    metric_crs: str | int,
    indicator_code: str = "green_areas.total_area",
    includes: Sequence[str] = ("avl",),
    warnings: tuple[AnalysisWarning, ...] = (),
) -> IndicatorCalculation:
    """BT-120: raw sum of green area in m2, over whichever macroareas
    *records* was already filtered to (see *includes* for what's reflected
    in this specific result's metadata).

    An empty *records* is a legitimate zero, not an error.
    """
    total = sum(record.area_m2 for record in records)
    return IndicatorCalculation(
        indicator_code=indicator_code,
        theme="green_areas",
        formula_version="1.0.0",
        raw_value=total,
        unit="m2",
        metric_crs=str(metric_crs),
        source_layers=tuple(includes),
        contributing_feature_ids=tuple(record.feature_id for record in records),
        parameters={"metric_crs": str(metric_crs), "includes": list(includes)},
        warnings=warnings,
    )


def calculate_total_green_area_from_context(context: GeospatialContext) -> IndicatorCalculation:
    """BT-120: `IndicatorDefinition.calculator` for `green_areas.total_area`
    (AVL only)."""
    records, area_warnings = _green_area_records_from_context(
        context, macroareas=GREEN_AREA_MACROAREAS
    )
    return calculate_total_green_area(
        records, metric_crs=context.metric_crs_value(), warnings=area_warnings
    )


def calculate_total_green_area_with_app_from_context(
    context: GeospatialContext,
) -> IndicatorCalculation:
    """`IndicatorDefinition.calculator` for `green_areas.total_area_with_app`
    (AVL+APP) - parecer da revisao teorica, nota 66 (22/07/2026). Same
    formula as the AVL-only variant; only the macroarea filter changes."""
    records, area_warnings = _green_area_records_from_context(
        context, macroareas=GREEN_AREA_WITH_APP_MACROAREAS
    )
    return calculate_total_green_area(
        records,
        metric_crs=context.metric_crs_value(),
        indicator_code="green_areas.total_area_with_app",
        includes=("avl", "app"),
        warnings=area_warnings,
    )


def calculate_green_area_percent(
    records: Sequence[GreenAreaRecord],
    *,
    total_project_area_m2: float,
    metric_crs: str | int,
    indicator_code: str = "green_areas.percent_of_project",
    includes: Sequence[str] = ("avl",),
    warnings: tuple[AnalysisWarning, ...] = (),
) -> IndicatorCalculation:
    """BT-121: green area (over whichever macroareas *records* was already
    filtered to) as a percentage of the gross project area
    (`territorial.total_area`, passed in rather than recomputed here).

    Matches how the UN-Habitat 15-25% benchmark is itself framed ("da area
    total do projeto") - deliberately a different denominator convention
    than land_use's percent-of-classified-lot-area (domain choice,
    2026-07-17, registered per project convention rather than left
    implicit; confirmed as coexisting with the other denominator
    conventions in the parecer da revisao teorica, notas 58/63/67,
    22/07/2026).
    """
    if total_project_area_m2 <= 0:
        raise IndicatorCalculationError(
            "A positive total project area is required to compute the green-area percentage."
        )
    total_green = sum(record.area_m2 for record in records)
    return IndicatorCalculation(
        indicator_code=indicator_code,
        theme="green_areas",
        formula_version="1.0.0",
        raw_value=total_green / total_project_area_m2,
        unit="ratio",
        metric_crs=str(metric_crs),
        source_layers=tuple(includes),
        contributing_feature_ids=tuple(record.feature_id for record in records),
        parameters={
            "metric_crs": str(metric_crs),
            "denominator": "territorial.total_area",
            "includes": list(includes),
        },
        warnings=warnings,
    )


def calculate_green_area_percent_from_context(context: GeospatialContext) -> IndicatorCalculation:
    """BT-121: `IndicatorDefinition.calculator` for
    `green_areas.percent_of_project` (AVL only).

    Reuses `territorial.calculate_total_area_from_context` for the
    denominator rather than re-deriving it, the same way `compactness`
    recomputes from the dissolved perimeter instead of depending on a
    persisted sibling result (ADR 004 - indicators stay self-sufficient
    within one run; nothing here reads another indicator's stored value).
    """
    total_area_result = calculate_total_area_from_context(context)
    total_project_area_m2 = total_area_result.raw_value
    assert isinstance(total_project_area_m2, float)  # calculate_total_area's contract

    records, area_warnings = _green_area_records_from_context(
        context, macroareas=GREEN_AREA_MACROAREAS
    )
    return calculate_green_area_percent(
        records,
        total_project_area_m2=total_project_area_m2,
        metric_crs=context.metric_crs_value(),
        warnings=area_warnings + total_area_result.warnings,
    )


def calculate_green_area_percent_with_app_from_context(
    context: GeospatialContext,
) -> IndicatorCalculation:
    """`IndicatorDefinition.calculator` for
    `green_areas.percent_of_project_with_app` (AVL+APP) - parecer da
    revisao teorica, nota 67 (22/07/2026)."""
    total_area_result = calculate_total_area_from_context(context)
    total_project_area_m2 = total_area_result.raw_value
    assert isinstance(total_project_area_m2, float)  # calculate_total_area's contract

    records, area_warnings = _green_area_records_from_context(
        context, macroareas=GREEN_AREA_WITH_APP_MACROAREAS
    )
    return calculate_green_area_percent(
        records,
        total_project_area_m2=total_project_area_m2,
        metric_crs=context.metric_crs_value(),
        indicator_code="green_areas.percent_of_project_with_app",
        includes=("avl", "app"),
        warnings=area_warnings + total_area_result.warnings,
    )
