import uuid

import pytest

from app.domain.analysis.warnings import WarningSeverity
from app.domain.indicators.territorial import (
    TerritorialAreaRecord,
    calculate_territorial_area_by_category,
    calculate_territorial_percent_by_category,
)


def _record(
    area_m2: float, macroarea: str | None, parcelavel: bool | None
) -> TerritorialAreaRecord:
    return TerritorialAreaRecord(
        feature_id=uuid.uuid4(), area_m2=area_m2, macroarea=macroarea, parcelavel=parcelavel
    )


class TestAreaByCategory:
    def test_sums_area_per_macroarea_category(self) -> None:
        records = [
            _record(1000.0, "lote", True),
            _record(500.0, "lote", True),
            _record(300.0, "sistema_viario", False),
        ]

        result = calculate_territorial_area_by_category(records, metric_crs=31982)

        assert result.indicator_code == "territorial.area_by_category"
        assert result.theme == "territorial"
        assert result.unit == "m2"
        assert result.raw_value == {"lote": 1500.0, "sistema_viario": 300.0}
        assert len(result.contributing_feature_ids) == 3

    def test_unclassified_features_get_their_own_nulo_bucket(self) -> None:
        records = [_record(1000.0, "lote", True), _record(250.0, None, None)]

        result = calculate_territorial_area_by_category(records, metric_crs=31982)

        assert result.raw_value == {"lote": 1000.0, "nulo": 250.0}

    def test_explicit_nulo_tag_joins_the_same_bucket_as_unclassified(self) -> None:
        records = [_record(100.0, "nulo", None), _record(50.0, None, None)]

        result = calculate_territorial_area_by_category(records, metric_crs=31982)

        assert result.raw_value == {"nulo": 150.0}

    def test_includes_non_parcelavel_categories_unlike_the_percent_indicator(self) -> None:
        records = [_record(300.0, "app", False)]

        result = calculate_territorial_area_by_category(records, metric_crs=31982)

        assert result.raw_value == {"app": 300.0}


class TestPercentByCategory:
    def test_percent_is_restricted_to_parcelavel_records_for_both_terms(self) -> None:
        records = [
            _record(750.0, "lote", True),
            _record(250.0, "avl", True),
            # Non-parcelavel: counted in area_by_category but not here.
            _record(5000.0, "sistema_viario", False),
            _record(1000.0, "app", False),
        ]

        result = calculate_territorial_percent_by_category(records, metric_crs=31982)

        assert result.indicator_code == "territorial.percent_by_category"
        assert result.raw_value == {
            "lote": pytest.approx(0.75),
            "avl": pytest.approx(0.25),
        }
        assert "sistema_viario" not in result.raw_value
        assert result.parameters["denominator"] == "parcelavel_area"

    def test_percentages_sum_to_one_over_the_parcelavel_universe(self) -> None:
        records = [
            _record(300.0, "lote", True),
            _record(200.0, "aci", True),
            _record(9999.0, "sistema_viario", False),
        ]

        result = calculate_territorial_percent_by_category(records, metric_crs=31982)

        assert isinstance(result.raw_value, dict)
        assert sum(result.raw_value.values()) == pytest.approx(1.0)

    def test_parcelavel_none_is_treated_as_not_parcelavel(self) -> None:
        records = [_record(500.0, "lote", True), _record(500.0, "lote", None)]

        result = calculate_territorial_percent_by_category(records, metric_crs=31982)

        assert result.raw_value == {"lote": pytest.approx(1.0)}

    def test_degrades_to_empty_when_nothing_is_parcelavel(self) -> None:
        # ADR 013: a gleba with zero parcelavel area (e.g. entirely APP) is a
        # legitimate degenerate case - warn and complete, don't fail the run.
        records = [_record(500.0, "sistema_viario", False)]

        result = calculate_territorial_percent_by_category(records, metric_crs=31982)

        assert result.raw_value == {}
        assert result.contributing_feature_ids == ()
        assert [w.code for w in result.warnings] == ["no_parcelavel_area"]
        assert result.warnings[0].severity == WarningSeverity.WARNING
