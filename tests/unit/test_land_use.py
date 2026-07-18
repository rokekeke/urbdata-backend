import math
import uuid

import pytest

from app.config.land_use_mapping import LandUseCategory
from app.domain.analysis.warnings import WarningSeverity
from app.domain.indicators.land_use import (
    LotAreaRecord,
    calculate_area_by_category,
    calculate_diversity_shannon,
    calculate_percent_by_category,
    calculate_predominant_use,
    classify_land_use,
)


def _lot(area_m2: float, raw_land_use: str | None) -> LotAreaRecord:
    return LotAreaRecord(feature_id=uuid.uuid4(), area_m2=area_m2, raw_land_use=raw_land_use)


class TestClassifyLandUse:
    def test_single_recognized_use_resolves_directly(self) -> None:
        assert classify_land_use("residencial") == LandUseCategory.RESIDENCIAL

    def test_is_case_and_accent_insensitive(self) -> None:
        assert classify_land_use("SERVI" + chr(0xC7) + "OS") == LandUseCategory.SERVICOS
        assert classify_land_use("  Comercial  ") == LandUseCategory.COMERCIAL

    def test_multiple_distinct_uses_are_always_misto(self) -> None:
        assert classify_land_use("residencial;comercial") == LandUseCategory.MISTO

    def test_repeating_the_same_use_is_not_misto(self) -> None:
        assert classify_land_use("residencial;residencial") == LandUseCategory.RESIDENCIAL

    def test_explicit_misto_alias_works_directly(self) -> None:
        assert classify_land_use("misto") == LandUseCategory.MISTO

    def test_unrecognized_or_empty_returns_none(self) -> None:
        assert classify_land_use(None) is None
        assert classify_land_use("") is None
        assert classify_land_use("nulo") is None
        assert classify_land_use("xyz-nao-existe") is None


class TestAreaAndPercentByCategory:
    def test_area_sums_per_category_and_excludes_unclassified(self) -> None:
        lots = [
            _lot(1000.0, "residencial"),
            _lot(500.0, "residencial"),
            _lot(2000.0, "comercial"),
            _lot(999.0, None),
            _lot(111.0, "nulo"),
        ]

        result = calculate_area_by_category(lots, metric_crs=31982)

        assert result.indicator_code == "land_use.area_by_category"
        assert result.unit == "m2"
        assert result.raw_value == {"residencial": 1500.0, "comercial": 2000.0}
        assert len(result.contributing_feature_ids) == 3

    def test_percent_is_over_classified_area_only(self) -> None:
        lots = [_lot(300.0, "residencial"), _lot(700.0, "comercial"), _lot(5000.0, None)]

        result = calculate_percent_by_category(lots, metric_crs=31982)

        assert result.raw_value == {
            "residencial": pytest.approx(0.3),
            "comercial": pytest.approx(0.7),
        }

    def test_unclassified_lots_produce_an_info_warning(self) -> None:
        unclassified = _lot(999.0, None)
        lots = [_lot(300.0, "residencial"), unclassified]

        result = calculate_area_by_category(lots, metric_crs=31982)

        assert len(result.warnings) == 1
        warning = result.warnings[0]
        assert warning.code == "lot_without_land_use"
        assert warning.severity == WarningSeverity.INFO
        assert warning.feature_ids == (unclassified.feature_id,)

    def test_percent_degrades_to_empty_when_nothing_is_classified(self) -> None:
        # ADR 013: an empty qualifying universe completes with a warning
        # instead of failing the whole run.
        lot = _lot(100.0, None)

        result = calculate_percent_by_category([lot], metric_crs=31982)

        assert result.raw_value == {}
        assert result.contributing_feature_ids == ()
        assert [w.code for w in result.warnings] == ["lot_without_land_use"]
        assert result.warnings[0].feature_ids == (lot.feature_id,)


class TestPredominantUse:
    def test_returns_the_category_with_the_most_area(self) -> None:
        lots = [_lot(100.0, "residencial"), _lot(900.0, "comercial")]

        result = calculate_predominant_use(lots, metric_crs=31982)

        assert result.raw_value == "comercial"
        assert result.warnings == ()

    def test_exact_tie_returns_none_with_an_info_warning(self) -> None:
        lots = [_lot(500.0, "residencial"), _lot(500.0, "comercial")]

        result = calculate_predominant_use(lots, metric_crs=31982)

        assert result.raw_value is None
        assert len(result.warnings) == 1
        assert result.warnings[0].code == "predominant_use_tie"

    def test_degrades_to_none_when_nothing_is_classified(self) -> None:
        result = calculate_predominant_use([_lot(100.0, None)], metric_crs=31982)

        assert result.raw_value is None
        assert [w.code for w in result.warnings] == ["lot_without_land_use"]

    def test_tie_keeps_the_unclassified_warning_too(self) -> None:
        lots = [_lot(500.0, "residencial"), _lot(500.0, "comercial"), _lot(50.0, None)]

        result = calculate_predominant_use(lots, metric_crs=31982)

        assert result.raw_value is None
        assert [w.code for w in result.warnings] == [
            "lot_without_land_use",
            "predominant_use_tie",
        ]


class TestDiversityShannon:
    def test_two_equal_categories_match_ln2(self) -> None:
        lots = [_lot(500.0, "residencial"), _lot(500.0, "comercial")]

        result = calculate_diversity_shannon(lots, metric_crs=31982)

        assert result.raw_value == pytest.approx(math.log(2))

    def test_a_single_category_has_zero_diversity(self) -> None:
        lots = [_lot(500.0, "residencial"), _lot(300.0, "residencial")]

        result = calculate_diversity_shannon(lots, metric_crs=31982)

        assert result.raw_value == pytest.approx(0.0, abs=1e-9)

    def test_degrades_to_none_when_nothing_is_classified(self) -> None:
        result = calculate_diversity_shannon([_lot(100.0, None)], metric_crs=31982)

        assert result.raw_value is None
        assert [w.code for w in result.warnings] == ["lot_without_land_use"]
