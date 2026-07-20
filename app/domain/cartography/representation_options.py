"""Representation metadata for the Documentacao editor (DOC-BE-004).

Pure domain logic: given aggregate stats of one field (computed in SQL by
the repository - never by scanning features in Python), decide the
detected type and the recommended cartographic mode. The recommendation
is a suggestion only - the authoritative check happens when the document
is validated (ADR 014); this module never applies anything silently.
"""

from dataclasses import dataclass
from enum import StrEnum

from app.domain.analysis.presentation import PRESENTATIONS, FeatureKey, IndicatorGranularity
from app.domain.cartography.document import (
    CATEGORICAL_CLASS_BLOCK_LIMIT,
    RepresentationMode,
)


class FieldOrigin(StrEnum):
    SOURCE = "source"
    MAPPED = "mapped"


class DetectedType(StrEnum):
    NUMERIC = "numeric"
    TEXT = "text"
    BOOLEAN = "boolean"
    EMPTY = "empty"
    MIXED = "mixed"


@dataclass(frozen=True, slots=True)
class FieldStats:
    """Aggregates for one field, straight from the SQL query."""

    field: str
    origin: FieldOrigin
    present_count: int
    empty_count: int
    cardinality: int
    numeric_count: int
    min_value: float | None
    max_value: float | None
    distinct_values: tuple[str, ...] | None
    boolean: bool = False


@dataclass(frozen=True, slots=True)
class FieldRecommendation:
    detected_type: DetectedType
    recommended_mode: RepresentationMode | None
    unsuitable_reason: str | None


def recommend_mode(stats: FieldStats) -> FieldRecommendation:
    filled = stats.present_count - stats.empty_count
    if filled <= 0:
        return FieldRecommendation(DetectedType.EMPTY, None, "field_empty")
    if stats.boolean:
        return FieldRecommendation(DetectedType.BOOLEAN, RepresentationMode.CATEGORICAL, None)
    if stats.numeric_count == filled:
        if stats.cardinality == 1:
            # A numeric constant has nothing to grade - still paintable as
            # a single style, honestly reported.
            return FieldRecommendation(DetectedType.NUMERIC, RepresentationMode.SINGLE, None)
        return FieldRecommendation(DetectedType.NUMERIC, RepresentationMode.SEQUENTIAL, None)
    if stats.numeric_count > 0:
        return FieldRecommendation(DetectedType.MIXED, None, "mixed_types")
    if stats.cardinality > CATEGORICAL_CLASS_BLOCK_LIMIT:
        return FieldRecommendation(
            DetectedType.TEXT, None, "categorical_cardinality_exceeded"
        )
    return FieldRecommendation(DetectedType.TEXT, RepresentationMode.CATEGORICAL, None)


# Which layer a per-feature indicator's dict keys join onto (ADR 014):
# feature UUIDs join the territorio layer's own features; quadra_id keys
# join the derived quadras layer (each feature carries `quadra_id`).
_LAYER_TYPES_BY_FEATURE_KEY: dict[FeatureKey, frozenset[str]] = {
    FeatureKey.FEATURE_ID: frozenset({"territorio"}),
    FeatureKey.QUADRA_ID: frozenset({"quadras"}),
}


def compatible_indicator_codes(layer_type: str) -> tuple[str, ...]:
    """Per-feature indicators whose values can style this layer type."""
    codes = [
        code
        for code, presentation in PRESENTATIONS.items()
        if presentation.granularity is IndicatorGranularity.POR_FEICAO
        and presentation.feature_key is not None
        and layer_type in _LAYER_TYPES_BY_FEATURE_KEY[presentation.feature_key]
    ]
    return tuple(sorted(codes))
