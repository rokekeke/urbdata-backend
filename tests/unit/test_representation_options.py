"""Pure-logic tests for representation recommendations (DOC-BE-004)."""

from app.domain.cartography.document import RepresentationMode
from app.domain.cartography.representation_options import (
    DetectedType,
    FieldOrigin,
    FieldStats,
    compatible_indicator_codes,
    recommend_mode,
)


def _stats(**overrides: object) -> FieldStats:
    base: dict[str, object] = {
        "field": "campo",
        "origin": FieldOrigin.SOURCE,
        "present_count": 10,
        "empty_count": 0,
        "cardinality": 5,
        "numeric_count": 0,
        "min_value": None,
        "max_value": None,
        "distinct_values": None,
        "boolean": False,
    }
    base.update(overrides)
    return FieldStats(**base)  # type: ignore[arg-type]


class TestRecommendMode:
    def test_all_numeric_recommends_sequential(self) -> None:
        result = recommend_mode(_stats(numeric_count=10, cardinality=8))
        assert result.detected_type is DetectedType.NUMERIC
        assert result.recommended_mode is RepresentationMode.SEQUENTIAL

    def test_numeric_constant_recommends_single(self) -> None:
        result = recommend_mode(_stats(numeric_count=10, cardinality=1))
        assert result.recommended_mode is RepresentationMode.SINGLE

    def test_text_with_low_cardinality_recommends_categorical(self) -> None:
        result = recommend_mode(_stats(cardinality=6))
        assert result.detected_type is DetectedType.TEXT
        assert result.recommended_mode is RepresentationMode.CATEGORICAL

    def test_text_above_block_limit_is_unsuitable(self) -> None:
        result = recommend_mode(_stats(cardinality=40))
        assert result.recommended_mode is None
        assert result.unsuitable_reason == "categorical_cardinality_exceeded"

    def test_empty_field_is_unsuitable(self) -> None:
        result = recommend_mode(_stats(present_count=10, empty_count=10, cardinality=0))
        assert result.detected_type is DetectedType.EMPTY
        assert result.unsuitable_reason == "field_empty"

    def test_mixed_numeric_and_text_is_unsuitable(self) -> None:
        result = recommend_mode(_stats(numeric_count=4, cardinality=8))
        assert result.detected_type is DetectedType.MIXED
        assert result.unsuitable_reason == "mixed_types"

    def test_boolean_recommends_categorical(self) -> None:
        result = recommend_mode(_stats(boolean=True, cardinality=2))
        assert result.detected_type is DetectedType.BOOLEAN
        assert result.recommended_mode is RepresentationMode.CATEGORICAL


class TestCompatibleIndicators:
    def test_territorio_gets_feature_id_indicators(self) -> None:
        assert compatible_indicator_codes("territorio") == (
            "lots.distance_to_green_area",
            "lots.distance_to_non_residential_use",
            "lots.frontage_length",
        )

    def test_quadras_gets_quadra_id_indicators(self) -> None:
        codes = compatible_indicator_codes("quadras")
        assert "quadras.face_length_score" in codes
        assert "lots.parceling_efficiency" in codes
        assert "lots.frontage_length" not in codes

    def test_unrelated_layer_gets_nothing(self) -> None:
        assert compatible_indicator_codes("perimetro") == ()
