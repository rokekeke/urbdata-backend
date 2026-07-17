import math
from collections.abc import Sequence
from dataclasses import dataclass
from uuid import UUID

from shapely.geometry.base import BaseGeometry

from app.config.macroarea_mapping import Macroarea
from app.domain.analysis.exceptions import IndicatorCalculationError
from app.domain.analysis.result import IndicatorCalculation
from app.domain.analysis.warnings import AnalysisWarning, WarningSeverity
from app.domain.geospatial.context import GeospatialContext
from app.domain.geospatial.geometry import area_m2, dissolve, length_m, resolve_feature_area

PERIMETER_LAYER = "perimetro"
TERRITORIO_LAYER = "territorio"


def _dissolve_perimeter(
    context: GeospatialContext,
) -> tuple[BaseGeometry, tuple[UUID, ...], tuple[AnalysisWarning, ...]]:
    """Shared first step for every territorial indicator: consolidate the
    perimeter layer once and report which features were skipped.
    """
    gdf = context.metric_gdf(PERIMETER_LAYER)
    geometry, contributing_ids, skipped_ids = dissolve(gdf)
    warnings = (
        (
            AnalysisWarning(
                code="perimeter_feature_skipped",
                message=(
                    "Uma ou mais feicoes do perimetro estavam vazias ou invalidas "
                    "e foram ignoradas na consolidacao."
                ),
                feature_ids=skipped_ids,
                severity=WarningSeverity.WARNING,
            ),
        )
        if skipped_ids
        else ()
    )
    return geometry, contributing_ids, warnings


def calculate_total_area(
    geometry: BaseGeometry,
    *,
    metric_crs: str | int,
    contributing_feature_ids: tuple[UUID, ...] = (),
    warnings: tuple[AnalysisWarning, ...] = (),
) -> IndicatorCalculation:
    return IndicatorCalculation(
        indicator_code="territorial.total_area",
        theme="territorial",
        formula_version="1.0.0",
        raw_value=area_m2(geometry, crs=metric_crs),
        unit="m2",
        metric_crs=str(metric_crs),
        source_layers=(PERIMETER_LAYER,),
        contributing_feature_ids=contributing_feature_ids,
        parameters={"metric_crs": str(metric_crs)},
        warnings=warnings,
    )


def calculate_total_area_from_context(context: GeospatialContext) -> IndicatorCalculation:
    """Consolidate the perimeter layer and calculate its total area.

    This is the `IndicatorDefinition.calculator` registered for
    `territorial.total_area` (see app/domain/indicators/catalog.py): the
    orchestrator calls it with nothing but the shared `GeospatialContext`.
    """
    geometry, contributing_ids, warnings = _dissolve_perimeter(context)
    return calculate_total_area(
        geometry,
        metric_crs=context.metric_crs_value(),
        contributing_feature_ids=contributing_ids,
        warnings=warnings,
    )


def calculate_perimeter(
    geometry: BaseGeometry,
    *,
    metric_crs: str | int,
    contributing_feature_ids: tuple[UUID, ...] = (),
    warnings: tuple[AnalysisWarning, ...] = (),
) -> IndicatorCalculation:
    return IndicatorCalculation(
        indicator_code="territorial.perimeter",
        theme="territorial",
        formula_version="1.0.0",
        # A (Multi)Polygon's `.length` is the sum of its ring lengths, i.e.
        # exactly the boundary/perimeter length - no separate boundary
        # extraction is needed.
        raw_value=length_m(geometry, crs=metric_crs),
        unit="m",
        metric_crs=str(metric_crs),
        source_layers=(PERIMETER_LAYER,),
        contributing_feature_ids=contributing_feature_ids,
        parameters={"metric_crs": str(metric_crs)},
        warnings=warnings,
    )


def calculate_perimeter_from_context(context: GeospatialContext) -> IndicatorCalculation:
    """BT-041: `IndicatorDefinition.calculator` for `territorial.perimeter`."""
    geometry, contributing_ids, warnings = _dissolve_perimeter(context)
    return calculate_perimeter(
        geometry,
        metric_crs=context.metric_crs_value(),
        contributing_feature_ids=contributing_ids,
        warnings=warnings,
    )


def calculate_compactness(
    geometry: BaseGeometry,
    *,
    metric_crs: str | int,
    contributing_feature_ids: tuple[UUID, ...] = (),
    warnings: tuple[AnalysisWarning, ...] = (),
) -> IndicatorCalculation:
    """Polsby-Popper isoperimetric quotient: `4 * pi * area / perimeter^2`.

    A perfect circle scores 1.0 (maximum compactness); more elongated or
    irregular perimeters approach 0. Standard, unambiguous formula - no
    domain sign-off needed on the math itself.
    """
    area = area_m2(geometry, crs=metric_crs)
    perimeter = length_m(geometry, crs=metric_crs)
    compactness = (4 * math.pi * area) / (perimeter**2)
    return IndicatorCalculation(
        indicator_code="territorial.compactness",
        theme="territorial",
        formula_version="1.0.0",
        raw_value=compactness,
        unit="adimensional",
        metric_crs=str(metric_crs),
        source_layers=(PERIMETER_LAYER,),
        contributing_feature_ids=contributing_feature_ids,
        parameters={"metric_crs": str(metric_crs), "formula": "4*pi*area/perimeter^2"},
        warnings=warnings,
    )


def calculate_compactness_from_context(context: GeospatialContext) -> IndicatorCalculation:
    """BT-042: `IndicatorDefinition.calculator` for `territorial.compactness`."""
    geometry, contributing_ids, warnings = _dissolve_perimeter(context)
    return calculate_compactness(
        geometry,
        metric_crs=context.metric_crs_value(),
        contributing_feature_ids=contributing_ids,
        warnings=warnings,
    )


@dataclass(frozen=True, slots=True)
class TerritorialAreaRecord:
    feature_id: UUID
    area_m2: float
    macroarea: str | None
    parcelavel: bool | None


def _macroarea_category(raw: str | None) -> Macroarea:
    """`macroarea` is already normalized to a valid `Macroarea.value` when
    stored (`FeatureRepository.apply_attribute_mapping`), so this only
    needs to parse it back - or fall back to NULO for a feature that was
    never classified at all, same bucket as an explicit "Nulo" tag."""
    return Macroarea(raw) if raw is not None else Macroarea.NULO


def _area_by_macroarea(
    records: Sequence[TerritorialAreaRecord],
) -> dict[Macroarea, tuple[float, tuple[UUID, ...]]]:
    """Every record counted once, grouped by macroarea category. Unlike
    land_use/green_areas, unclassified features are not excluded - they
    get their own `nulo` bucket, since knowing how much of the matricula
    remains unclassified is itself useful (domain choice, 2026-07-17)."""
    areas: dict[Macroarea, float] = {}
    ids: dict[Macroarea, list[UUID]] = {}
    for record in records:
        category = _macroarea_category(record.macroarea)
        areas[category] = areas.get(category, 0.0) + record.area_m2
        ids.setdefault(category, []).append(record.feature_id)
    return {category: (area, tuple(ids[category])) for category, area in areas.items()}


def _territorial_contributing_ids(
    breakdown: dict[Macroarea, tuple[float, tuple[UUID, ...]]],
) -> tuple[UUID, ...]:
    return tuple(feature_id for _, ids in breakdown.values() for feature_id in ids)


def _territorial_records_from_context(
    context: GeospatialContext,
) -> tuple[tuple[TerritorialAreaRecord, ...], tuple[AnalysisWarning, ...]]:
    """Every feature of the TERRITORIO layer (no macroarea filter - BT-043
    reports the complete inventory), with area resolved per feature
    (geometric vs. reference_area_m2 - ADR 008 / Obsidian note 11)."""
    gdf = context.metric_gdf(TERRITORIO_LAYER)
    metric_crs = context.metric_crs_value()
    records: list[TerritorialAreaRecord] = []
    area_warnings: list[AnalysisWarning] = []
    for row in gdf.itertuples():
        resolved = resolve_feature_area(
            row.feature_id, row.geometry, row.reference_area_m2, crs=metric_crs
        )
        if resolved.warning is not None:
            area_warnings.append(resolved.warning)
        records.append(
            TerritorialAreaRecord(
                feature_id=row.feature_id,
                area_m2=resolved.area_m2,
                macroarea=row.macroarea,
                parcelavel=row.parcelavel,
            )
        )
    return tuple(records), tuple(area_warnings)


def calculate_territorial_area_by_category(
    records: Sequence[TerritorialAreaRecord],
    *,
    metric_crs: str | int,
    warnings: tuple[AnalysisWarning, ...] = (),
) -> IndicatorCalculation:
    """BT-043: raw area in m2 per territorial macroarea category (Lote,
    Sistema viario, AVL, APP, ACI, and Nulo for whatever isn't classified
    yet) - the complete "quadro de areas" inventory, not filtered by
    Parcelavel. See `calculate_territorial_percent_by_category` for the
    Parcelavel-scoped percentage view (BT-044), which is deliberately a
    different lens on the same data."""
    breakdown = _area_by_macroarea(records)
    return IndicatorCalculation(
        indicator_code="territorial.area_by_category",
        theme="territorial",
        formula_version="1.0.0",
        raw_value={category.value: area for category, (area, _) in breakdown.items()},
        unit="m2",
        metric_crs=str(metric_crs),
        source_layers=(TERRITORIO_LAYER,),
        contributing_feature_ids=_territorial_contributing_ids(breakdown),
        parameters={"metric_crs": str(metric_crs)},
        warnings=warnings,
    )


def calculate_territorial_area_by_category_from_context(
    context: GeospatialContext,
) -> IndicatorCalculation:
    """BT-043: `IndicatorDefinition.calculator` for `territorial.area_by_category`."""
    records, area_warnings = _territorial_records_from_context(context)
    return calculate_territorial_area_by_category(
        records, metric_crs=context.metric_crs_value(), warnings=area_warnings
    )


def calculate_territorial_percent_by_category(
    records: Sequence[TerritorialAreaRecord],
    *,
    metric_crs: str | int,
    warnings: tuple[AnalysisWarning, ...] = (),
) -> IndicatorCalculation:
    """BT-044: percentage per category, restricted to the Parcelavel subset
    of *records* for both the numerator and the denominator (domain
    decision, 2026-07-17: "soma de toda a area classificada como
    Parcelavel"). A non-parcelavel category (typically Sistema viario, APP)
    contributes nothing here, so the percentages sum to ~100% of the
    buildable-land universe - "of my buildable land, what fraction is each
    category" - not 100% of the whole gleba (that reading is BT-043's raw
    area breakdown, or `green_areas.percent_of_project`'s gross-area
    convention, a deliberately different denominator for a different
    question)."""
    parcelavel_records = [record for record in records if record.parcelavel is True]
    breakdown = _area_by_macroarea(parcelavel_records)
    total = sum(area for area, _ in breakdown.values())
    if total <= 0:
        raise IndicatorCalculationError(
            "No area classified as parcelavel is available to compute territorial percentages."
        )
    return IndicatorCalculation(
        indicator_code="territorial.percent_by_category",
        theme="territorial",
        formula_version="1.0.0",
        raw_value={category.value: area / total for category, (area, _) in breakdown.items()},
        unit="ratio",
        metric_crs=str(metric_crs),
        source_layers=(TERRITORIO_LAYER,),
        contributing_feature_ids=_territorial_contributing_ids(breakdown),
        parameters={"metric_crs": str(metric_crs), "denominator": "parcelavel_area"},
        warnings=warnings,
    )


def calculate_territorial_percent_by_category_from_context(
    context: GeospatialContext,
) -> IndicatorCalculation:
    """BT-044: `IndicatorDefinition.calculator` for `territorial.percent_by_category`."""
    records, area_warnings = _territorial_records_from_context(context)
    return calculate_territorial_percent_by_category(
        records, metric_crs=context.metric_crs_value(), warnings=area_warnings
    )
