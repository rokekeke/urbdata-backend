from collections.abc import Callable
from dataclasses import dataclass

from app.domain.analysis.result import IndicatorCalculation

IndicatorCalculator = Callable[..., IndicatorCalculation]


@dataclass(frozen=True, slots=True)
class IndicatorDefinition:
    code: str
    theme: str
    formula_version: str
    unit: str
    required_layers: tuple[str, ...]
    optional_layers: tuple[str, ...]
    dependencies: tuple[str, ...]
    calculator: IndicatorCalculator
