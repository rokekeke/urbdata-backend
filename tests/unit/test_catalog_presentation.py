"""Drift guard: presentation metadata must stay 1:1 with the registry."""

import pytest

from app.domain.analysis.presentation import (
    PRESENTATIONS,
    FeatureKey,
    IndicatorGranularity,
    IndicatorPresentation,
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


class TestPresentationValidation:
    def test_empty_display_name_is_rejected(self) -> None:
        with pytest.raises(ValueError):
            IndicatorPresentation("", "descricao", IndicatorGranularity.PROJETO)

    def test_por_feicao_without_feature_key_is_rejected(self) -> None:
        with pytest.raises(ValueError):
            IndicatorPresentation("Nome", "descricao", IndicatorGranularity.POR_FEICAO)

    def test_projeto_with_feature_key_is_rejected(self) -> None:
        with pytest.raises(ValueError):
            IndicatorPresentation(
                "Nome", "descricao", IndicatorGranularity.PROJETO, FeatureKey.FEATURE_ID
            )
