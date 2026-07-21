"""Conservative source-field -> mapped-attribute suggestions.

`LayerAttributesOut.suggested_mapping` has existed in the schema since Fase 2
but was always returned as `{}` - never implemented. This fills it in,
deliberately narrow: only source field names already confirmed in a real
export are recognized (exact alias, tolerant of case/accents/formatting via
`normalize_key`) - never fuzzy/keyword matching (e.g. "any field containing
MACRO"). A wrong automatic guess here would silently steer a real mapping
decision (macroarea, parcelavel, ...); rule 6 of the project's invariants
says to never do that. Add a new alias only after confirming a real
delivered file uses it - this is a lookup table of observed facts, not a
heuristic.
"""

from collections.abc import Iterable

from app.domain.text_encoding import normalize_key

# Verified against real exports: Obsidian notas 11/23 (earlier Revit/
# Masterplan deliveries) and the PROJETO_R01.json/MATRICULA.json pair
# inspected 2026-07-20. `road_status` has no confirmed alias yet - the
# source files seen so far don't carry usable values for it.
# `land_use`/`ca_max` were confirmed later by the separate
# PROJETO_R01_GEOMETRIA.json/DATA_EXPORT_PROJETO_01.csv pair evaluated for
# the combined GeoJSON+CSV import (nota 53/54): "Uso do solo" carries real
# categories (Residencial/Misto/Comercial/Industrial/Institucional) and
# "07.COEFICIENTE DE APROVEITAMENTO" carries real numeric values, unlike
# the earlier sample's "(none)"/"Element" exporter-bug placeholders.
# `macroarea` now has two confirmed aliases: "Comments" from the earlier
# sample stays valid, "TIPO DE MACROÁREA" is the new CSV's equivalent
# column - both are kept, never replaced.
_ALIASES: dict[str, tuple[str, ...]] = {
    "macroarea": ("Comments", "TIPO DE MACROÁREA"),
    "quadra_id": ("QUADRA",),
    "parcelavel": ("P_Área de Projeto",),
    "reference_area_m2": ("Area",),
    "land_use": ("Uso do solo",),
    "ca_max": ("07.COEFICIENTE DE APROVEITAMENTO",),
}


def suggest_attribute_mapping(source_fields: Iterable[str]) -> dict[str, str | None]:
    """Return type matches `LayerAttributesOut.suggested_mapping` exactly
    (`dict[str, str | None]`) even though this function only ever fills in
    `str` values - `dict` is invariant, so mypy strict rejects a narrower
    `dict[str, str]` here."""
    normalized_lookup = {normalize_key(field): field for field in source_fields}
    suggestions: dict[str, str | None] = {}
    for target, aliases in _ALIASES.items():
        for alias in aliases:
            match = normalized_lookup.get(normalize_key(alias))
            if match is not None:
                suggestions[target] = match
                break
    return suggestions
