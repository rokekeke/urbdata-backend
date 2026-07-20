"""Pure-logic tests for write-time contextual validation (ADR 014,
Decisao 3/8, item 4.3). No DB - `LayerContext` is synthetic here;
`build_layer_contexts` (which does the real querying) is covered by
`tests/integration/test_map_document_repository.py`.
"""

import json
import uuid
from pathlib import Path
from typing import Any

from app.domain.cartography.contextual_validation import (
    LayerContext,
    references_property_field,
    validate_document_context,
)
from app.domain.cartography.document import MapDocumentConfig
from app.domain.cartography.representation_options import FieldOrigin, FieldStats

FIXTURE = Path(__file__).parent.parent / "fixtures" / "map_documents" / "v1_example.json"

LAYER_0_ID = uuid.UUID("0b2f6d0e-49f2-4a11-9f2d-6a5f5b7f2c01")
LAYER_1_ID = uuid.UUID("3c9a1f7b-2d64-4e08-8a4e-9d1c0b3e5f02")


def _fixture_payload() -> dict[str, Any]:
    payload: dict[str, Any] = json.loads(FIXTURE.read_text(encoding="utf-8"))
    return payload


def _config(payload: dict[str, Any] | None = None) -> MapDocumentConfig:
    return MapDocumentConfig.model_validate(payload or _fixture_payload())


def _text_field_stats(field: str = "quadra_id") -> FieldStats:
    """A healthy, small-cardinality text field - existence-only checks
    (feature_panel references) don't care about the rest of the stats."""
    return FieldStats(
        field=field,
        origin=FieldOrigin.SOURCE,
        present_count=10,
        empty_count=0,
        cardinality=2,
        numeric_count=0,
        min_value=None,
        max_value=None,
        distinct_values=("Q1", "Q2"),
    )


def _numeric_field_stats(field: str, *, cardinality: int = 8) -> FieldStats:
    return FieldStats(
        field=field,
        origin=FieldOrigin.SOURCE,
        present_count=10,
        empty_count=0,
        cardinality=cardinality,
        numeric_count=10,
        min_value=0.0,
        max_value=100.0,
        distinct_values=None,
    )


def _mixed_field_stats(field: str) -> FieldStats:
    return FieldStats(
        field=field,
        origin=FieldOrigin.SOURCE,
        present_count=10,
        empty_count=0,
        cardinality=8,
        numeric_count=4,
        min_value=0.0,
        max_value=100.0,
        distinct_values=None,
    )


def _empty_field_stats(field: str) -> FieldStats:
    return FieldStats(
        field=field,
        origin=FieldOrigin.SOURCE,
        present_count=5,
        empty_count=5,
        cardinality=0,
        numeric_count=0,
        min_value=None,
        max_value=None,
        distinct_values=None,
    )


def _full_context() -> dict[uuid.UUID, LayerContext]:
    """Everything the fixture references resolves - the "nothing wrong"
    baseline every violation test mutates away from."""
    return {
        LAYER_0_ID: LayerContext(
            layer_type="territorio", fields={"quadra_id": _text_field_stats()}
        ),
        LAYER_1_ID: LayerContext(layer_type="territorio", fields={}),
    }


def _property_representation_payload(
    field: str,
    mode: str,
    *,
    scale: str | None = None,
    classes: int | None = None,
    stops: list[float] | None = None,
    palette: list[str] | None = None,
) -> dict[str, Any]:
    """A single-layer document with `source=property` driving the
    representation - the fixture's layer 0 uses source=indicator, so mode
    x field-type tests need their own minimal, fully valid template."""
    payload = _fixture_payload()
    layer = payload["layers"][0]
    layer["representation"] = {
        "source": "property",
        "field": field,
        "indicator_code": None,
        "mode": mode,
        "scale": scale,
        "classes": classes,
        "stops": stops,
        "null_behavior": "transparent",
    }
    layer["style"]["fill"]["palette"] = palette
    layer["interaction"]["feature_panel"] = {
        "enabled": False,
        "title_field": None,
        "width": "compact",
        "blocks": [],
    }
    payload["layers"] = [layer]
    return payload


def _indicator_representation_payload(indicator_code: str, mode: str) -> dict[str, Any]:
    payload = _fixture_payload()
    layer = payload["layers"][0]
    layer["representation"]["indicator_code"] = indicator_code
    layer["representation"]["mode"] = mode
    if mode == "single":
        layer["representation"]["scale"] = None
        layer["representation"]["classes"] = None
        layer["style"]["fill"]["palette"] = None
        layer["style"]["fill"]["color"] = "#336699"
    layer["interaction"]["feature_panel"] = {
        "enabled": False,
        "title_field": None,
        "width": "compact",
        "blocks": [],
    }
    payload["layers"] = [layer]
    return payload


class TestValidDocument:
    def test_fixture_produces_no_violations(self) -> None:
        assert validate_document_context(_config(), _full_context()) == []


class TestLayerMembership:
    def test_layer_missing_from_context_is_a_violation(self) -> None:
        contexts = _full_context()
        del contexts[LAYER_1_ID]

        violations = validate_document_context(_config(), contexts)

        assert [v.path for v in violations] == ["layers[1].layer_id"]
        assert violations[0].code == "layer_not_in_version"

    def test_missing_layer_skips_its_other_checks(self) -> None:
        # Layer 0 has an indicator/field reference too, but since it's
        # entirely missing from the version, only the membership
        # violation should be reported - nothing else about it is
        # checkable.
        contexts = _full_context()
        del contexts[LAYER_0_ID]

        violations = validate_document_context(_config(), contexts)

        assert len(violations) == 1
        assert violations[0].path == "layers[0].layer_id"


class TestIndicatorCompatibility:
    def test_indicator_incompatible_with_layer_type(self) -> None:
        contexts = _full_context()
        # lots.frontage_length needs feature_key=feature_id -> "territorio"
        # layers, not "quadras".
        contexts[LAYER_0_ID] = LayerContext(
            layer_type="quadras", fields={"quadra_id": _text_field_stats()}
        )

        violations = validate_document_context(_config(), contexts)

        codes_by_path = {v.path: v.code for v in violations}
        assert codes_by_path["layers[0].representation.indicator_code"] == (
            "indicator_incompatible_with_layer"
        )
        # Same indicator also drives the feature_panel table's indicator
        # field in the fixture - both references are checked independently.
        assert (
            codes_by_path["layers[0].interaction.feature_panel.blocks[1].fields[1].key"]
            == "indicator_incompatible_with_layer"
        )

    def test_compatible_indicator_is_not_a_violation(self) -> None:
        payload = _fixture_payload()
        payload["layers"][0]["representation"]["indicator_code"] = "quadras.face_length_score"
        payload["layers"][0]["interaction"]["feature_panel"]["blocks"][1]["fields"][1][
            "key"
        ] = "quadras.face_length_score"
        contexts = _full_context()
        contexts[LAYER_0_ID] = LayerContext(
            layer_type="quadras", fields={"quadra_id": _text_field_stats()}
        )

        violations = validate_document_context(_config(payload), contexts)

        assert violations == []


class TestPropertyFieldExistence:
    def test_missing_field_flags_every_reference_to_it(self) -> None:
        contexts = _full_context()
        contexts[LAYER_0_ID] = LayerContext(layer_type="territorio", fields={})

        violations = validate_document_context(_config(), contexts)

        paths = {v.path for v in violations}
        assert paths == {
            "layers[0].interaction.feature_panel.title_field",
            "layers[0].interaction.feature_panel.blocks[0].field",
            "layers[0].interaction.feature_panel.blocks[1].fields[0].key",
        }
        assert all(v.code == "field_not_found" for v in violations)

    def test_present_field_is_not_a_violation(self) -> None:
        assert validate_document_context(_config(), _full_context()) == []


class TestModeFieldCompatibility:
    """The gap flagged after 4.3: document.py's own docstring defers
    "mode compativel com o tipo do campo" to this module."""

    def test_sequential_on_text_field_is_rejected(self) -> None:
        payload = _property_representation_payload(
            "bairro", "sequential", scale="quantile", classes=5,
            palette=["#111111", "#222222", "#333333", "#444444", "#555555"],
        )
        contexts = {
            LAYER_0_ID: LayerContext(
                layer_type="territorio", fields={"bairro": _text_field_stats("bairro")}
            ),
        }

        violations = validate_document_context(_config(payload), contexts)

        assert [(v.path, v.code) for v in violations] == [
            ("layers[0].representation.mode", "mode_incompatible_with_field_type")
        ]

    def test_sequential_on_numeric_field_is_allowed(self) -> None:
        payload = _property_representation_payload(
            "area_m2", "sequential", scale="quantile", classes=5,
            palette=["#111111", "#222222", "#333333", "#444444", "#555555"],
        )
        contexts = {
            LAYER_0_ID: LayerContext(
                layer_type="territorio", fields={"area_m2": _numeric_field_stats("area_m2")}
            ),
        }

        assert validate_document_context(_config(payload), contexts) == []

    def test_diverging_on_boolean_field_is_rejected(self) -> None:
        payload = _property_representation_payload(
            "parcelavel", "diverging", scale="linear", classes=3,
            palette=["#111111", "#222222", "#333333"],
        )
        boolean_stats = FieldStats(
            field="parcelavel", origin=FieldOrigin.MAPPED, present_count=10,
            empty_count=0, cardinality=2, numeric_count=0, min_value=None,
            max_value=None, distinct_values=None, boolean=True,
        )
        contexts = {
            LAYER_0_ID: LayerContext(layer_type="territorio", fields={"parcelavel": boolean_stats}),
        }

        violations = validate_document_context(_config(payload), contexts)

        assert [v.code for v in violations] == ["mode_incompatible_with_field_type"]

    def test_categorical_on_numeric_field_is_allowed(self) -> None:
        # Ordinal scales can legitimately treat numeric codes (e.g. zoning
        # classes 1-5) as discrete categories - not rejected.
        payload = _property_representation_payload(
            "zona", "categorical", scale="ordinal", classes=3,
            palette=["#111111", "#222222", "#333333"],
        )
        contexts = {
            LAYER_0_ID: LayerContext(
                layer_type="territorio",
                fields={"zona": _numeric_field_stats("zona", cardinality=3)},
            ),
        }

        assert validate_document_context(_config(payload), contexts) == []

    def test_empty_field_rejects_any_non_single_mode(self) -> None:
        payload = _property_representation_payload(
            "vazio", "categorical", scale="ordinal", classes=1, palette=["#111111"]
        )
        contexts = {
            LAYER_0_ID: LayerContext(
                layer_type="territorio", fields={"vazio": _empty_field_stats("vazio")}
            ),
        }

        violations = validate_document_context(_config(payload), contexts)

        assert [v.code for v in violations] == ["field_unsuitable_for_representation"]

    def test_empty_field_allows_single_mode(self) -> None:
        payload = _property_representation_payload("vazio", "single")
        payload["layers"][0]["style"]["fill"]["color"] = "#336699"
        contexts = {
            LAYER_0_ID: LayerContext(
                layer_type="territorio", fields={"vazio": _empty_field_stats("vazio")}
            ),
        }

        assert validate_document_context(_config(payload), contexts) == []

    def test_mixed_type_field_rejects_sequential(self) -> None:
        payload = _property_representation_payload(
            "confuso", "sequential", scale="linear", classes=4,
            palette=["#111111", "#222222", "#333333", "#444444"],
        )
        contexts = {
            LAYER_0_ID: LayerContext(
                layer_type="territorio", fields={"confuso": _mixed_field_stats("confuso")}
            ),
        }

        violations = validate_document_context(_config(payload), contexts)

        assert [v.code for v in violations] == ["field_unsuitable_for_representation"]


class TestModeIndicatorCompatibility:
    """quadras.stats/min_rotated_rectangle are structured (dict) results
    (catalog unit="composto") - cannot drive a numeric/ordinal scale."""

    def test_sequential_on_structured_indicator_is_rejected(self) -> None:
        payload = _indicator_representation_payload("quadras.stats", "sequential")
        contexts = _full_context()
        contexts[LAYER_0_ID] = LayerContext(
            layer_type="quadras", fields={"quadra_id": _text_field_stats()}
        )

        violations = validate_document_context(_config(payload), contexts)

        assert [v.code for v in violations] == ["mode_incompatible_with_indicator_type"]
        assert violations[0].path == "layers[0].representation.mode"

    def test_single_on_structured_indicator_is_allowed(self) -> None:
        payload = _indicator_representation_payload("quadras.stats", "single")
        contexts = _full_context()
        contexts[LAYER_0_ID] = LayerContext(
            layer_type="quadras", fields={"quadra_id": _text_field_stats()}
        )

        assert validate_document_context(_config(payload), contexts) == []

    def test_sequential_on_scalar_indicator_is_allowed(self) -> None:
        payload = _indicator_representation_payload("quadras.compactness", "sequential")
        contexts = _full_context()
        contexts[LAYER_0_ID] = LayerContext(
            layer_type="quadras", fields={"quadra_id": _text_field_stats()}
        )

        assert validate_document_context(_config(payload), contexts) == []


class TestReferencesPropertyField:
    def test_true_when_representation_uses_property(self) -> None:
        payload = _fixture_payload()
        payload["layers"][1]["representation"] = {
            "source": "property",
            "field": "macroarea",
            "indicator_code": None,
            "mode": "categorical",
            "scale": "ordinal",
            "classes": 1,
            "stops": None,
            "null_behavior": "transparent",
        }
        payload["layers"][1]["style"]["fill"]["palette"] = ["#ffffff"]
        config = _config(payload)

        assert references_property_field(config.layers[1]) is True

    def test_false_when_layer_only_uses_indicator_and_disabled_panel(self) -> None:
        config = _config()

        assert references_property_field(config.layers[1]) is False

    def test_true_when_layer_only_needs_title_field(self) -> None:
        config = _config()

        assert references_property_field(config.layers[0]) is True
