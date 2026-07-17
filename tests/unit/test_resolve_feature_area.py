import math
import uuid

import pytest
from shapely.geometry import Polygon

from app.domain.geospatial.geometry import resolve_feature_area

SQUARE_100M = Polygon([(0, 0), (100, 0), (100, 100), (0, 100)])  # 10_000 m2


def test_no_reference_area_uses_the_geometric_value() -> None:
    feature_id = uuid.uuid4()

    resolved = resolve_feature_area(feature_id, SQUARE_100M, None, crs=31982)

    assert resolved.area_m2 == pytest.approx(10_000.0)
    assert resolved.warning is None


def test_reference_within_threshold_keeps_geometric_value_without_a_warning() -> None:
    feature_id = uuid.uuid4()

    resolved = resolve_feature_area(feature_id, SQUARE_100M, 10_200.0, crs=31982)

    assert resolved.area_m2 == pytest.approx(10_000.0)
    assert resolved.warning is None


def test_reference_diverging_past_threshold_keeps_geometric_value_and_warns() -> None:
    feature_id = uuid.uuid4()

    resolved = resolve_feature_area(feature_id, SQUARE_100M, 8_000.0, crs=31982)

    assert resolved.area_m2 == pytest.approx(10_000.0)
    assert resolved.warning is not None
    assert resolved.warning.code == "area_reference_divergence"
    assert resolved.warning.feature_ids == (feature_id,)


def test_custom_threshold_is_respected() -> None:
    feature_id = uuid.uuid4()

    resolved = resolve_feature_area(
        feature_id, SQUARE_100M, 9_500.0, crs=31982, divergence_threshold=0.01
    )

    assert resolved.warning is not None


def test_nan_reference_is_treated_as_missing() -> None:
    # A GeoDataFrame column with mixed None/float commonly stores missing
    # values as NaN rather than None - callers reading a row straight from
    # one (land_use.py, green_areas.py) rely on this being handled here.
    feature_id = uuid.uuid4()

    resolved = resolve_feature_area(feature_id, SQUARE_100M, math.nan, crs=31982)

    assert resolved.area_m2 == pytest.approx(10_000.0)
    assert resolved.warning is None
