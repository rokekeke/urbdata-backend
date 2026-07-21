"""Safe CSV parsing for the combined GeoJSON+CSV import (nota 53/54).

Domain-pure: no database access, no knowledge of layers or features. Takes
the raw bytes exactly as read from the uploaded file and returns a list of
dicts (one per data row, keyed by header) or raises `CSVParseError` with
enough context to build an actionable API error message. Never guesses past
an unreadable encoding or an ambiguous delimiter (rule 6: no silent
correction) - the confirmed-good shape from the sample evaluated in nota 53
is UTF-8 (with or without BOM) and `;` as the delimiter, but this accepts
any of the three candidate delimiters, not just that one.
"""

import csv
import io
from collections.abc import Mapping
from typing import Any

_CANDIDATE_DELIMITERS = (",", ";", "\t")

# Generous relative to the largest real project measured so far (Vandressen,
# 387 features, nota 28) - not a domain requirement, just an early guard
# against a misparsed/corrupted file producing an absurd row or column count.
_MAX_ROWS = 20_000
_MAX_COLUMNS = 200


class CSVParseError(Exception):
    code = "csv_parse_error"

    def __init__(self, message: str, *, context: Mapping[str, Any] | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.context = dict(context or {})


class UnreadableEncodingError(CSVParseError):
    code = "csv_unreadable_encoding"


class AmbiguousDelimiterError(CSVParseError):
    code = "csv_ambiguous_delimiter"


class MalformedCSVError(CSVParseError):
    code = "csv_malformed"


def parse_csv(raw: bytes) -> list[dict[str, str]]:
    """Parse *raw* CSV bytes into one dict per data row, keyed by header.

    Raises a `CSVParseError` subclass instead of returning a partial or
    best-guess result - the caller (eventually the upload route, b6) is
    expected to surface `.code`/`.message`/`.context` as a 400 response.
    """
    text = _decode(raw)
    lines = text.splitlines()
    if not lines or not lines[0].strip():
        raise MalformedCSVError("Arquivo CSV esta vazio.")

    delimiter = _detect_delimiter(lines[0])
    reader = csv.reader(io.StringIO(text), delimiter=delimiter)
    all_rows = [row for row in reader if row]

    header = all_rows[0]
    _validate_header(header)

    data_rows = all_rows[1:]
    if len(data_rows) > _MAX_ROWS:
        raise MalformedCSVError(
            f"CSV com {len(data_rows)} linhas de dados excede o limite de {_MAX_ROWS}.",
            context={"row_count": len(data_rows), "limit": _MAX_ROWS},
        )

    records: list[dict[str, str]] = []
    for row_number, row in enumerate(data_rows, start=2):
        if len(row) != len(header):
            raise MalformedCSVError(
                f"Linha {row_number} do CSV tem {len(row)} colunas, "
                f"mas o cabecalho define {len(header)}.",
                context={
                    "row_number": row_number,
                    "expected_columns": len(header),
                    "actual_columns": len(row),
                },
            )
        records.append(dict(zip(header, row, strict=True)))

    return records


def _decode(raw: bytes) -> str:
    try:
        return raw.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise UnreadableEncodingError(
            "Nao foi possivel ler a codificacao do arquivo CSV. "
            "Salve o arquivo como UTF-8 (com ou sem BOM) e tente novamente.",
            context={"byte_offset": exc.start},
        ) from exc


def _validate_header(header: list[str]) -> None:
    if len(header) > _MAX_COLUMNS:
        raise MalformedCSVError(
            f"CSV com {len(header)} colunas excede o limite de {_MAX_COLUMNS}.",
            context={"column_count": len(header), "limit": _MAX_COLUMNS},
        )
    seen: set[str] = set()
    duplicates: set[str] = set()
    for column in header:
        if column in seen:
            duplicates.add(column)
        seen.add(column)
    if duplicates:
        raise MalformedCSVError(
            "O cabecalho do CSV tem colunas repetidas: "
            f"{', '.join(sorted(duplicates))}.",
            context={"duplicate_columns": sorted(duplicates)},
        )


def _detect_delimiter(header_line: str) -> str:
    counts = {delimiter: header_line.count(delimiter) for delimiter in _CANDIDATE_DELIMITERS}
    best = max(counts.values())
    if best == 0 or sum(1 for count in counts.values() if count == best) > 1:
        raise AmbiguousDelimiterError(
            "Nao foi possivel identificar o separador de colunas do CSV. "
            "Use virgula (,), ponto e virgula (;) ou tabulacao como separador.",
            context={"candidate_counts": counts},
        )
    return max(counts, key=lambda delimiter: counts[delimiter])
