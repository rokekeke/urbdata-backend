"""Repairs double-encoded UTF-8 ("mojibake") in uploaded GeoJSON property
text - e.g. some GIS/BIM exporters read the original UTF-8 bytes as
Latin-1/cp1252 and re-encode them as UTF-8, turning "Área" into "Ãrea".

Reversing this is a deterministic byte round-trip, not a domain judgment
call, so it is safe to apply automatically at upload validation (unlike
geometry corrections, which are never automatic).
"""

from typing import Any


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
