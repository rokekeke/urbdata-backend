"""Repairs double-encoded UTF-8 ("mojibake") in uploaded GeoJSON property
text - e.g. some GIS/BIM exporters read the original UTF-8 bytes as
Latin-1/cp1252 and re-encode them as UTF-8, turning "Área" into "Ãrea".

Reversing this is a deterministic byte round-trip, not a domain judgment
call, so it is safe to apply automatically at upload validation (unlike
geometry corrections, which are never automatic).
"""

import unicodedata
from typing import Any


def normalize_key(text: str) -> str:
    """Lowercase, strip accents/diacritics, and drop separators, for case-,
    encoding- and formatting-tolerant lookups against a closed vocabulary.

    Collapsing separators matters in practice: the same category shows up
    in real exports as "sistema_viario" (slug) and "SISTEMA VIÁRIO"
    (human-readable, from the `Comments` field) - both normalize to
    "sistemaviario". Unrelated to `fix_mojibake` below: this is for
    *comparing* text, not repairing corrupted bytes.
    """
    decomposed = unicodedata.normalize("NFKD", text.strip().lower())
    without_accents = "".join(
        character for character in decomposed if not unicodedata.combining(character)
    )
    return "".join(character for character in without_accents if character.isalnum())


def fix_mojibake(value: str) -> str:
    """Reverse a UTF-8-decoded-as-Latin-1-then-re-encoded-as-UTF-8 string.

    Leaves *value* untouched when the round-trip isn't clean, so text that
    was never double-encoded (e.g. plain ASCII, or already-correct UTF-8
    that isn't representable in Latin-1) is never touched.
    """
    try:
        return value.encode("latin-1").decode("utf-8")
    except (UnicodeEncodeError, UnicodeDecodeError):
        return value


def fix_geojson_feature_properties(properties: dict[str, Any]) -> dict[str, Any]:
    """Repair mojibake in both property names and string values of one
    GeoJSON Feature's `properties` object.
    """
    return {
        fix_mojibake(key): fix_mojibake(value) if isinstance(value, str) else value
        for key, value in properties.items()
    }
