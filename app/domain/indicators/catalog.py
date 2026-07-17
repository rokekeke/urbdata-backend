"""Central catalog of registered indicator definitions (ADR 002).

The orchestrator consults `build_registry()` and never imports a concrete
formula module directly; adding an indicator means registering it here.
"""

from functools import lru_cache

from app.domain.analysis.definitions import IndicatorDefinition
from app.domain.analysis.registry import IndicatorRegistry
from app.domain.indicators.green_areas import (
    TERRITORIO_LAYER as GREEN_AREAS_TERRITORIO_LAYER,
)
from app.domain.indicators.green_areas import (
    calculate_green_area_percent_from_context,
    calculate_total_green_area_from_context,
)
from app.domain.indicators.land_use import (
    TERRITORIO_LAYER as LAND_USE_TERRITORIO_LAYER,
)
from app.domain.indicators.land_use import (
    calculate_area_by_category_from_context,
    calculate_diversity_shannon_from_context,
    calculate_percent_by_category_from_context,
    calculate_predominant_use_from_context,
)
from app.domain.indicators.quadras import (
    TERRITORIO_LAYER as QUADRAS_TERRITORIO_LAYER,
)
from app.domain.indicators.quadras import (
    calculate_quadra_compactness_from_context,
    calculate_quadra_face_length_score_from_context,
    calculate_quadra_min_rotated_rectangle_from_context,
    calculate_quadra_stats_from_context,
)
from app.domain.indicators.territorial import (
    PERIMETER_LAYER,
    TERRITORIO_LAYER,
    calculate_compactness_from_context,
    calculate_perimeter_from_context,
    calculate_territorial_area_by_category_from_context,
    calculate_territorial_percent_by_category_from_context,
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

TERRITORIAL_AREA_BY_CATEGORY = IndicatorDefinition(
    code="territorial.area_by_category",
    theme="territorial",
    formula_version="1.0.0",
    unit="m2",
    required_layers=(TERRITORIO_LAYER,),
    optional_layers=(),
    dependencies=(),
    calculator=calculate_territorial_area_by_category_from_context,
)

TERRITORIAL_PERCENT_BY_CATEGORY = IndicatorDefinition(
    code="territorial.percent_by_category",
    theme="territorial",
    formula_version="1.0.0",
    unit="ratio",
    required_layers=(TERRITORIO_LAYER,),
    optional_layers=(),
    dependencies=(),
    calculator=calculate_territorial_percent_by_category_from_context,
)

LAND_USE_AREA_BY_CATEGORY = IndicatorDefinition(
    code="land_use.area_by_category",
    theme="land_use",
    formula_version="1.0.0",
    unit="m2",
    required_layers=(LAND_USE_TERRITORIO_LAYER,),
    optional_layers=(),
    dependencies=(),
    calculator=calculate_area_by_category_from_context,
)

LAND_USE_PERCENT_BY_CATEGORY = IndicatorDefinition(
    code="land_use.percent_by_category",
    theme="land_use",
    formula_version="1.0.0",
    unit="ratio",
    required_layers=(LAND_USE_TERRITORIO_LAYER,),
    optional_layers=(),
    dependencies=(),
    calculator=calculate_percent_by_category_from_context,
)

LAND_USE_PREDOMINANT_USE = IndicatorDefinition(
    code="land_use.predominant_use",
    theme="land_use",
    formula_version="1.0.0",
    unit="categoria",
    required_layers=(LAND_USE_TERRITORIO_LAYER,),
    optional_layers=(),
    dependencies=(),
    calculator=calculate_predominant_use_from_context,
)

LAND_USE_DIVERSITY_SHANNON = IndicatorDefinition(
    code="land_use.diversity_shannon",
    theme="land_use",
    formula_version="1.0.0",
    unit="adimensional",
    required_layers=(LAND_USE_TERRITORIO_LAYER,),
    optional_layers=(),
    dependencies=(),
    calculator=calculate_diversity_shannon_from_context,
)

GREEN_AREAS_TOTAL_AREA = IndicatorDefinition(
    code="green_areas.total_area",
    theme="green_areas",
    formula_version="1.0.0",
    unit="m2",
    required_layers=(GREEN_AREAS_TERRITORIO_LAYER,),
    optional_layers=(),
    dependencies=(),
    calculator=calculate_total_green_area_from_context,
)

GREEN_AREAS_PERCENT_OF_PROJECT = IndicatorDefinition(
    code="green_areas.percent_of_project",
    theme="green_areas",
    formula_version="1.0.0",
    unit="ratio",
    # Needs both the macroarea layer (for AVL features) and the perimeter
    # (for the gross-project-area denominator, via territorial.total_area).
    required_layers=(GREEN_AREAS_TERRITORIO_LAYER, PERIMETER_LAYER),
    optional_layers=(),
    dependencies=(),
    calculator=calculate_green_area_percent_from_context,
)

QUADRAS_STATS = IndicatorDefinition(
    code="quadras.stats",
    theme="quadras",
    formula_version="1.0.0",
    unit="composto",
    required_layers=(QUADRAS_TERRITORIO_LAYER,),
    optional_layers=(),
    dependencies=(),
    calculator=calculate_quadra_stats_from_context,
)

QUADRAS_COMPACTNESS = IndicatorDefinition(
    code="quadras.compactness",
    theme="quadras",
    formula_version="1.0.0",
    unit="adimensional",
    required_layers=(QUADRAS_TERRITORIO_LAYER,),
    optional_layers=(),
    dependencies=(),
    calculator=calculate_quadra_compactness_from_context,
)

QUADRAS_MIN_ROTATED_RECTANGLE = IndicatorDefinition(
    code="quadras.min_rotated_rectangle",
    theme="quadras",
    formula_version="1.0.0",
    unit="composto",
    required_layers=(QUADRAS_TERRITORIO_LAYER,),
    optional_layers=(),
    dependencies=(),
    calculator=calculate_quadra_min_rotated_rectangle_from_context,
)

QUADRAS_FACE_LENGTH_SCORE = IndicatorDefinition(
    code="quadras.face_length_score",
    theme="quadras",
    formula_version="1.0.0",
    unit="adimensional",
    required_layers=(QUADRAS_TERRITORIO_LAYER,),
    optional_layers=(),
    dependencies=(),
    calculator=calculate_quadra_face_length_score_from_context,
)

ALL_DEFINITIONS: tuple[IndicatorDefinition, ...] = (
    TOTAL_AREA,
    PERIMETER,
    COMPACTNESS,
    TERRITORIAL_AREA_BY_CATEGORY,
    TERRITORIAL_PERCENT_BY_CATEGORY,
    LAND_USE_AREA_BY_CATEGORY,
    LAND_USE_PERCENT_BY_CATEGORY,
    LAND_USE_PREDOMINANT_USE,
    LAND_USE_DIVERSITY_SHANNON,
    GREEN_AREAS_TOTAL_AREA,
    GREEN_AREAS_PERCENT_OF_PROJECT,
    QUADRAS_STATS,
    QUADRAS_COMPACTNESS,
    QUADRAS_MIN_ROTATED_RECTANGLE,
    QUADRAS_FACE_LENGTH_SCORE,
)


@lru_cache
def build_registry() -> IndicatorRegistry:
    registry = IndicatorRegistry()
    for definition in ALL_DEFINITIONS:
        registry.register(definition)
    return registry
