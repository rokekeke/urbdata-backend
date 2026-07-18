import math
from collections.abc import Sequence
from dataclasses import dataclass
from uuid import UUID

from app.config.land_use_mapping import (
    LAND_USE_ALIASES,
    LAND_USE_DELIMITER,
    LandUseCategory,
    normalize_land_use_key,
)
from app.config.macroarea_mapping import Macroarea
from app.domain.analysis.result import IndicatorCalculation
from app.domain.analysis.warnings import AnalysisWarning, WarningSeverity
from app.domain.geospatial.context import GeospatialContext
from app.domain.geospatial.geometry import resolve_feature_area

TERRITORIO_LAYER = "territorio"
LOTE_LAYER = Macroarea.LOTE.value


@dataclass(frozen=True, slots=True)
class LotAreaRecord:
    feature_id: UUID
    area_m2: float
    raw_land_use: str | None


def classify_land_use(raw_value: str | None) -> LandUseCategory | None:
    """Resolve a lot's raw land-use text to a canonical category.

    A lot listing more than one recognized use (values joined by
    `LAND_USE_DELIMITER`) is always `MISTO`, regardless of how the uses are
    distributed - domain decision, 2026-07-17. Unrecognized or empty values
    return `None` (the lot stays unclassified and is excluded downstream).
    """
    if raw_value is None:
        return None
    resolved = {
        LAND_USE_ALIASES[normalize_land_use_key(token)]
        for token in raw_value.split(LAND_USE_DELIMITER)
        if token.strip() and normalize_land_use_key(token) in LAND_USE_ALIASES
    }
    if not resolved:
        return None
    if len(resolved) > 1:
        return LandUseCategory.MISTO
    return next(iter(resolved))


def _area_by_category(
    lots: Sequence[LotAreaRecord],
) -> dict[LandUseCategory, tuple[float, tuple[UUID, ...]]]:
    areas: dict[LandUseCategory, float] = {}
    ids: dict[LandUseCategory, list[UUID]] = {}
    for lot in lots:
        category = classify_land_use(lot.raw_land_use)
        if category is None:
            continue
        areas[category] = areas.get(category, 0.0) + lot.area_m2
        ids.setdefault(category, []).append(lot.feature_id)
    return {category: (area, tuple(ids[category])) for category, area in areas.items()}


def _contributing_ids(
    breakdown: dict[LandUseCategory, tuple[float, tuple[UUID, ...]]],
) -> tuple[UUID, ...]:
    return tuple(feature_id for _, ids in breakdown.values() for feature_id in ids)


def _unclassified_warning(lots: Sequence[LotAreaRecord]) -> AnalysisWarning | None:
    """Per-feature INFO warning for lots whose land use didn't resolve to a
    category (ADR 013 degradation policy - same shape as `lot_without_quadra`
    and `lot_ca_missing`). `None` when every lot classified."""
    unclassified = tuple(
        lot.feature_id for lot in lots if classify_land_use(lot.raw_land_use) is None
    )
    if not unclassified:
        return None
    return AnalysisWarning(
        code="lot_without_land_use",
        message=(
            "Lotes sem uso do solo reconhecido ficam fora dos indicadores de uso do solo."
        ),
        feature_ids=unclassified,
        severity=WarningSeverity.INFO,
    )


def _with_unclassified(
    warnings: tuple[AnalysisWarning, ...], lots: Sequence[LotAreaRecord]
) -> tuple[AnalysisWarning, ...]:
    warning = _unclassified_warning(lots)
    return warnings if warning is None else (*warnings, warning)


def _lot_records_from_context(
    context: GeospatialContext,
) -> tuple[tuple[LotAreaRecord, ...], tuple[AnalysisWarning, ...]]:
    """Filter the TERRITORIO layer down to Lote features and resolve each
    one's area (geometric vs. reference_area_m2 - ADR 008 / note 11)."""
    gdf = context.metric_gdf(TERRITORIO_LAYER)
    metric_crs = context.metric_crs_value()
    records: list[LotAreaRecord] = []
    area_warnings: list[AnalysisWarning] = []
    for row in gdf.itertuples():
        if row.macroarea != LOTE_LAYER:
            continue
        resolved = resolve_feature_area(
            row.feature_id, row.geometry, row.reference_area_m2, crs=metric_crs
        )
        if resolved.warning is not None:
            area_warnings.append(resolved.warning)
        records.append(
            LotAreaRecord(
                feature_id=row.feature_id, area_m2=resolved.area_m2, raw_land_use=row.land_use
            )
        )
    return tuple(records), tuple(area_warnings)


def calculate_area_by_category(
    lots: Sequence[LotAreaRecord],
    *,
    metric_crs: str | int,
    warnings: tuple[AnalysisWarning, ...] = (),
) -> IndicatorCalculation:
    """BT-062: raw area in m2 per land-use category, summed over lots
    (unclassified lots excluded, domain decision, 2026-07-17)."""
    breakdown = _area_by_category(lots)
    return IndicatorCalculation(
        indicator_code="land_use.area_by_category",
        theme="land_use",
        formula_version="1.0.0",
        raw_value={category.value: area for category, (area, _) in breakdown.items()},
        unit="m2",
        metric_crs=str(metric_crs),
        source_layers=(LOTE_LAYER,),
        contributing_feature_ids=_contributing_ids(breakdown),
        parameters={"metric_crs": str(metric_crs)},
        warnings=_with_unclassified(warnings, lots),
    )


def calculate_area_by_category_from_context(context: GeospatialContext) -> IndicatorCalculation:
    """BT-062: `IndicatorDefinition.calculator` for `land_use.area_by_category`."""
    lots, area_warnings = _lot_records_from_context(context)
    return calculate_area_by_category(
        lots, metric_crs=context.metric_crs_value(), warnings=area_warnings
    )


def calculate_percent_by_category(
    lots: Sequence[LotAreaRecord],
    *,
    metric_crs: str | int,
    warnings: tuple[AnalysisWarning, ...] = (),
) -> IndicatorCalculation:
    """BT-063: percentage per category over the sum of classified lot area
    only (domain decision, 2026-07-17 - other macroareas don't apply).

    Zero classified lot area is an empty qualifying universe, not a
    structural failure: the result degrades to an empty breakdown with the
    per-lot warning instead of failing the run (ADR 013)."""
    breakdown = _area_by_category(lots)
    total = sum(area for area, _ in breakdown.values())
    raw_value: dict[str, object] = (
        {}
        if total <= 0
        else {category.value: area / total for category, (area, _) in breakdown.items()}
    )
    return IndicatorCalculation(
        indicator_code="land_use.percent_by_category",
        theme="land_use",
        formula_version="1.0.1",
        raw_value=raw_value,
        unit="ratio",
        metric_crs=str(metric_crs),
        source_layers=(LOTE_LAYER,),
        contributing_feature_ids=_contributing_ids(breakdown),
        parameters={"metric_crs": str(metric_crs), "denominator": "classified_lot_area"},
        warnings=_with_unclassified(warnings, lots),
    )


def calculate_percent_by_category_from_context(context: GeospatialContext) -> IndicatorCalculation:
    """BT-063: `IndicatorDefinition.calculator` for `land_use.percent_by_category`."""
    lots, area_warnings = _lot_records_from_context(context)
    return calculate_percent_by_category(
        lots, metric_crs=context.metric_crs_value(), warnings=area_warnings
    )


def calculate_predominant_use(
    lots: Sequence[LotAreaRecord],
    *,
    metric_crs: str | int,
    warnings: tuple[AnalysisWarning, ...] = (),
) -> IndicatorCalculation:
    """BT-064: the category with the most classified area. An exact tie is
    reported as `None` with an info warning rather than an arbitrary pick -
    the per-lot Misto rule resolves lot-level ties, but a project-level tie
    across categories is a distinct, honestly-reportable outcome.

    An empty breakdown (no lot classified) degrades to `None` with the
    per-lot warning instead of failing the run (ADR 013)."""
    breakdown = _area_by_category(lots)
    all_warnings = _with_unclassified(warnings, lots)
    if not breakdown:
        return IndicatorCalculation(
            indicator_code="land_use.predominant_use",
            theme="land_use",
            formula_version="1.0.1",
            raw_value=None,
            unit="categoria",
            metric_crs=str(metric_crs),
            source_layers=(LOTE_LAYER,),
            contributing_feature_ids=(),
            parameters={"metric_crs": str(metric_crs)},
            warnings=all_warnings,
        )
    max_area = max(area for area, _ in breakdown.values())
    leaders = sorted(category for category, (area, _) in breakdown.items() if area == max_area)
    value: str | None = leaders[0].value
    if len(leaders) > 1:
        value = None
        all_warnings = (
            *all_warnings,
            AnalysisWarning(
                code="predominant_use_tie",
                message=(
                    "Duas ou mais categorias de uso do solo empataram em area; "
                    "nenhuma foi escolhida como predominante."
                ),
                severity=WarningSeverity.INFO,
            ),
        )
    return IndicatorCalculation(
        indicator_code="land_use.predominant_use",
        theme="land_use",
        formula_version="1.0.1",
        raw_value=value,
        unit="categoria",
        metric_crs=str(metric_crs),
        source_layers=(LOTE_LAYER,),
        contributing_feature_ids=_contributing_ids(breakdown),
        parameters={"metric_crs": str(metric_crs)},
        warnings=all_warnings,
    )


def calculate_predominant_use_from_context(context: GeospatialContext) -> IndicatorCalculation:
    """BT-064: `IndicatorDefinition.calculator` for `land_use.predominant_use`."""
    lots, area_warnings = _lot_records_from_context(context)
    return calculate_predominant_use(
        lots, metric_crs=context.metric_crs_value(), warnings=area_warnings
    )


def calculate_diversity_shannon(
    lots: Sequence[LotAreaRecord],
    *,
    metric_crs: str | int,
    warnings: tuple[AnalysisWarning, ...] = (),
) -> IndicatorCalculation:
    """BT-065/066: Shannon-Wiener diversity index over area proportions
    (not lot count) - the standard basis in land-use-mix literature, since
    it weighs a large lot the same as its actual spatial/functional share
    rather than as "one unit" (domain choice, 2026-07-17, registered per
    instruction rather than left implicit).

    Zero classified lot area degrades to `None` with the per-lot warning
    instead of failing the run (ADR 013)."""
    breakdown = _area_by_category(lots)
    total = sum(area for area, _ in breakdown.values())
    shannon: float | None = None
    if total > 0:
        shannon = -sum(
            (area / total) * math.log(area / total) for area, _ in breakdown.values() if area > 0
        )
    return IndicatorCalculation(
        indicator_code="land_use.diversity_shannon",
        theme="land_use",
        formula_version="1.0.1",
        raw_value=shannon,
        unit="adimensional",
        metric_crs=str(metric_crs),
        source_layers=(LOTE_LAYER,),
        contributing_feature_ids=_contributing_ids(breakdown),
        parameters={
            "metric_crs": str(metric_crs),
            "formula": "-sum(pi*ln(pi))",
            "base": "area",
        },
        warnings=_with_unclassified(warnings, lots),
    )


def calculate_diversity_shannon_from_context(context: GeospatialContext) -> IndicatorCalculation:
    """BT-065/066: `IndicatorDefinition.calculator` for `land_use.diversity_shannon`."""
    lots, area_warnings = _lot_records_from_context(context)
    return calculate_diversity_shannon(
        lots, metric_crs=context.metric_crs_value(), warnings=area_warnings
    )
