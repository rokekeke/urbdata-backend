"""Conservative source-field -> mapped-attribute suggestions.

Real export deliveries this exercises against: the Revit/Masterplan
template already used by `tests/Geosjon_basico_teste.json`, the
PROJETO_R01.json/MATRICULA.json pair inspected 2026-07-20 (same field
names: Comments, QUADRA, P_Área de Projeto, Area), and the
PROJETO_R01_GEOMETRIA.json/DATA_EXPORT_PROJETO_01.csv pair evaluated for
the combined GeoJSON+CSV import - nota 53/54 (TIPO DE MACROÁREA, Uso do
solo, 07.COEFICIENTE DE APROVEITAMENTO).
"""

from app.domain.attribute_suggestions import suggest_attribute_mapping


def test_matches_known_aliases_exactly() -> None:
    suggestion = suggest_attribute_mapping(
        ["Comments", "QUADRA", "P_Área de Projeto", "Area", "IfcGUID", "Family Name"]
    )
    assert suggestion == {
        "macroarea": "Comments",
        "quadra_id": "QUADRA",
        "parcelavel": "P_Área de Projeto",
        "reference_area_m2": "Area",
    }


def test_tolerates_case_and_extra_whitespace() -> None:
    suggestion = suggest_attribute_mapping(["  comments  ", "quadra", "area"])
    assert suggestion == {
        "macroarea": "  comments  ",
        "quadra_id": "quadra",
        "reference_area_m2": "area",
    }


def test_never_fuzzy_matches_a_field_that_only_contains_the_word() -> None:
    """A field like 'MACROAREA' (bare) or 'Masterplan - Uso' must NOT match
    just because it contains a related word - only an exact known alias is
    recognized. Guessing here would silently steer a real domain-mapping
    decision (rule 6). ('TIPO DE MACROAREA' no longer belongs in this test:
    since nota 53/54, 'TIPO DE MACROÁREA' - the accented version - is
    itself a confirmed real alias, so the two now match on purpose via the
    same accent-tolerant normalize_key already covered below.)"""
    suggestion = suggest_attribute_mapping(["MACROAREA", "Masterplan - Uso"])
    assert suggestion == {}


def test_confirmed_split_import_sample_aliases() -> None:
    """Nota 53/54: PROJETO_R01_GEOMETRIA.json/DATA_EXPORT_PROJETO_01.csv
    confirmed three additions - a second macroarea alias, and the first
    confirmed aliases for land_use/ca_max (the earlier sample only ever
    carried exporter-bug placeholders for those two)."""
    suggestion = suggest_attribute_mapping(
        ["TIPO DE MACROÁREA", "Uso do solo", "07.COEFICIENTE DE APROVEITAMENTO"]
    )
    assert suggestion == {
        "macroarea": "TIPO DE MACROÁREA",
        "land_use": "Uso do solo",
        "ca_max": "07.COEFICIENTE DE APROVEITAMENTO",
    }


def test_macroarea_prefers_first_alias_when_both_are_present() -> None:
    """Comments and TIPO DE MACROÁREA are aliases from two different real
    samples that have never co-occurred in practice; if a future file ever
    carried both, the earlier-confirmed one wins deterministically rather
    than the outcome depending on dict/set ordering."""
    suggestion = suggest_attribute_mapping(["TIPO DE MACROÁREA", "Comments"])
    assert suggestion == {"macroarea": "Comments"}


def test_missing_fields_are_simply_absent_not_none() -> None:
    suggestion = suggest_attribute_mapping(["Comments"])
    assert suggestion == {"macroarea": "Comments"}
    assert "quadra_id" not in suggestion


def test_empty_input_returns_empty_mapping() -> None:
    assert suggest_attribute_mapping([]) == {}
