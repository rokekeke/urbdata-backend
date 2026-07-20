"""Conservative source-field -> mapped-attribute suggestions.

Real export deliveries this exercises against: the Revit/Masterplan
template already used by `tests/Geosjon_basico_teste.json`, and the
PROJETO_R01.json/MATRICULA.json pair inspected 2026-07-20 (same field
names: Comments, QUADRA, P_Área de Projeto, Area).
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
    """A field like 'TIPO DE MACROAREA' must NOT match 'macroarea' just
    because it contains a related word - only the exact known alias
    ('Comments') is recognized. Guessing here would silently steer a real
    domain-mapping decision (rule 6)."""
    suggestion = suggest_attribute_mapping(["TIPO DE MACROAREA", "Masterplan - Uso"])
    assert suggestion == {}


def test_missing_fields_are_simply_absent_not_none() -> None:
    suggestion = suggest_attribute_mapping(["Comments"])
    assert suggestion == {"macroarea": "Comments"}
    assert "quadra_id" not in suggestion


def test_empty_input_returns_empty_mapping() -> None:
    assert suggest_attribute_mapping([]) == {}
