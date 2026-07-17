import uuid

import pytest

from app.domain.analysis.exceptions import DuplicateLayerError
from app.domain.geospatial.layers import resolve_single_layer_id


def test_no_candidates_returns_none() -> None:
    assert resolve_single_layer_id([], layer_type="perimetro") is None


def test_single_candidate_is_returned() -> None:
    layer_id = uuid.uuid4()

    assert resolve_single_layer_id([layer_id], layer_type="perimetro") == layer_id


def test_multiple_candidates_raise_duplicate_layer_error() -> None:
    ids = [uuid.uuid4(), uuid.uuid4()]

    with pytest.raises(DuplicateLayerError) as exc_info:
        resolve_single_layer_id(ids, layer_type="quadras")

    assert exc_info.value.code == "duplicate_layer"
    assert exc_info.value.context["layer_type"] == "quadras"
    assert set(exc_info.value.context["layer_ids"]) == {str(i) for i in ids}
