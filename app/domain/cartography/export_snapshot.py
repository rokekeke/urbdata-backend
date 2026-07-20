"""Export snapshot assembler (Fase 5, ADR 014 Decisao 6 + checkpoint 5.1).

Pure, DB-free: takes an already-validated `MapDocumentConfig` plus the
export-specific parameters (legend toggle, image spec, renderer info) and
assembles the exact JSONB shape persisted in `exports.config`, plus its
sha256 checksum. Called once, at export-creation time (`POST
/documents/{id}/exports`, item 5.5) - the 5.1 checkpoint resolved that
`renderer` is client-declared intent (which build it is about to render
with), not a render outcome, so nothing here needs to wait for the second
(file-delivery) call; the whole snapshot is knowable up front.

`layers` is copied by value straight from the document config - already
concrete, since `Representation.classes/stops`/`LayerStyle.fill.palette`
etc. are literal values in `MapDocumentConfig`, never references to
anything external. "nao so a referencia" in the ADR text contrasts this
with a hypothetical design that stored a pointer back to the live
document instead of a copy - it does not mean deriving new statistics
(e.g. real quantile breakpoints) here; that computation, if ever needed,
is the client's concern (same one it already runs to paint the legend).
"""

import hashlib
import json
import uuid
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Any

from app.domain.cartography.basemaps import get_basemap
from app.domain.cartography.document import MapDocumentConfig
from app.domain.cartography.exceptions import BasemapNotExportableError

RENDERER_AGENT = "frontend-maplibre"


class ImageRatio(StrEnum):
    SCREEN = "screen"
    FOUR_BY_THREE = "four_by_three"
    SIXTEEN_BY_NINE = "sixteen_by_nine"


class ImageResolution(StrEnum):
    ONE_X = "1x"
    TWO_X = "2x"


_SCALE_BY_RESOLUTION: dict[ImageResolution, int] = {
    ImageResolution.ONE_X: 1,
    ImageResolution.TWO_X: 2,
}


@dataclass(frozen=True, slots=True)
class ExportImageSpec:
    ratio_id: ImageRatio
    resolution_id: ImageResolution
    width_px: int
    height_px: int

    def __post_init__(self) -> None:
        if self.width_px <= 0 or self.height_px <= 0:
            raise ValueError("width_px/height_px devem ser positivos")

    @property
    def scale(self) -> int:
        return _SCALE_BY_RESOLUTION[self.resolution_id]


@dataclass(frozen=True, slots=True)
class ExportRendererInfo:
    maplibre_version: str
    frontend_version: str
    agent: str = RENDERER_AGENT


def _canonical_json(payload: dict[str, Any]) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def build_export_snapshot(
    *,
    document_id: uuid.UUID,
    document_revision: int,
    document_config: MapDocumentConfig,
    project_version_id: uuid.UUID,
    analysis_run_id: uuid.UUID | None,
    legend: bool,
    image: ExportImageSpec,
    renderer: ExportRendererInfo,
    requested_at: datetime,
) -> dict[str, Any]:
    basemap = get_basemap(document_config.basemap_id)
    # MapDocumentConfig._basemap_in_catalog already guarantees membership -
    # this can only be None if that invariant broke.
    assert basemap is not None
    if not basemap.export_allowed:
        raise BasemapNotExportableError(
            f"Mapa-base '{basemap.id}' nao esta liberado para exportacao.",
            context={"basemap_id": basemap.id},
        )

    payload: dict[str, Any] = {
        "document_id": str(document_id),
        "document_revision": document_revision,
        "schema_version": document_config.schema_version,
        "project_version_id": str(project_version_id),
        "analysis_run_id": str(analysis_run_id) if analysis_run_id is not None else None,
        "viewport": document_config.viewport.model_dump(mode="json"),
        "layers": [layer.model_dump(mode="json") for layer in document_config.layers],
        "basemap": {
            "id": basemap.id,
            "label": basemap.label,
            "style_url": basemap.style_url,
            "attribution": basemap.attribution,
        },
        "legend": legend,
        "image": {
            "ratio_id": image.ratio_id.value,
            "resolution_id": image.resolution_id.value,
            "scale": image.scale,
            "width_px": image.width_px,
            "height_px": image.height_px,
        },
        "renderer": {
            "agent": renderer.agent,
            "maplibre_version": renderer.maplibre_version,
            "frontend_version": renderer.frontend_version,
        },
        "requested_at": requested_at.isoformat(),
    }
    checksum = hashlib.sha256(_canonical_json(payload).encode("utf-8")).hexdigest()
    return {**payload, "checksum": checksum}
