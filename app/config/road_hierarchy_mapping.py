"""Canonical road attributes used by the uploaded centerline layer."""

from enum import StrEnum

from app.domain.text_encoding import normalize_key


class RoadStatus(StrEnum):
    EXISTING = "existente"
    PROPOSED = "proposta"


_ROAD_STATUS_ALIASES: dict[str, RoadStatus] = {
    "existente": RoadStatus.EXISTING,
    "existing": RoadStatus.EXISTING,
    "atual": RoadStatus.EXISTING,
    "implantada": RoadStatus.EXISTING,
    "viaexistente": RoadStatus.EXISTING,
    "proposta": RoadStatus.PROPOSED,
    "proposto": RoadStatus.PROPOSED,
    "proposed": RoadStatus.PROPOSED,
    "nova": RoadStatus.PROPOSED,
    "novo": RoadStatus.PROPOSED,
    "projetada": RoadStatus.PROPOSED,
    "projetado": RoadStatus.PROPOSED,
    "viaprojetada": RoadStatus.PROPOSED,
    "viaproposta": RoadStatus.PROPOSED,
}


def resolve_road_status(value: object) -> RoadStatus | None:
    """Normalize an explicit source classification without guessing.

    Unknown or empty values remain unclassified and are surfaced by the
    network-quality warnings instead of silently becoming existing roads.
    """
    if value is None:
        return None
    return _ROAD_STATUS_ALIASES.get(normalize_key(str(value)))

ROAD_WIDTHS_M: dict[str, float] = {}
