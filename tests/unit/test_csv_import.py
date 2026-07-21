"""Safe CSV parsing (nota 53/54, subetapa b2).

The confirmed-good shape from the real sample evaluated in nota 53 is
UTF-8 with BOM and `;` as the delimiter - covered here alongside the other
two candidate delimiters and the encoding/structure rejections.
"""

import pytest

from app.domain.csv_import import (
    AmbiguousDelimiterError,
    MalformedCSVError,
    UnreadableEncodingError,
    parse_csv,
)


def test_parses_utf8_with_bom_and_semicolon_delimiter() -> None:
    body = "Name;TIPO DE MACROÁREA;Area\nL01;Lote;1338.63 m²\nL02;AVL;450\n"
    raw = b"\xef\xbb\xbf" + body.encode("utf-8")
    assert parse_csv(raw) == [
        {"Name": "L01", "TIPO DE MACROÁREA": "Lote", "Area": "1338.63 m²"},
        {"Name": "L02", "TIPO DE MACROÁREA": "AVL", "Area": "450"},
    ]


def test_parses_utf8_without_bom_and_comma_delimiter() -> None:
    raw = b"Name,QUADRA\nL01,Q1\nL02,Q2\n"
    assert parse_csv(raw) == [{"Name": "L01", "QUADRA": "Q1"}, {"Name": "L02", "QUADRA": "Q2"}]


def test_parses_tab_delimiter() -> None:
    raw = b"Name\tQUADRA\nL01\tQ1\n"
    assert parse_csv(raw) == [{"Name": "L01", "QUADRA": "Q1"}]


def test_rejects_unreadable_encoding() -> None:
    raw = b"Name;Area\nL01;\xff\xfe\n"
    with pytest.raises(UnreadableEncodingError):
        parse_csv(raw)


def test_rejects_ambiguous_delimiter_when_candidates_tie() -> None:
    raw = b"Name;Area,Other\nL01;1,2\n"
    with pytest.raises(AmbiguousDelimiterError) as exc_info:
        parse_csv(raw)
    assert exc_info.value.context["candidate_counts"] == {",": 1, ";": 1, "\t": 0}


def test_rejects_when_no_candidate_delimiter_is_present() -> None:
    raw = b"SingleColumn\nL01\n"
    with pytest.raises(AmbiguousDelimiterError):
        parse_csv(raw)


def test_rejects_duplicate_header_columns() -> None:
    raw = b"Name;Name\nL01;L02\n"
    with pytest.raises(MalformedCSVError) as exc_info:
        parse_csv(raw)
    assert exc_info.value.context["duplicate_columns"] == ["Name"]


def test_rejects_empty_file() -> None:
    with pytest.raises(MalformedCSVError):
        parse_csv(b"")


def test_rejects_row_with_wrong_column_count() -> None:
    raw = b"Name;Area\nL01;100;extra\n"
    with pytest.raises(MalformedCSVError) as exc_info:
        parse_csv(raw)
    assert exc_info.value.context == {
        "row_number": 2,
        "expected_columns": 2,
        "actual_columns": 3,
    }


def test_rejects_too_many_columns() -> None:
    header = ";".join(f"col{i}" for i in range(201))
    raw = (header + "\n").encode("utf-8")
    with pytest.raises(MalformedCSVError) as exc_info:
        parse_csv(raw)
    assert exc_info.value.context["column_count"] == 201


def test_rejects_too_many_rows() -> None:
    header = "Name;Area\n"
    body = "".join(f"L{i};1\n" for i in range(20_001))
    raw = (header + body).encode("utf-8")
    with pytest.raises(MalformedCSVError) as exc_info:
        parse_csv(raw)
    assert exc_info.value.context["row_count"] == 20_001


def test_trailing_blank_line_is_ignored() -> None:
    raw = b"Name;Area\nL01;100\n\n"
    assert parse_csv(raw) == [{"Name": "L01", "Area": "100"}]
