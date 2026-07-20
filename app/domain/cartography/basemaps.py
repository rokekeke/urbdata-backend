"""Controlled basemap catalog v1 (ADR 014, Decisao 5).

Static, server-defined, credential-free: the three public CARTO vector
styles (the same MapLibre defaults kepler.gl ships) plus `none`. No free
URLs in v1 - that closes off SSRF, token leakage and license ambiguity.
Availability is not contractually guaranteed by the provider, so `none`
is always a valid fallback and must never be removed from the catalog.
"""

from dataclasses import dataclass
from enum import StrEnum

CARTO_ATTRIBUTION = "(c) OpenStreetMap contributors, (c) CARTO"


class BasemapColorMode(StrEnum):
    NONE = "none"
    LIGHT = "light"
    DARK = "dark"


@dataclass(frozen=True, slots=True)
class Basemap:
    id: str
    label: str
    style_url: str | None
    color_mode: BasemapColorMode
    attribution: str | None
    export_allowed: bool

    def __post_init__(self) -> None:
        # A basemap with tiles but no attribution must never exist (ADR 014:
        # attribution is mandatory and non-removable in every export).
        if self.style_url is not None and not self.attribution:
            raise ValueError("basemap with style_url requires attribution")


NO_BASEMAP_ID = "none"

BASEMAPS: tuple[Basemap, ...] = (
    Basemap(
        id=NO_BASEMAP_ID,
        label="Sem mapa-base",
        style_url=None,
        color_mode=BasemapColorMode.NONE,
        attribution=None,
        export_allowed=True,
    ),
    Basemap(
        id="positron",
        label="Claro (Positron)",
        style_url="https://basemaps.cartocdn.com/gl/positron-gl-style/style.json",
        color_mode=BasemapColorMode.LIGHT,
        attribution=CARTO_ATTRIBUTION,
        export_allowed=True,
    ),
    Basemap(
        id="dark_matter",
        label="Escuro (Dark Matter)",
        style_url="https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json",
        color_mode=BasemapColorMode.DARK,
        attribution=CARTO_ATTRIBUTION,
        export_allowed=True,
    ),
    Basemap(
        id="voyager",
        label="Detalhado (Voyager)",
        style_url="https://basemaps.cartocdn.com/gl/voyager-gl-style/style.json",
        color_mode=BasemapColorMode.LIGHT,
        attribution=CARTO_ATTRIBUTION,
        export_allowed=True,
    ),
)

BASEMAP_IDS: frozenset[str] = frozenset(basemap.id for basemap in BASEMAPS)


def get_basemap(basemap_id: str) -> Basemap | None:
    for basemap in BASEMAPS:
        if basemap.id == basemap_id:
            return basemap
    return None
