import pytest

from app.application.analysis.dependency_resolver import resolve_dependencies
from app.domain.analysis.definitions import IndicatorDefinition
from app.domain.analysis.exceptions import IndicatorDependencyError
from app.domain.analysis.result import IndicatorCalculation


def _calculator() -> IndicatorCalculation:
    return IndicatorCalculation("unused", "test", "1.0.0", None, "count")


def _definition(code: str, dependencies: tuple[str, ...] = ()) -> IndicatorDefinition:
    return IndicatorDefinition(code, "test", "1.0.0", "count", (), (), dependencies, _calculator)


def test_dependencies_are_ordered_before_dependents() -> None:
    ordered = resolve_dependencies((_definition("b", ("a",)), _definition("a")))
    assert tuple(item.code for item in ordered) == ("a", "b")


def test_dependency_cycle_is_rejected() -> None:
    with pytest.raises(IndicatorDependencyError):
        resolve_dependencies((_definition("a", ("b",)), _definition("b", ("a",))))
