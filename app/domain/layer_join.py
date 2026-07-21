"""Join geometry features to CSV attribute rows by an explicit key (nota
53/54, subetapa b3) - domain-pure, no database access.

Takes keys already resolved by the caller: the geometry side is whatever
`geometry_join_key` (a GeoJSON property name) or `feature.id` resolved to
for each feature, in feature order; the attribute side is the parsed CSV
rows from `app.domain.csv_import.parse_csv`. Never matches by row/feature
position - only by key equality, and only exact equality (rule 6: no
approximation, text search or case correction on the key).

Every rule the export team locked down is checked and collected before
raising, not fail-fast - the same philosophy as `MapDocument`'s contextual
validation - so a rejected upload's error lists everything wrong at once
instead of one problem per retry.
"""

from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any


class AttributeJoinError(Exception):
    code = "attribute_join_mismatch"

    def __init__(self, message: str, *, context: Mapping[str, Any] | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.context = dict(context or {})


@dataclass(frozen=True)
class MatchedPair:
    """One geometry feature (by its index in the original feature list)
    paired with its matching CSV row."""

    geometry_index: int
    attribute_row: Mapping[str, str]


@dataclass(frozen=True)
class JoinSummary:
    geometry_count: int
    attribute_count: int
    matched: int
    missing_geometry_keys: tuple[str, ...]
    missing_attribute_keys: tuple[str, ...]
    duplicate_geometry_keys: tuple[str, ...]
    duplicate_attribute_keys: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        """Matches the `project_layers.join_summary` shape exactly (nota 54)."""
        return {
            "geometry_count": self.geometry_count,
            "attribute_count": self.attribute_count,
            "matched": self.matched,
            "missing_geometry_keys": list(self.missing_geometry_keys),
            "missing_attribute_keys": list(self.missing_attribute_keys),
            "duplicate_geometry_keys": list(self.duplicate_geometry_keys),
            "duplicate_attribute_keys": list(self.duplicate_attribute_keys),
        }


@dataclass(frozen=True)
class JoinResult:
    matched: tuple[MatchedPair, ...]
    summary: JoinSummary


def resolve_geometry_join_keys(
    features: Sequence[Mapping[str, Any]], geometry_join_key: str | None
) -> list[str | None]:
    """Resolve each GeoJSON feature's join key, in feature order: the
    `geometry_join_key` property when given, else `feature.id` (nota 53/54
    contract default - the same value that becomes `Feature.external_id` at
    persistence). Converts to `str` either way, since the CSV side
    (`app.domain.csv_import.parse_csv`) always produces string values and a
    JSON number vs. its string form is not the kind of mismatch rule 6
    guards against - a feature/row with no usable value resolves to `None`
    (an empty key, caught by `join_geometry_and_attributes`), never guessed.
    """
    if geometry_join_key is None:
        return [
            str(feature["id"]) if feature.get("id") is not None else None
            for feature in features
        ]
    resolved: list[str | None] = []
    for feature in features:
        properties = feature.get("properties") or {}
        value = properties.get(geometry_join_key)
        resolved.append(str(value) if value is not None else None)
    return resolved


def join_geometry_and_attributes(
    geometry_keys: Sequence[str | None],
    attribute_rows: Sequence[Mapping[str, str]],
    attributes_join_key: str,
) -> JoinResult:
    """Raises `AttributeJoinError` unless every geometry feature and every
    CSV row has a non-empty key, no key repeats on either side, and the two
    sides match exactly 1:1. On success, `JoinResult.matched` has exactly
    one `MatchedPair` per input geometry feature, in the same order.
    """
    attribute_keys = [row.get(attributes_join_key) for row in attribute_rows]

    # Positional, not key-valued: an empty key has no value worth reporting,
    # only a location. Both 0-based into the sequences this function
    # received - a human-facing CSV line number (accounting for the header
    # row) is an API-layer concern, not this pure function's.
    empty_geometry_feature_indices = [
        index for index, key in enumerate(geometry_keys) if not key
    ]
    empty_attribute_row_indices = [index for index, key in enumerate(attribute_keys) if not key]

    geometry_key_counts = Counter(key for key in geometry_keys if key)
    attribute_key_counts = Counter(key for key in attribute_keys if key)
    duplicate_geometry_keys = sorted(
        key for key, count in geometry_key_counts.items() if count > 1
    )
    duplicate_attribute_keys = sorted(
        key for key, count in attribute_key_counts.items() if count > 1
    )

    geometry_key_set = set(geometry_key_counts)
    attribute_key_set = set(attribute_key_counts)
    missing_geometry_keys = sorted(attribute_key_set - geometry_key_set)
    missing_attribute_keys = sorted(geometry_key_set - attribute_key_set)

    if (
        empty_geometry_feature_indices
        or empty_attribute_row_indices
        or duplicate_geometry_keys
        or duplicate_attribute_keys
        or missing_geometry_keys
        or missing_attribute_keys
    ):
        raise AttributeJoinError(
            "A geometria e os atributos do CSV nao correspondem 1:1 pela chave informada.",
            context={
                "empty_geometry_feature_indices": empty_geometry_feature_indices,
                "empty_attribute_row_indices": empty_attribute_row_indices,
                "duplicate_geometry_keys": duplicate_geometry_keys,
                "duplicate_attribute_keys": duplicate_attribute_keys,
                "missing_geometry_keys": missing_geometry_keys,
                "missing_attribute_keys": missing_attribute_keys,
            },
        )

    attribute_row_by_key = {row[attributes_join_key]: row for row in attribute_rows}
    matched = tuple(
        MatchedPair(geometry_index=index, attribute_row=attribute_row_by_key[key])
        for index, key in enumerate(geometry_keys)
        if key is not None
    )
    summary = JoinSummary(
        geometry_count=len(geometry_keys),
        attribute_count=len(attribute_rows),
        matched=len(matched),
        missing_geometry_keys=(),
        missing_attribute_keys=(),
        duplicate_geometry_keys=(),
        duplicate_attribute_keys=(),
    )
    return JoinResult(matched=matched, summary=summary)
