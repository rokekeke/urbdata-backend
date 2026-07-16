import pytest

from app.domain.analysis.definitions import IndicatorDefinition
from app.domain.analysis.exceptions import IndicatorDependencyError
from app.domain.analysis.registry import IndicatorRegistry
from app.domain.analysis.result import IndicatorCalculation


def _calculator() -> IndicatorCalculation:
    return IndicatorCalculation(
        indicator_code="test.value",
        theme="test",
        formula_version="1.0.0",
        raw_value=1.0,
        unit="count",
    )


def test_registry_rejects_duplicate_codes() -> None:
    registry = IndicatorRegistry()
    definition = IndicatorDefinition(
        "test.value", "test", "1.0.0", "count", (), (), (), _calculator
    )
    registry.register(definition)

    with pytest.raises(IndicatorDependencyError):
        registry.register(definition)
