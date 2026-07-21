"""Drift guard: presentation metadata must stay 1:1 with the registry."""

import pytest

from app.domain.analysis.presentation import (
    PRESENTATIONS,
    FeatureKey,
    IndicatorGranularity,
    IndicatorPresentation,
    ValueShape,
)
from app.domain.indicators.catalog import build_registry


class TestPresentationCoverage:
    def test_every_registered_indicator_has_presentation(self) -> None:
        registered = {definition.code for definition in build_registry().all()}
        missing = registered - PRESENTATIONS.keys()
        assert not missing, f"Indicadores sem metadados de apresentacao: {sorted(missing)}"

    def test_no_presentation_for_unregistered_indicator(self) -> None:
        registered = {definition.code for definition in build_registry().all()}
        stale = PRESENTATIONS.keys() - registered
        assert not stale, f"Metadados orfaos (indicador nao registrado): {sorted(stale)}"

    def test_per_feature_indicators_declare_their_join_key(self) -> None:
        for code, presentation in PRESENTATIONS.items():
            if presentation.granularity is IndicatorGranularity.POR_FEICAO:
                assert presentation.feature_key is not None, code

    def test_known_join_keys_are_correct(self) -> None:
        # Anchors the contract the frontend relies on (nota 28, decisao 11):
        # lots.frontage_length joins by feature UUID; quadras.* and
        # parceling_efficiency join by quadra_id.
        assert PRESENTATIONS["lots.frontage_length"].feature_key is FeatureKey.FEATURE_ID
        assert PRESENTATIONS["quadras.compactness"].feature_key is FeatureKey.QUADRA_ID
        assert PRESENTATIONS["lots.parceling_efficiency"].feature_key is FeatureKey.QUADRA_ID

    def test_accented_text_survived_the_toolchain(self) -> None:
        # Regression guard for the known encoding hazard (Obsidian nota 10):
        # U+00C1 is the genuine "A with acute", not a mojibake byte pair.
        name = PRESENTATIONS["territorial.total_area"].display_name
        assert name.startswith(chr(0xC1) + "rea")
        assert chr(0xC3) + chr(0x81) not in name

    def test_value_shape_matches_granularity_for_every_entry(self) -> None:
        # Same contract test_projeto_with_feature_key_is_rejected/
        # test_por_feicao_without_feature_key_is_rejected enforce for
        # feature_key, mirrored for value_shape (indicator representation
        # review, 2026-07-20): __post_init__ already guards this per-entry
        # at import time, so a passing collection here is the real proof.
        for code, presentation in PRESENTATIONS.items():
            if presentation.granularity is IndicatorGranularity.PROJETO:
                assert presentation.value_shape in {
                    ValueShape.SCALAR,
                    ValueShape.CATEGORY_BREAKDOWN,
                    ValueShape.CATEGORICAL_LABEL,
                }, code
            else:
                assert presentation.value_shape in {
                    ValueShape.FEATURE_SERIES,
                    ValueShape.FEATURE_COMPOUND,
                }, code

    def test_known_compound_and_breakdown_shapes_are_correct(self) -> None:
        # Anchors the two cases the review set out to fix: these used to
        # fall into the frontend's generic "Configuracao composta" catch-all
        # with no real visualization.
        assert PRESENTATIONS["quadras.stats"].value_shape is ValueShape.FEATURE_COMPOUND
        assert (
            PRESENTATIONS["quadras.min_rotated_rectangle"].value_shape
            is ValueShape.FEATURE_COMPOUND
        )
        assert (
            PRESENTATIONS["territorial.area_by_category"].value_shape
            is ValueShape.CATEGORY_BREAKDOWN
        )
        assert (
            PRESENTATIONS["land_use.predominant_use"].value_shape
            is ValueShape.CATEGORICAL_LABEL
        )

    def test_category_feature_property_only_on_breakdowns(self) -> None:
        # Frente 2 (nota 52): the map paints features by this property, so
        # it must exist exactly on the four breakdown indicators and nowhere
        # else.
        with_property = {
            code: presentation.category_feature_property
            for code, presentation in PRESENTATIONS.items()
            if presentation.category_feature_property is not None
        }
        assert with_property == {
            "territorial.area_by_category": "macroarea",
            "territorial.percent_by_category": "macroarea",
            "land_use.area_by_category": "land_use",
            "land_use.percent_by_category": "land_use",
        }


class TestPresentationValidation:
    def test_empty_display_name_is_rejected(self) -> None:
        with pytest.raises(ValueError):
            IndicatorPresentation(
                "", "descricao", IndicatorGranularity.PROJETO, value_shape=ValueShape.SCALAR
            )

    def test_por_feicao_without_feature_key_is_rejected(self) -> None:
        with pytest.raises(ValueError):
            IndicatorPresentation(
                "Nome",
                "descricao",
                IndicatorGranularity.POR_FEICAO,
                value_shape=ValueShape.FEATURE_SERIES,
            )

    def test_projeto_with_feature_key_is_rejected(self) -> None:
        with pytest.raises(ValueError):
            IndicatorPresentation(
                "Nome",
                "descricao",
                IndicatorGranularity.PROJETO,
                FeatureKey.FEATURE_ID,
                value_shape=ValueShape.SCALAR,
            )

    def test_category_property_outside_breakdown_is_rejected(self) -> None:
        with pytest.raises(ValueError):
            IndicatorPresentation(
                "Nome",
                "descricao",
                IndicatorGranularity.PROJETO,
                value_shape=ValueShape.SCALAR,
                category_feature_property="macroarea",
            )

    def test_value_shape_mismatched_with_granularity_is_rejected(self) -> None:
        with pytest.raises(ValueError):
            IndicatorPresentation(
                "Nome",
                "descricao",
                IndicatorGranularity.PROJETO,
                value_shape=ValueShape.FEATURE_SERIES,
            )
        with pytest.raises(ValueError):
            IndicatorPresentation(
                "Nome",
                "descricao",
                IndicatorGranularity.POR_FEICAO,
                FeatureKey.QUADRA_ID,
                value_shape=ValueShape.SCALAR,
            )
