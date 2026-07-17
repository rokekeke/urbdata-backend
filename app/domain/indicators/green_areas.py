"""Green-area indicators. Thresholds remain pending domain approval."""

from collections.abc import Sequence
from dataclasses import dataclass
from uuid import UUID

from app.domain.analysis.exceptions import IndicatorCalculationError
from app.domain.analysis.result import IndicatorCalculation

# Placeholder pending the macroarea upload/layer design (Obsidian note 11),
# same as app.domain.indicators.land_use.LOTE_LAYER.
GREEN_AREA_LAYER = "avl"


@dataclass(frozen=True, slots=True)
class GreenAreaRecord:
    feature_id: UUID
    area_m2: float


def calculate_total_green_area(
    records: Sequence[GreenAreaRecord], *, metric_crs: str | int
) -> IndicatorCalculation:
    """BT-120: raw sum of AVL (Área Verde de Lazer) area in m2.

    Whether APP (permanent-preservation area) should also count toward
    "green area" is an open domain question (Obsidian note 14) - for now
    this only sums AVL, the unambiguous reading of "área verde de lazer".
    An empty *records* is a legitimate zero, not an error.
    """
    total = sum(record.area_m2 for record in records)
    return IndicatorCalculation(
        indicator_code="green_areas.total_area",
        theme="green_areas",
        formula_version="1.0.0",
        raw_value=total,
        unit="m2",
        metric_crs=str(metric_crs),
        source_layers=(GREEN_AREA_LAYER,),
        contributing_feature_ids=tuple(record.feature_id for record in records),
        parameters={"metric_crs": str(metric_crs), "includes": ["avl"]},
    )


def calculate_green_area_percent(
    records: Sequence[GreenAreaRecord],
    *,
    total_project_area_m2: float,
    metric_crs: str | int,
) -> IndicatorCalculation:
    """BT-121: AVL area as a percentage of the gross project area
    (`territorial.total_area`, passed in rather than recomputed here).

    Matches how the UN-Habitat 15-25% benchmark is itself framed ("da area
    total do projeto") - deliberately a different denominator convention
    than land_use's percent-of-classified-lot-area (domain choice,
    2026-07-17, registered per project convention rather than left
    implicit).
    """
    if total_project_area_m2 <= 0:
        raise IndicatorCalculationError(
            "A positive total project area is required to compute the green-area percentage."
        )
    total_green = sum(record.area_m2 for record in records)
    return IndicatorCalculation(
        indicator_code="green_areas.percent_of_project",
        theme="green_areas",
        formula_version="1.0.0",
        raw_value=total_green / total_project_area_m2,
        unit="ratio",
        metric_crs=str(metric_crs),
        source_layers=(GREEN_AREA_LAYER,),
        contributing_feature_ids=tuple(record.feature_id for record in records),
        parameters={
            "metric_crs": str(metric_crs),
            "denominator": "territorial.total_area",
            "includes": ["avl"],
        },
    )
