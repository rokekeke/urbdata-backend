import uuid

import pytest

from app.domain.analysis.exceptions import IndicatorCalculationError
from app.domain.indicators.green_areas import (
    GreenAreaRecord,
    calculate_green_area_percent,
    calculate_total_green_area,
)


def _record(area_m2: float) -> GreenAreaRecord:
    return GreenAreaRecord(feature_id=uuid.uuid4(), area_m2=area_m2)


class TestTotalGreenArea:
    def test_sums_area_across_records(self) -> None:
        records = [_record(1000.0), _record(2500.5), _record(300.0)]

        result = calculate_total_green_area(records, metric_crs=31982)

        assert result.indicator_code == "green_areas.total_area"
        assert result.theme == "green_areas"
        assert result.unit == "m2"
        assert result.raw_value == pytest.approx(3800.5)
        assert len(result.contributing_feature_ids) == 3

    def test_empty_records_is_a_legitimate_zero_not_an_error(self) -> None:
        result = calculate_total_green_area([], metric_crs=31982)

        assert result.raw_value == 0.0
        assert result.contributing_feature_ids == ()


class TestGreenAreaPercent:
    def test_percent_is_over_the_gross_project_area(self) -> None:
        records = [_record(1500.0), _record(500.0)]

        result = calculate_green_area_percent(
            records, total_project_area_m2=10_000.0, metric_crs=31982
        )

        assert result.indicator_code == "green_areas.percent_of_project"
        assert result.unit == "ratio"
        assert result.raw_value == pytest.approx(0.2)
        assert result.parameters["denominator"] == "territorial.total_area"

    def test_zero_green_area_is_a_legitimate_zero_percent(self) -> None:
        result = calculate_green_area_percent(
            [], total_project_area_m2=10_000.0, metric_crs=31982
        )

        assert result.raw_value == pytest.approx(0.0)

    def test_raises_when_total_project_area_is_not_positive(self) -> None:
        with pytest.raises(IndicatorCalculationError):
            calculate_green_area_percent(
                [_record(100.0)], total_project_area_m2=0.0, metric_crs=31982
            )
