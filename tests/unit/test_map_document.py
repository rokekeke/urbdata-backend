"""Structural validation of the MapDocument v1 contract (ADR 014).

Covers the valid fixture round-trip and every invalid example listed in
the ADR's acceptance section (DOC-BE-001/005).
"""

import json
import uuid
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from app.domain.cartography.document import (
    CATEGORICAL_CLASS_BLOCK_LIMIT,
    FEATURE_PANEL_MAX_BLOCKS,
    TABLE_FIELD_MAX,
    MapDocumentConfig,
    document_warnings,
    upcast_document,
)

FIXTURE = Path(__file__).parent.parent / "fixtures" / "map_documents" / "v1_example.json"


def _fixture_payload() -> dict[str, Any]:
    payload: dict[str, Any] = json.loads(FIXTURE.read_text(encoding="utf-8"))
    return payload


def _layer(payload: dict[str, Any], index: int = 0) -> dict[str, Any]:
    layer: dict[str, Any] = payload["layers"][index]
    return layer


def _panel(payload: dict[str, Any], index: int = 0) -> dict[str, Any]:
    panel: dict[str, Any] = _layer(payload, index)["interaction"]["feature_panel"]
    return panel


class TestFeaturePanel:
    """ADR 014, Decisao 7 (nota 33)."""

    def _expect_error(self, payload: dict[str, Any], fragment: str) -> None:
        with pytest.raises(ValidationError) as excinfo:
            MapDocumentConfig.model_validate(payload)
        assert fragment in str(excinfo.value)

    def test_disabled_by_default_is_valid(self) -> None:
        payload = _fixture_payload()
        _panel(payload, 0).update(
            {"enabled": False, "title_field": None, "width": "compact", "blocks": []}
        )

        document = MapDocumentConfig.model_validate(payload)

        panel = document.layers[0].interaction.feature_panel
        assert panel.enabled is False
        assert panel.blocks == []

    def test_fixture_panel_round_trips_with_text_and_table_blocks(self) -> None:
        payload = _fixture_payload()

        document = MapDocumentConfig.model_validate(payload)

        panel = document.layers[0].interaction.feature_panel
        assert panel.enabled is True
        assert panel.width.value == "medium"
        assert [block.type for block in panel.blocks] == ["text", "table"]

    def test_text_block_with_project_level_indicator_is_rejected(self) -> None:
        payload = _fixture_payload()
        _panel(payload)["blocks"] = [
            {
                "type": "text",
                "source": "indicator",
                "field": "territorial.total_area",
                "style": "body",
            }
        ]
        self._expect_error(payload, "nao e por feicao")

    def test_table_block_requires_at_least_one_field(self) -> None:
        payload = _fixture_payload()
        _panel(payload)["blocks"] = [{"type": "table", "layout": "key_value", "fields": []}]
        self._expect_error(payload, "at least 1 item")

    def test_text_format_rejects_decimals(self) -> None:
        payload = _fixture_payload()
        _panel(payload)["blocks"] = [
            {
                "type": "table",
                "layout": "key_value",
                "fields": [
                    {
                        "source": "property",
                        "key": "quadra_id",
                        "label": "Quadra",
                        "format": {"type": "text", "decimals": 2},
                    }
                ],
            }
        ]
        self._expect_error(payload, "decimals/prefix/suffix")

    def test_duplicate_table_field_is_rejected(self) -> None:
        payload = _fixture_payload()
        field = {"source": "property", "key": "quadra_id", "label": "Quadra", "format": None}
        _panel(payload)["blocks"] = [
            {"type": "table", "layout": "key_value", "fields": [field, dict(field)]}
        ]
        self._expect_error(payload, "campo duplicado")

    def test_too_many_blocks_is_rejected(self) -> None:
        payload = _fixture_payload()
        block = {"type": "text", "source": "property", "field": "quadra_id", "style": "body"}
        _panel(payload)["blocks"] = [dict(block) for _ in range(FEATURE_PANEL_MAX_BLOCKS + 1)]
        self._expect_error(payload, "at most")

    def test_too_many_table_fields_is_rejected(self) -> None:
        payload = _fixture_payload()
        fields = [
            {"source": "property", "key": f"campo_{i}", "label": f"Campo {i}", "format": None}
            for i in range(TABLE_FIELD_MAX + 1)
        ]
        _panel(payload)["blocks"] = [
            {"type": "table", "layout": "key_value", "fields": fields}
        ]
        self._expect_error(payload, "at most")

    def test_unknown_block_type_is_rejected(self) -> None:
        payload = _fixture_payload()
        _panel(payload)["blocks"] = [{"type": "chart", "field": "quadra_id"}]
        self._expect_error(payload, "chart")

    def test_label_above_60_chars_is_rejected(self) -> None:
        payload = _fixture_payload()
        _panel(payload)["blocks"] = [
            {
                "type": "table",
                "layout": "key_value",
                "fields": [
                    {
                        "source": "property",
                        "key": "quadra_id",
                        "label": "x" * 61,
                        "format": None,
                    }
                ],
            }
        ]
        self._expect_error(payload, "at most 60")


class TestValidDocuments:
    def test_fixture_v1_validates_and_round_trips(self) -> None:
        payload = _fixture_payload()

        document = MapDocumentConfig.model_validate(payload)

        # Round-trip integrity (DOC-BE-003): serializing back yields the
        # same content the client sent.
        assert json.loads(document.model_dump_json(by_alias=True)) == payload
        assert document_warnings(document) == []

    def test_empty_layer_list_is_a_valid_draft(self) -> None:
        payload = _fixture_payload()
        payload["layers"] = []

        document = MapDocumentConfig.model_validate(payload)

        assert document.layers == []

    def test_threshold_scale_with_ordered_stops(self) -> None:
        payload = _fixture_payload()
        layer = _layer(payload)
        layer["representation"].update(
            {"scale": "threshold", "classes": None, "stops": [10.0, 20.0, 50.0]}
        )
        layer["style"]["fill"]["palette"] = ["#111111", "#222222", "#333333", "#444444"]

        document = MapDocumentConfig.model_validate(payload)

        assert document.layers[0].representation.effective_classes() == 4

    def test_categorical_above_12_classes_warns_but_validates(self) -> None:
        payload = _fixture_payload()
        layer = _layer(payload)
        layer["representation"].update(
            {"source": "property", "indicator_code": None, "field": "uso",
             "mode": "categorical", "scale": "ordinal", "classes": 14}
        )
        layer["style"]["fill"]["palette"] = [f"#0000{i:02x}" for i in range(14)]

        document = MapDocumentConfig.model_validate(payload)
        warnings = document_warnings(document)

        assert [w.code for w in warnings] == ["high_categorical_class_count"]
        assert warnings[0].layer_id == document.layers[0].layer_id


class TestInvalidDocuments:
    def _expect_error(self, payload: dict[str, Any], fragment: str) -> None:
        with pytest.raises(ValidationError) as excinfo:
            MapDocumentConfig.model_validate(payload)
        assert fragment in str(excinfo.value)

    def test_categorical_with_linear_scale(self) -> None:
        payload = _fixture_payload()
        _layer(payload)["representation"].update(
            {"source": "property", "indicator_code": None, "field": "uso",
             "mode": "categorical", "scale": "linear"}
        )
        self._expect_error(payload, "incompativel")

    def test_unordered_stops(self) -> None:
        payload = _fixture_payload()
        layer = _layer(payload)
        layer["representation"].update(
            {"scale": "threshold", "classes": None, "stops": [10.0, 5.0, 20.0]}
        )
        self._expect_error(payload, "estritamente crescentes")

    def test_too_many_stops(self) -> None:
        payload = _fixture_payload()
        layer = _layer(payload)
        layer["representation"].update(
            {"scale": "threshold", "classes": None, "stops": [float(i) for i in range(13)]}
        )
        self._expect_error(payload, "stops deve ter entre")

    def test_palette_size_mismatch(self) -> None:
        payload = _fixture_payload()
        _layer(payload)["style"]["fill"]["palette"] = ["#111111", "#222222"]
        self._expect_error(payload, "palette tem 2 cores")

    def test_basemap_outside_catalog(self) -> None:
        payload = _fixture_payload()
        payload["basemap_id"] = "osm-custom"
        self._expect_error(payload, "fora do catalogo")

    def test_classes_above_block_limit(self) -> None:
        payload = _fixture_payload()
        _layer(payload)["representation"]["classes"] = CATEGORICAL_CLASS_BLOCK_LIMIT + 1
        self._expect_error(payload, "classes")

    def test_unregistered_indicator(self) -> None:
        payload = _fixture_payload()
        _layer(payload)["representation"]["indicator_code"] = "nao.existe"
        self._expect_error(payload, "nao registrado")

    def test_project_level_indicator_cannot_be_mapped(self) -> None:
        payload = _fixture_payload()
        _layer(payload)["representation"]["indicator_code"] = "territorial.total_area"
        self._expect_error(payload, "nao e por feicao")

    def test_invalid_hex_color(self) -> None:
        payload = _fixture_payload()
        _layer(payload)["style"]["stroke"]["color"] = "vermelho"
        self._expect_error(payload, "cor invalida")

    def test_stroke_width_above_limit(self) -> None:
        payload = _fixture_payload()
        _layer(payload)["style"]["stroke"]["width_px"] = 21
        self._expect_error(payload, "width_px")

    def test_null_behavior_color_without_null_color(self) -> None:
        payload = _fixture_payload()
        _layer(payload)["representation"]["null_behavior"] = "color"
        self._expect_error(payload, "null_color")

    def test_duplicate_layer_id(self) -> None:
        payload = _fixture_payload()
        payload["layers"].append(json.loads(json.dumps(payload["layers"][0])))
        self._expect_error(payload, "duplicado")

    def test_filters_reserved_in_v1(self) -> None:
        payload = _fixture_payload()
        _layer(payload)["interaction"]["filters"] = {"field": "uso"}
        self._expect_error(payload, "filters")

    def test_unknown_key_is_rejected(self) -> None:
        payload = _fixture_payload()
        payload["theme_song"] = "nao"
        self._expect_error(payload, "theme_song")

    def test_source_none_with_thematic_mode(self) -> None:
        payload = _fixture_payload()
        _layer(payload, 1)["representation"]["mode"] = "sequential"
        self._expect_error(payload, "source=none exige mode=single")


class TestUpcast:
    def test_v1_is_identity(self) -> None:
        payload = _fixture_payload()
        assert upcast_document(payload) is payload

    def test_unknown_version_raises(self) -> None:
        with pytest.raises(ValueError, match="desconhecida"):
            upcast_document({"schema_version": "99"})


class TestWarningModel:
    def test_warning_carries_layer_reference(self) -> None:
        payload = _fixture_payload()
        layer = _layer(payload)
        layer["representation"].update(
            {"source": "property", "indicator_code": None, "field": "uso",
             "mode": "categorical", "scale": "ordinal", "classes": 20}
        )
        layer["style"]["fill"]["palette"] = [f"#00ff{i:02x}" for i in range(20)]

        warnings = document_warnings(MapDocumentConfig.model_validate(payload))

        assert warnings[0].layer_id == uuid.UUID(layer["layer_id"])
