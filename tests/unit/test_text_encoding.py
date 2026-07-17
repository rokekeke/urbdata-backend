import json
from pathlib import Path

from app.domain.text_encoding import fix_geojson_feature_properties, fix_mojibake

FIXTURE_PATH = Path(__file__).parent.parent / "Geosjon_basico_teste.json"


def _corrupt(correct: str) -> str:
    """Simulate the bug: UTF-8 bytes read as Latin-1, re-encoded as UTF-8."""
    return correct.encode("utf-8").decode("latin-1")


def test_fix_mojibake_reverses_the_double_utf8_encoding() -> None:
    # Built from chr()/codepoints, not literal accented source characters:
    # this environment's toolchain has shown it can mangle non-ASCII bytes
    # typed directly into a .py file. chr() is pure ASCII in the source, so
    # there is nothing for an encoding mismatch to corrupt before the test
    # even runs.
    a_upper_grave = chr(0xC1)  # "Á"
    e_lower_acute = chr(0xE9)  # "é"
    correct = "Acr" + e_lower_acute + "scimo de " + a_upper_grave + "rea"

    assert fix_mojibake(_corrupt(correct)) == correct


def test_fix_mojibake_recovers_the_real_exported_file_correctly() -> None:
    # This is the exact corruption pattern flagged in Obsidian note 10: an
    # uppercase accented letter (Á, U+00C1) turns into U+00C3 followed by
    # an invalid C1 control character (U+0081), not a printable glyph.
    raw = FIXTURE_PATH.read_bytes()
    features = json.loads(raw.decode("utf-8"))["features"]
    corrupted_comments = next(
        f["properties"]["Comments"]
        for f in features
        if f["properties"]["Comments"].startswith("SISTEMA")
    )
    assert corrupted_comments == "SISTEMA VI" + chr(0xC3) + chr(0x81) + "RIO"

    fixed = fix_mojibake(corrupted_comments)

    assert fixed == "SISTEMA VI" + chr(0xC1) + "RIO"


def test_fix_mojibake_leaves_plain_ascii_untouched() -> None:
    assert fix_mojibake("SISTEMA VIARIO") == "SISTEMA VIARIO"
    assert fix_mojibake("L-1") == "L-1"
    assert fix_mojibake("") == ""


def test_fix_mojibake_leaves_text_unrepresentable_in_latin1_untouched() -> None:
    tokyo = chr(0x6771) + chr(0x4EAC)
    assert fix_mojibake(tokyo) == tokyo


def test_fix_geojson_feature_properties_repairs_keys_and_string_values() -> None:
    a_upper_grave = chr(0xC1)
    key = "04." + a_upper_grave + "REA DE LOTE"
    value = "SISTEMA VI" + a_upper_grave + "RIO"
    properties = {
        _corrupt(key): "",
        "Comments": _corrupt(value),
        "Area": 4110.16406585,
        "Export to IFC": 0,
        "Image": None,
    }

    fixed = fix_geojson_feature_properties(properties)

    assert fixed == {
        key: "",
        "Comments": value,
        "Area": 4110.16406585,
        "Export to IFC": 0,
        "Image": None,
    }
