"""Join geometry features to CSV attribute rows by key (nota 53/54, b3).

The happy-path shape mirrors the real sample evaluated in nota 53: 102
geometries, 102 CSV rows, 102 matches, joined on `Name`.
"""

from typing import Any

import pytest

from app.domain.layer_join import (
    AttributeJoinError,
    join_geometry_and_attributes,
    resolve_geometry_join_keys,
)


class TestResolveGeometryJoinKeys:
    """b6.2: resolves each feature's key in feature order, before b3 ever
    sees the values."""

    def test_defaults_to_feature_id_when_no_property_key_given(self) -> None:
        features = [{"id": "L01", "properties": {}}, {"id": "L02", "properties": {}}]
        assert resolve_geometry_join_keys(features, None) == ["L01", "L02"]

    def test_uses_the_named_property_when_given(self) -> None:
        features = [
            {"id": "ignored-1", "properties": {"URBDATA_ID": "A1"}},
            {"id": "ignored-2", "properties": {"URBDATA_ID": "A2"}},
        ]
        assert resolve_geometry_join_keys(features, "URBDATA_ID") == ["A1", "A2"]

    def test_missing_feature_id_resolves_to_none_not_a_guess(self) -> None:
        features: list[dict[str, Any]] = [{"properties": {}}, {"id": None, "properties": {}}]
        assert resolve_geometry_join_keys(features, None) == [None, None]

    def test_missing_named_property_resolves_to_none(self) -> None:
        features = [{"id": "L01", "properties": {"Other": "x"}}]
        assert resolve_geometry_join_keys(features, "URBDATA_ID") == [None]

    def test_feature_with_no_properties_dict_resolves_to_none(self) -> None:
        features = [{"id": "L01"}]
        assert resolve_geometry_join_keys(features, "URBDATA_ID") == [None]

    def test_numeric_feature_id_is_stringified_for_comparison_with_csv_values(self) -> None:
        """The CSV side is always strings (parse_csv) - a JSON number id
        must still be comparable to it, that's not the approximation rule 6
        forbids."""
        features = [{"id": 42, "properties": {}}]
        assert resolve_geometry_join_keys(features, None) == ["42"]


def test_matches_every_feature_to_its_row_by_key_not_position() -> None:
    geometry_keys = ["L02", "L01"]
    attribute_rows = [{"Name": "L01", "Area": "100"}, {"Name": "L02", "Area": "200"}]

    result = join_geometry_and_attributes(geometry_keys, attribute_rows, "Name")

    assert [pair.geometry_index for pair in result.matched] == [0, 1]
    assert result.matched[0].attribute_row == {"Name": "L02", "Area": "200"}
    assert result.matched[1].attribute_row == {"Name": "L01", "Area": "100"}
    assert result.summary.to_dict() == {
        "geometry_count": 2,
        "attribute_count": 2,
        "matched": 2,
        "missing_geometry_keys": [],
        "missing_attribute_keys": [],
        "duplicate_geometry_keys": [],
        "duplicate_attribute_keys": [],
    }


def test_rejects_empty_key_on_geometry_side() -> None:
    with pytest.raises(AttributeJoinError) as exc_info:
        join_geometry_and_attributes(
            ["L01", None, ""],
            [{"Name": "L01"}, {"Name": "L02"}, {"Name": "L03"}],
            "Name",
        )
    assert exc_info.value.context["empty_geometry_feature_indices"] == [1, 2]


def test_rejects_empty_key_on_attribute_side() -> None:
    with pytest.raises(AttributeJoinError) as exc_info:
        join_geometry_and_attributes(
            ["L01", "L02"],
            [{"Name": "L01"}, {"Name": ""}],
            "Name",
        )
    assert exc_info.value.context["empty_attribute_row_indices"] == [1]


def test_rejects_duplicate_key_on_geometry_side() -> None:
    with pytest.raises(AttributeJoinError) as exc_info:
        join_geometry_and_attributes(
            ["L01", "L01"],
            [{"Name": "L01"}],
            "Name",
        )
    assert exc_info.value.context["duplicate_geometry_keys"] == ["L01"]


def test_rejects_duplicate_key_on_attribute_side() -> None:
    with pytest.raises(AttributeJoinError) as exc_info:
        join_geometry_and_attributes(
            ["L01"],
            [{"Name": "L01"}, {"Name": "L01"}],
            "Name",
        )
    assert exc_info.value.context["duplicate_attribute_keys"] == ["L01"]


def test_rejects_geometry_feature_with_no_matching_csv_row() -> None:
    with pytest.raises(AttributeJoinError) as exc_info:
        join_geometry_and_attributes(
            ["L01", "L02"],
            [{"Name": "L01"}],
            "Name",
        )
    assert exc_info.value.context["missing_attribute_keys"] == ["L02"]


def test_rejects_csv_row_with_no_matching_geometry_feature() -> None:
    with pytest.raises(AttributeJoinError) as exc_info:
        join_geometry_and_attributes(
            ["L01"],
            [{"Name": "L01"}, {"Name": "L02"}],
            "Name",
        )
    assert exc_info.value.context["missing_geometry_keys"] == ["L02"]


def test_never_matches_by_approximate_or_case_insensitive_key() -> None:
    """Rule 6: no approximation, text search or case correction on the
    key - 'l01' and 'L01' are different keys, full stop."""
    with pytest.raises(AttributeJoinError) as exc_info:
        join_geometry_and_attributes(["L01"], [{"Name": "l01"}], "Name")
    assert exc_info.value.context["missing_attribute_keys"] == ["L01"]
    assert exc_info.value.context["missing_geometry_keys"] == ["l01"]


def test_collects_every_violation_at_once_instead_of_failing_fast() -> None:
    result_context = None
    try:
        join_geometry_and_attributes(
            ["L01", "L01", None, "L03"],
            [{"Name": "L01"}, {"Name": "L01"}, {"Name": ""}, {"Name": "L04"}],
            "Name",
        )
    except AttributeJoinError as exc:
        result_context = exc.context

    assert result_context == {
        "empty_geometry_feature_indices": [2],
        "empty_attribute_row_indices": [2],
        "duplicate_geometry_keys": ["L01"],
        "duplicate_attribute_keys": ["L01"],
        "missing_geometry_keys": ["L04"],
        "missing_attribute_keys": ["L03"],
    }
