import math
import uuid

import pytest
from shapely.affinity import rotate
from shapely.geometry import Polygon

from app.domain.indicators.quadras import (
    QuadraGeometry,
    calculate_quadra_compactness,
    calculate_quadra_face_length_score,
    calculate_quadra_min_rotated_rectangle,
    calculate_quadra_orientation,
    calculate_quadra_stats,
)


def _quadra(quadra_id: str, geometry: Polygon, lot_count: int = 2) -> QuadraGeometry:
    return QuadraGeometry(
        quadra_id=quadra_id,
        geometry=geometry,
        lot_feature_ids=tuple(uuid.uuid4() for _ in range(lot_count)),
    )


SQUARE_100M = Polygon([(0, 0), (100, 0), (100, 100), (0, 100)])  # area 10_000, perimeter 400
RECT_50X20 = Polygon([(0, 0), (50, 0), (50, 20), (0, 20)])  # area 1_000, perimeter 140


class TestQuadraStats:
    def test_reports_area_perimeter_and_lot_count_per_quadra(self) -> None:
        quadras = [_quadra("Q1", SQUARE_100M, lot_count=3), _quadra("Q2", RECT_50X20, lot_count=1)]

        result = calculate_quadra_stats(quadras, metric_crs=31982)

        assert result.indicator_code == "quadras.stats"
        assert result.theme == "quadras"
        assert result.unit == "composto"
        assert result.raw_value == {
            "Q1": {
                "area_m2": pytest.approx(10_000.0),
                "perimetro_m": pytest.approx(400.0),
                "quantidade_lotes": 3,
            },
            "Q2": {
                "area_m2": pytest.approx(1_000.0),
                "perimetro_m": pytest.approx(140.0),
                "quantidade_lotes": 1,
            },
        }
        assert len(result.contributing_feature_ids) == 4

    def test_empty_quadras_is_a_legitimate_empty_result(self) -> None:
        result = calculate_quadra_stats([], metric_crs=31982)

        assert result.raw_value == {}
        assert result.contributing_feature_ids == ()


class TestQuadraCompactness:
    def test_square_scores_pi_over_four(self) -> None:
        quadras = [_quadra("Q1", SQUARE_100M)]

        result = calculate_quadra_compactness(quadras, metric_crs=31982)

        assert result.indicator_code == "quadras.compactness"
        assert result.raw_value == {"Q1": pytest.approx(math.pi / 4)}


class TestQuadraMinRotatedRectangle:
    def test_axis_aligned_square_returns_equal_edges(self) -> None:
        quadras = [_quadra("Q1", SQUARE_100M)]

        result = calculate_quadra_min_rotated_rectangle(quadras, metric_crs=31982)

        assert result.indicator_code == "quadras.min_rotated_rectangle"
        assert result.raw_value == {
            "Q1": {"comprimento_m": pytest.approx(100.0), "largura_m": pytest.approx(100.0)}
        }

    def test_rectangle_returns_the_longer_edge_as_comprimento(self) -> None:
        quadras = [_quadra("Q1", RECT_50X20)]

        result = calculate_quadra_min_rotated_rectangle(quadras, metric_crs=31982)

        assert isinstance(result.raw_value, dict)
        dims = result.raw_value["Q1"]
        assert dims["comprimento_m"] == pytest.approx(50.0)
        assert dims["largura_m"] == pytest.approx(20.0)


class TestQuadraFaceLengthScore:
    def test_short_block_scores_maximum(self) -> None:
        # 100x100 square: longer edge is 100m, below the 120m floor.
        quadras = [_quadra("Q1", SQUARE_100M)]

        result = calculate_quadra_face_length_score(quadras, metric_crs=31982)

        assert result.indicator_code == "quadras.face_length_score"
        assert result.raw_value == {"Q1": pytest.approx(1.0)}
        assert result.warnings == ()

    def test_score_decays_linearly_between_ideal_and_legal_limit(self) -> None:
        # 185x1m rectangle: longer edge is exactly halfway between 120 and 250,
        # so the score is exactly halfway between 1.0 and the 0.1 floor.
        rect = Polygon([(0, 0), (185, 0), (185, 1), (0, 1)])
        quadras = [_quadra("Q1", rect)]

        result = calculate_quadra_face_length_score(quadras, metric_crs=31982)

        assert result.raw_value == {"Q1": pytest.approx(0.55)}
        assert result.warnings == ()

    def test_face_at_exactly_legal_limit_scores_the_floor_without_warning(self) -> None:
        rect = Polygon([(0, 0), (250, 0), (250, 1), (0, 1)])
        quadras = [_quadra("Q1", rect)]

        result = calculate_quadra_face_length_score(quadras, metric_crs=31982)

        assert result.raw_value == {"Q1": pytest.approx(0.1)}
        assert result.warnings == ()

    def test_face_beyond_legal_limit_scores_the_floor_and_warns(self) -> None:
        rect = Polygon([(0, 0), (300, 0), (300, 1), (0, 1)])
        quadras = [_quadra("Q1", rect, lot_count=2)]

        result = calculate_quadra_face_length_score(quadras, metric_crs=31982)

        assert result.raw_value == {"Q1": pytest.approx(0.1)}
        assert len(result.warnings) == 1
        warning = result.warnings[0]
        assert warning.code == "block_face_out_of_compliance"
        assert set(warning.feature_ids) == set(quadras[0].lot_feature_ids)

    def test_base_warnings_are_preserved_alongside_compliance_warnings(self) -> None:
        from app.domain.analysis.warnings import AnalysisWarning, WarningSeverity

        base_warning = AnalysisWarning(
            code="lot_without_quadra", message="...", feature_ids=(), severity=WarningSeverity.INFO
        )
        rect = Polygon([(0, 0), (300, 0), (300, 1), (0, 1)])
        quadras = [_quadra("Q1", rect)]

        result = calculate_quadra_face_length_score(
            quadras, metric_crs=31982, warnings=(base_warning,)
        )

        assert base_warning in result.warnings
        assert any(w.code == "block_face_out_of_compliance" for w in result.warnings)


class TestQuadraOrientation:
    def test_axis_aligned_rectangle_reports_zero_deviation(self) -> None:
        # RECT_50X20's longer edge runs from (0,0) to (50,0) - due east.
        quadras = [_quadra("Q1", RECT_50X20)]

        result = calculate_quadra_orientation(quadras, metric_crs=31982)

        assert result.indicator_code == "quadras.orientation"
        assert result.unit == "graus"
        assert result.raw_value == {"Q1": pytest.approx(0.0, abs=1e-9)}

    def test_perpendicular_rectangle_reports_ninety_degrees(self) -> None:
        quadras = [_quadra("Q1", rotate(RECT_50X20, 90, origin=(0, 0)))]

        result = calculate_quadra_orientation(quadras, metric_crs=31982)

        assert result.raw_value == {"Q1": pytest.approx(90.0)}

    def test_forty_five_degree_rectangle_reports_forty_five(self) -> None:
        quadras = [_quadra("Q1", rotate(RECT_50X20, 45, origin=(0, 0)))]

        result = calculate_quadra_orientation(quadras, metric_crs=31982)

        assert result.raw_value == {"Q1": pytest.approx(45.0)}

    def test_matches_the_certification_fifteen_degree_threshold(self) -> None:
        # CTE/Methafora and LEED-ND both check "quadra axis within 15
        # degrees of East-West" - this is the exact boundary value.
        quadras = [_quadra("Q1", rotate(RECT_50X20, 15, origin=(0, 0)))]

        result = calculate_quadra_orientation(quadras, metric_crs=31982)

        assert result.raw_value == {"Q1": pytest.approx(15.0)}

    def test_folds_angles_past_ninety_to_the_shorter_arc(self) -> None:
        # A rectangle at 170 degrees is the same line as one at 10 degrees
        # (a line has no direction) - this exercises the wraparound fold,
        # not just a "nice" angle that would pass even with buggy math.
        quadras = [_quadra("Q1", rotate(RECT_50X20, 170, origin=(0, 0)))]

        result = calculate_quadra_orientation(quadras, metric_crs=31982)

        assert result.raw_value == {"Q1": pytest.approx(10.0)}

    def test_axis_aligned_square_pins_shapelys_deterministic_tie_break(self) -> None:
        # SQUARE_100M's two edges are equally "major" - Shapely's
        # minimum_rotated_rectangle happens to return the north-south edge
        # first for this shape, so the tie resolves to 90 here. This test
        # pins that deterministic (if not hand-derivable) behavior, not a
        # claim that 90 is "the" correct orientation for a square - either
        # axis is equally valid when the two edges are exactly equal.
        quadras = [_quadra("Q1", SQUARE_100M)]

        result = calculate_quadra_orientation(quadras, metric_crs=31982)

        assert result.raw_value == {"Q1": pytest.approx(90.0)}

    def test_rotated_square_gives_the_same_deviation_regardless_of_tie_break(self) -> None:
        # Once genuinely rotated 45 degrees, both edges fold to the same
        # deviation - the tie-break choice stops mattering.
        quadras = [_quadra("Q1", rotate(SQUARE_100M, 45, origin=(0, 0)))]

        result = calculate_quadra_orientation(quadras, metric_crs=31982)

        assert result.raw_value == {"Q1": pytest.approx(45.0)}
