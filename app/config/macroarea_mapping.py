"""Territorial macroarea taxonomy for the MVP (Obsidian note 11). Closed
list confirmed by the responsible party on 2026-07-17, pending the export
team's final template - see docs/adr/008-macroarea-territorial-layer.md.
"""

from enum import StrEnum

from app.domain.text_encoding import normalize_key


class Macroarea(StrEnum):
    LOTE = "lote"
    SISTEMA_VIARIO = "sistema_viario"
    AVL = "avl"  # Área Verde de Lazer
    APP = "app"  # Área de Preservação Permanente
    ACI = "aci"  # Área Comunitária ou Institucional
    NULO = "nulo"  # não classificada


MACROAREA_ALIASES: dict[str, Macroarea] = {
    normalize_key(macroarea.value): macroarea for macroarea in Macroarea
}


def resolve_macroarea(raw: str | None) -> Macroarea | None:
    """Resolve a raw export value to a canonical `Macroarea`.

    Returns `None` for missing or unrecognized values - callers treat that
    the same as `Macroarea.NULO` (requires manual classification), rather
    than guessing.
    """
    if raw is None:
        return None
    return MACROAREA_ALIASES.get(normalize_key(raw))
