"""Traceable spatial-relation strategies for lots, blocks, buildings, and facilities."""

from enum import StrEnum


class SpatialRelation(StrEnum):
    """Vocabulary shared by the interactive selection endpoint (ADR 007) and,
    later, the batch lot-block association logic in Epico 8.
    """

    INTERSECTS = "intersects"
    CONTAINS = "contains"
    WITHIN = "within"
    DWITHIN = "dwithin"
