"""Presentation metadata for catalog indicators (Fase 0 do roadmap, nota 28/29).

Separated from `IndicatorDefinition` on purpose: the engine never needs
display names, and the API composes registry + presentation at the edge.
A drift test (`tests/unit/test_catalog_presentation.py`) keeps this table
1:1 with the registered catalog.

Accented Portuguese text uses \\uXXXX escapes so the source file stays pure
ASCII - the local toolchain has mangled literal accented characters in .py
files before (see Obsidian note 10 and the project memory).
"""

from dataclasses import dataclass, field
from enum import StrEnum


class IndicatorGranularity(StrEnum):
    """Spatial granularity of the indicator's persisted value."""

    PROJETO = "projeto"
    POR_FEICAO = "por_feicao"


class FeatureKey(StrEnum):
    """What keys a `por_feicao` dict value: feature UUIDs (joinable against
    `feature.id` in the layer GeoJSON) or `quadra_id` grouping strings
    (joinable against the derived quadras layer's `quadra_id` property)."""

    FEATURE_ID = "feature_id"
    QUADRA_ID = "quadra_id"


class ValueShape(StrEnum):
    """Structure of the raw value this indicator persists (`value`/
    `value_json` in `indicator_results`) - drives which visualization the
    frontend picks for it (indicator representation review, 2026-07-20).
    Independent of `unit`/number formatting, which stays on the
    calculation result (`IndicatorDefinition.unit`), not here.

    - SCALAR: one number for the whole project.
    - CATEGORY_BREAKDOWN: dict[categoria -> numero] for the whole project
      (e.g. area/percentual por macroarea ou uso do solo).
    - CATEGORICAL_LABEL: a single category name for the whole project (or
      null on a tie/no data) - not a number at all.
    - FEATURE_SERIES: one number per feature/quadra (`por_feicao`) - the
      existing min/mean/max + ranked-list view already suits this.
    - FEATURE_COMPOUND: one compound record (dict of sub-fields) per
      feature/quadra (`por_feicao`) - needs a table, not a single bar.
    """

    SCALAR = "scalar"
    CATEGORY_BREAKDOWN = "category_breakdown"
    CATEGORICAL_LABEL = "categorical_label"
    FEATURE_SERIES = "feature_series"
    FEATURE_COMPOUND = "feature_compound"


_PROJETO_SHAPES = frozenset(
    {ValueShape.SCALAR, ValueShape.CATEGORY_BREAKDOWN, ValueShape.CATEGORICAL_LABEL}
)
_POR_FEICAO_SHAPES = frozenset({ValueShape.FEATURE_SERIES, ValueShape.FEATURE_COMPOUND})


@dataclass(frozen=True, slots=True)
class IndicatorPresentation:
    display_name: str
    description: str
    granularity: IndicatorGranularity
    feature_key: FeatureKey | None = None
    # Keyword-only (not just "has a default"): every catalog entry must
    # state its shape explicitly - a silently-defaulted SCALAR would hide
    # the exact compound-value cases (quadras.stats, min_rotated_rectangle)
    # this field exists to catch.
    value_shape: ValueShape = field(kw_only=True)
    # Only for CATEGORY_BREAKDOWN: the per-feature property (in the layer's
    # GeoJSON) whose values are this breakdown's categories - lets the map
    # paint each feature by its category even though the indicator itself
    # is project-level (Frente 2 da revisao de representacao, nota 52).
    # The GeoJSON carries the RAW mapped value (e.g. "SISTEMA VIARIO"), not
    # the slug - clients must normalize before joining, same rule as
    # `normalize_key`.
    category_feature_property: str | None = field(default=None, kw_only=True)
    # An internal metric feeds a map representation and/or a warning
    # (e.g. quadras.face_length_score paints the map and raises
    # block_face_out_of_compliance), but is not itself a highlighted
    # dashboard card - parecer da revisao teorica, nota Obsidian 71/87/88
    # (22/07/2026). Still fully queryable via GET /catalog/indicators; the
    # frontend is what decides not to list it among the theme's cards.
    internal: bool = field(default=False, kw_only=True)

    def __post_init__(self) -> None:
        if not self.display_name or not self.description:
            raise ValueError("display_name and description must not be empty")
        if self.granularity is IndicatorGranularity.POR_FEICAO and self.feature_key is None:
            raise ValueError("por_feicao indicators must declare a feature_key")
        if self.granularity is IndicatorGranularity.PROJETO and self.feature_key is not None:
            raise ValueError("projeto indicators must not declare a feature_key")
        if (
            self.granularity is IndicatorGranularity.PROJETO
            and self.value_shape not in _PROJETO_SHAPES
        ):
            raise ValueError(f"granularity=projeto requires value_shape in {_PROJETO_SHAPES}")
        if (
            self.granularity is IndicatorGranularity.POR_FEICAO
            and self.value_shape not in _POR_FEICAO_SHAPES
        ):
            raise ValueError(f"granularity=por_feicao requires value_shape in {_POR_FEICAO_SHAPES}")
        if (
            self.category_feature_property is not None
            and self.value_shape is not ValueShape.CATEGORY_BREAKDOWN
        ):
            raise ValueError(
                "category_feature_property is only valid for value_shape=category_breakdown"
            )


_P = IndicatorPresentation
_PROJETO = IndicatorGranularity.PROJETO
_POR_FEICAO = IndicatorGranularity.POR_FEICAO
_SCALAR = ValueShape.SCALAR
_CATEGORY_BREAKDOWN = ValueShape.CATEGORY_BREAKDOWN
_CATEGORICAL_LABEL = ValueShape.CATEGORICAL_LABEL
_FEATURE_SERIES = ValueShape.FEATURE_SERIES
_FEATURE_COMPOUND = ValueShape.FEATURE_COMPOUND

PRESENTATIONS: dict[str, IndicatorPresentation] = {
    "territorial.total_area": _P(
        "Área total do projeto",
        "Área bruta do perímetro da matrícula, em metros quadrados, "
        "medida em CRS métrico.",
        _PROJETO,
        value_shape=_SCALAR,
    ),
    "territorial.perimeter": _P(
        "Perímetro do projeto",
        "Comprimento do limite consolidado do projeto, em metros.",
        _PROJETO,
        value_shape=_SCALAR,
    ),
    "territorial.compactness": _P(
        "Compacidade do perímetro",
        "Índice isoperimétrico de Polsby-Popper (círculo = 1,0).",
        _PROJETO,
        value_shape=_SCALAR,
    ),
    "territorial.area_by_category": _P(
        "Área por macroárea",
        "Inventário de área por categoria territorial (Lote, Sistema "
        "viário, AVL, APP, ACI, Nulo), incluindo não parceláveis.",
        _PROJETO,
        value_shape=_CATEGORY_BREAKDOWN,
        category_feature_property="macroarea",
    ),
    "territorial.percent_by_category": _P(
        "Percentual por macroárea (parcelável)",
        "Distribuição percentual da área parcelável por categoria; "
        "soma ~100% do universo parcelável.",
        _PROJETO,
        value_shape=_CATEGORY_BREAKDOWN,
        category_feature_property="macroarea",
    ),
    "land_use.area_by_category": _P(
        "Área por uso do solo",
        "Área dos lotes por categoria de uso (residencial, comercial, "
        "serviços, institucional, industrial, misto).",
        _PROJETO,
        value_shape=_CATEGORY_BREAKDOWN,
        category_feature_property="land_use",
    ),
    "land_use.percent_by_category": _P(
        "Percentual por uso do solo",
        "Distribuição percentual sobre a área classificada dos lotes.",
        _PROJETO,
        value_shape=_CATEGORY_BREAKDOWN,
        category_feature_property="land_use",
    ),
    "land_use.predominant_use": _P(
        "Uso predominante",
        "Categoria com maior área classificada; empate retorna vazio com aviso.",
        _PROJETO,
        value_shape=_CATEGORICAL_LABEL,
    ),
    "land_use.diversity_shannon": _P(
        "Diversidade de usos (Shannon)",
        "Índice de Shannon-Wiener sobre proporções de área por uso.",
        _PROJETO,
        value_shape=_SCALAR,
    ),
    "green_areas.total_area": _P(
        "Área verde total",
        "Soma das áreas AVL do projeto, em metros quadrados.",
        _PROJETO,
        value_shape=_SCALAR,
    ),
    "green_areas.percent_of_project": _P(
        "Área verde sobre o projeto",
        "Razão entre a área verde e a área bruta do projeto.",
        _PROJETO,
        value_shape=_SCALAR,
    ),
    "green_areas.total_area_with_app": _P(
        "Área verde total (com APP)",
        "Soma das áreas AVL e APP do projeto, em metros quadrados - "
        "mostra o potencial paisagístico que a APP acrescenta.",
        _PROJETO,
        value_shape=_SCALAR,
    ),
    "green_areas.percent_of_project_with_app": _P(
        "Área verde sobre o projeto (com APP)",
        "Razão entre a área verde (AVL+APP) e a área bruta do projeto.",
        _PROJETO,
        value_shape=_SCALAR,
    ),
    "quadras.stats": _P(
        "Estatísticas por quadra",
        "Área, perímetro e lotes contribuintes de cada quadra derivada.",
        _POR_FEICAO,
        FeatureKey.QUADRA_ID,
        value_shape=_FEATURE_COMPOUND,
    ),
    "quadras.compactness": _P(
        "Compacidade por quadra",
        "Índice de Polsby-Popper de cada quadra derivada.",
        _POR_FEICAO,
        FeatureKey.QUADRA_ID,
        value_shape=_FEATURE_SERIES,
    ),
    "quadras.min_rotated_rectangle": _P(
        "Dimensões por quadra",
        "Comprimento e largura do retângulo mínimo rotacionado de cada quadra.",
        _POR_FEICAO,
        FeatureKey.QUADRA_ID,
        value_shape=_FEATURE_COMPOUND,
    ),
    "quadras.face_length_score": _P(
        "Pontuação de face de quadra",
        "Escore gradual do comprimento de face: 1,0 até 120 m, piso 0,1 "
        "em 250 m (limite legal local).",
        _POR_FEICAO,
        FeatureKey.QUADRA_ID,
        value_shape=_FEATURE_SERIES,
        internal=True,
    ),
    "road_network.total_length": _P(
        "Extensão viária total",
        "Soma dos comprimentos dos trechos do eixo viário, em metros.",
        _PROJETO,
        value_shape=_SCALAR,
    ),
    "road_network.existing_length": _P(
        "Extensão de vias existentes",
        "Comprimento total dos trechos classificados como existentes, em metros.",
        _PROJETO,
        value_shape=_SCALAR,
    ),
    "road_network.proposed_length": _P(
        "Extensão de vias propostas",
        "Comprimento total dos trechos classificados como propostos, em metros.",
        _PROJETO,
        value_shape=_SCALAR,
    ),
    "road_network.intersection_count": _P(
        "Número de interseções",
        "Nós do grafo viário com grau 3 ou mais.",
        _PROJETO,
        value_shape=_SCALAR,
    ),
    "road_network.intersection_density": _P(
        "Densidade de interseções",
        "Interseções por km² da área bruta do projeto.",
        _PROJETO,
        value_shape=_SCALAR,
    ),
    "road_network.link_node_ratio": _P(
        "Relação trechos/nós",
        "Conectividade da malha: número de arestas dividido pelo de nós.",
        _PROJETO,
        value_shape=_SCALAR,
    ),
    "road_network.proposed_connection_count": _P(
        "Conexões propostas",
        "Ligações entre a rede viária proposta e a existente.",
        _PROJETO,
        value_shape=_SCALAR,
    ),
    "density.max_computable_area": _P(
        "Potencial construtivo máximo",
        "Soma de área do lote × CA máximo dos lotes com CA válido, "
        "em metros quadrados.",
        _PROJETO,
        value_shape=_SCALAR,
    ),
    "density.lot_count_with_ca": _P(
        "Lotes com CA definido",
        "Quantidade de lotes com coeficiente de aproveitamento válido.",
        _PROJETO,
        value_shape=_SCALAR,
    ),
    "density.ca_coverage": _P(
        "Cobertura de CA",
        "Fração da área dos lotes coberta por CA válido.",
        _PROJETO,
        value_shape=_SCALAR,
    ),
    "lots.frontage_length": _P(
        "Testada por lote",
        "Comprimento do limite do lote junto ao sistema viário "
        "(buffer de 3 m), por lote.",
        _POR_FEICAO,
        FeatureKey.FEATURE_ID,
        value_shape=_FEATURE_SERIES,
    ),
    "lots.parceling_efficiency": _P(
        "Eficiência de parcelamento",
        "Área bruta dos lotes dividida pela área da quadra, por quadra.",
        _POR_FEICAO,
        FeatureKey.QUADRA_ID,
        value_shape=_FEATURE_SERIES,
    ),
}
