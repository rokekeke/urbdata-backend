"""Export snapshot assembler (Fase 5, ADR 014 Decisao 6 + checkpoint 5.1) -
pure, DB-free construction of `exports.config` + its checksum.
"""

import hashlib
import json
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from app.domain.cartography import export_snapshot as export_snapshot_module
from app.domain.cartography.basemaps import Basemap, BasemapColorMode
from app.domain.cartography.document import MapDocumentConfig
from app.domain.cartography.exceptions import BasemapNotExportableError
from app.domain.cartography.export_snapshot import (
    ExportImageSpec,
    ExportRendererInfo,
    ImageRatio,
    ImageResolution,
    build_export_snapshot,
)

FIXTURE = Path(__file__).parent.parent / "fixtures" / "map_documents" / "v1_example.json"

DOCUMENT_ID = uuid.UUID("11111111-1111-1111-1111-111111111111")
PROJECT_VERSION_ID = uuid.UUID("22222222-2222-2222-2222-222222222222")
ANALYSIS_RUN_ID = uuid.UUID("33333333-3333-3333-3333-333333333333")


def _fixture_payload() -> dict[str, Any]:
    payload: dict[str, Any] = json.loads(FIXTURE.read_text(encoding="utf-8"))
    return payload


def _config() -> MapDocumentConfig:
    return MapDocumentConfig.model_validate(_fixture_payload())


def _image() -> ExportImageSpec:
    return ExportImageSpec(
        ratio_id=ImageRatio.SCREEN,
        resolution_id=ImageResolution.TWO_X,
        width_px=1600,
        height_px=900,
    )


def _renderer() -> ExportRendererInfo:
    return ExportRendererInfo(maplibre_version="4.7.1", frontend_version="0.1.0")


def _build(**overrides: Any) -> dict[str, Any]:
    kwargs: dict[str, Any] = {
        "document_id": DOCUMENT_ID,
        "document_revision": 3,
        "document_config": _config(),
        "project_version_id": PROJECT_VERSION_ID,
        "analysis_run_id": ANALYSIS_RUN_ID,
        "legend": True,
        "image": _image(),
        "renderer": _renderer(),
        "requested_at": datetime(2026, 7, 20, 12, 0, 0, tzinfo=UTC),
    }
    kwargs.update(overrides)
    return build_export_snapshot(**kwargs)


class TestShape:
    def test_every_key_from_the_adr_is_present(self) -> None:
        snapshot = _build()
        assert set(snapshot) == {
            "document_id",
            "document_revision",
            "schema_version",
            "project_version_id",
            "analysis_run_id",
            "viewport",
            "layers",
            "basemap",
            "legend",
            "image",
            "renderer",
            "requested_at",
            "checksum",
        }

    def test_ids_and_scalars_round_trip(self) -> None:
        snapshot = _build()
        assert snapshot["document_id"] == str(DOCUMENT_ID)
        assert snapshot["document_revision"] == 3
        assert snapshot["schema_version"] == "1"
        assert snapshot["project_version_id"] == str(PROJECT_VERSION_ID)
        assert snapshot["analysis_run_id"] == str(ANALYSIS_RUN_ID)
        assert snapshot["legend"] is True
        assert snapshot["requested_at"] == "2026-07-20T12:00:00+00:00"

    def test_analysis_run_id_is_optional(self) -> None:
        snapshot = _build(analysis_run_id=None)
        assert snapshot["analysis_run_id"] is None

    def test_layers_are_copied_by_value_from_the_document(self) -> None:
        config = _config()
        snapshot = _build(document_config=config)
        expected = [layer.model_dump(mode="json") for layer in config.layers]
        assert snapshot["layers"] == expected

    def test_viewport_matches_the_document(self) -> None:
        config = _config()
        snapshot = _build(document_config=config)
        assert snapshot["viewport"] == config.viewport.model_dump(mode="json")

    def test_image_carries_the_derived_scale(self) -> None:
        snapshot = _build(
            image=ExportImageSpec(
                ratio_id=ImageRatio.FOUR_BY_THREE,
                resolution_id=ImageResolution.ONE_X,
                width_px=800,
                height_px=600,
            )
        )
        assert snapshot["image"] == {
            "ratio_id": "four_by_three",
            "resolution_id": "1x",
            "scale": 1,
            "width_px": 800,
            "height_px": 600,
        }

    def test_renderer_defaults_agent_to_frontend_maplibre(self) -> None:
        snapshot = _build()
        assert snapshot["renderer"] == {
            "agent": "frontend-maplibre",
            "maplibre_version": "4.7.1",
            "frontend_version": "0.1.0",
        }


class TestBasemap:
    def test_resolved_from_the_catalog(self) -> None:
        snapshot = _build()
        assert snapshot["basemap"] == {
            "id": "positron",
            "label": "Claro (Positron)",
            "style_url": "https://basemaps.cartocdn.com/gl/positron-gl-style/style.json",
            "attribution": "(c) OpenStreetMap contributors, (c) CARTO",
        }

    def test_none_basemap_has_no_attribution_or_style_url(self) -> None:
        payload = _fixture_payload()
        payload["basemap_id"] = "none"
        snapshot = _build(document_config=MapDocumentConfig.model_validate(payload))
        assert snapshot["basemap"] == {
            "id": "none",
            "label": "Sem mapa-base",
            "style_url": None,
            "attribution": None,
        }

    def test_export_allowed_false_is_rejected(self, monkeypatch: pytest.MonkeyPatch) -> None:
        blocked = Basemap(
            id="positron",
            label="Claro (Positron)",
            style_url="https://basemaps.cartocdn.com/gl/positron-gl-style/style.json",
            color_mode=BasemapColorMode.LIGHT,
            attribution="(c) OpenStreetMap contributors, (c) CARTO",
            export_allowed=False,
        )
        monkeypatch.setattr(export_snapshot_module, "get_basemap", lambda _basemap_id: blocked)

        with pytest.raises(BasemapNotExportableError) as excinfo:
            _build()
        assert excinfo.value.context["basemap_id"] == "positron"


class TestChecksum:
    def test_deterministic_for_identical_inputs(self) -> None:
        assert _build()["checksum"] == _build()["checksum"]

    def test_changes_when_legend_toggle_changes(self) -> None:
        assert _build(legend=True)["checksum"] != _build(legend=False)["checksum"]

    def test_changes_when_requested_at_changes(self) -> None:
        first = _build(requested_at=datetime(2026, 7, 20, 12, 0, 0, tzinfo=UTC))
        second = _build(requested_at=datetime(2026, 7, 20, 12, 0, 1, tzinfo=UTC))
        assert first["checksum"] != second["checksum"]

    def test_does_not_cover_itself(self) -> None:
        snapshot = _build()
        payload_without_checksum = {k: v for k, v in snapshot.items() if k != "checksum"}
        expected = hashlib.sha256(
            json.dumps(
                payload_without_checksum, sort_keys=True, separators=(",", ":"), ensure_ascii=False
            ).encode("utf-8")
        ).hexdigest()
        assert snapshot["checksum"] == expected


class TestImageSpec:
    def test_rejects_non_positive_dimensions(self) -> None:
        with pytest.raises(ValueError):
            ExportImageSpec(
                ratio_id=ImageRatio.SCREEN,
                resolution_id=ImageResolution.ONE_X,
                width_px=0,
                height_px=600,
            )
