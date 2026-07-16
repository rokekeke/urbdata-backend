from dataclasses import dataclass, field
from typing import Any
from uuid import UUID

from app.domain.analysis.warnings import AnalysisWarning

IndicatorValue = float | int | str | dict[str, Any] | None


@dataclass(frozen=True, slots=True)
class IndicatorCalculation:
    indicator_code: str
    theme: str
    formula_version: str
    raw_value: IndicatorValue
    unit: str
    metric_crs: str | None = None
    source_layers: tuple[str, ...] = field(default_factory=tuple)
    contributing_feature_ids: tuple[UUID, ...] = field(default_factory=tuple)
    parameters: dict[str, Any] = field(default_factory=dict)
    warnings: tuple[AnalysisWarning, ...] = field(default_factory=tuple)
