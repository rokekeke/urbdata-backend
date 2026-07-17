"""Central catalog of registered indicator definitions (ADR 002).

The orchestrator consults `build_registry()` and never imports a concrete
formula module directly; adding an indicator means registering it here.
"""

from functools import lru_cache

from app.domain.analysis.definitions import IndicatorDefinition
from app.domain.analysis.registry import IndicatorRegistry
from app.domain.indicators.territorial import (
    PERIMETER_LAYER,
    calculate_compactness_from_context,
    calculate_perimeter_from_context,
    calculate_total_area_from_context,
)

TOTAL_AREA = IndicatorDefinition(
    code="territorial.total_area",
    theme="territorial",
    formula_version="1.0.0",
    unit="m2",
    required_layers=(PERIMETER_LAYER,),
    optional_layers=(),
    dependencies=(),
    calculator=calculate_total_area_from_context,
)

PERIMETER = IndicatorDefinition(
    code="territorial.perimeter",
    theme="territorial",
    formula_version="1.0.0",
    unit="m",
    required_layers=(PERIMETER_LAYER,),
    optional_layers=(),
    dependencies=(),
    calculator=calculate_perimeter_from_context,
)

COMPACTNESS = IndicatorDefinition(
    code="territorial.compactness",
    theme="territorial",
    formula_version="1.0.0",
    unit="adimensional",
    required_layers=(PERIMETER_LAYER,),
    optional_layers=(),
    dependencies=(),
    calculator=calculate_compactness_from_context,
)

ALL_DEFINITIONS: tuple[IndicatorDefinition, ...] = (TOTAL_AREA, PERIMETER, COMPACTNESS)


@lru_cache
def build_registry() -> IndicatorRegistry:
    registry = IndicatorRegistry()
    for definition in ALL_DEFINITIONS:
        registry.register(definition)
    return registry
