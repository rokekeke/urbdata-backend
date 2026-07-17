import math
import uuid

import pytest
from shapely.geometry import Polygon

from app.domain.indicators.quadras import (
    QuadraGeometry,
    calculate_quadra_compactness,
    calculate_quadra_face_length_score,
    calculate_quadra_min_rotated_rectangle,
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
