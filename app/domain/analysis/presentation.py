"""Presentation metadata for catalog indicators (Fase 0 do roadmap, nota 28/29).

Separated from `IndicatorDefinition` on purpose: the engine never needs
display names, and the API composes registry + presentation at the edge.
A drift test (`tests/unit/test_catalog_presentation.py`) keeps this table
1:1 with the registered catalog.

Accented Portuguese text uses \\uXXXX escapes so the source file stays pure
ASCII - the local toolchain has mangled literal accented characters in .py
files before (see Obsidian note 10 and the project memory).
"""

from dataclasses import dataclass
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


@dataclass(frozen=True, slots=True)
class IndicatorPresentation:
    display_name: str
    description: str
    granularity: IndicatorGranularity
    feature_key: FeatureKey | None = None

    def __post_init__(self) -> None:
        if not self.display_name or not self.description:
            raise ValueError("display_name and description must not be empty")
        if self.granularity is IndicatorGranularity.POR_FEICAO and self.feature_key is None:
            raise ValueError("por_feicao indicators must declare a feature_key")
        if self.granularity is IndicatorGranularity.PROJETO and self.feature_key is not None:
            raise ValueError("projeto indicators must not declare a feature_key")


_P = IndicatorPresentation
_PROJETO = IndicatorGranularity.PROJETO
_POR_FEICAO = IndicatorGranularity.POR_FEICAO

PRESENTATIONS: dict[str, IndicatorPresentation] = {
    "territorial.total_area": _P(
        "Área total do projeto",
        "Área bruta do perímetro da matrícula, em metros quadrados, "
        "medida em CRS métrico.",
        _PROJETO,
    ),
    "territorial.perimeter": _P(
        "Perímetro do projeto",
        "Comprimento do limite consolidado do projeto, em metros.",
        _PROJETO,
    ),
    "territorial.compactness": _P(
        "Compacidade do perímetro",
        "Índice isoperimétrico de Polsby-Popper (círculo = 1,0).",
        _PROJETO,
    ),
    "territorial.area_by_category": _P(
        "Área por macroárea",
        "Inventário de área por categoria territorial (Lote, Sistema "
        "viário, AVL, APP, ACI, Nulo), incluindo não parceláveis.",
        _PROJETO,
    ),
    "territorial.percent_by_category": _P(
        "Percentual por macroárea (parcelável)",
        "Distribuição percentual da área parcelável por categoria; "
        "soma ~100% do universo parcelável.",
        _PROJETO,
    ),
    "land_use.area_by_category": _P(
        "Área por uso do solo",
        "Área dos lotes por categoria de uso (residencial, comercial, "
        "serviços, institucional, industrial, misto).",
        _PROJETO,
    ),
    "land_use.percent_by_category": _P(
        "Percentual por uso do solo",
        "Distribuição percentual sobre a área classificada dos lotes.",
        _PROJETO,
    ),
    "land_use.predominant_use": _P(
        "Uso predominante",
        "Categoria com maior área classificada; empate retorna vazio com aviso.",
        _PROJETO,
    ),
    "land_use.diversity_shannon": _P(
        "Diversidade de usos (Shannon)",
        "Índice de Shannon-Wiener sobre proporções de área por uso.",
        _PROJETO,
    ),
    "green_areas.total_area": _P(
        "Área verde total",
        "Soma das áreas AVL do projeto, em metros quadrados.",
        _PROJETO,
    ),
    "green_areas.percent_of_project": _P(
        "Área verde sobre o projeto",
        "Razão entre a área verde e a área bruta do projeto.",
        _PROJETO,
    ),
    "quadras.stats": _P(
        "Estatísticas por quadra",
        "Área, perímetro e lotes contribuintes de cada quadra derivada.",
        _POR_FEICAO,
        FeatureKey.QUADRA_ID,
    ),
    "quadras.compactness": _P(
        "Compacidade por quadra",
        "Índice de Polsby-Popper de cada quadra derivada.",
        _POR_FEICAO,
        FeatureKey.QUADRA_ID,
    ),
    "quadras.min_rotated_rectangle": _P(
        "Dimensões por quadra",
        "Comprimento e largura do retângulo mínimo rotacionado de cada quadra.",
        _POR_FEICAO,
        FeatureKey.QUADRA_ID,
    ),
    "quadras.face_length_score": _P(
        "Pontuação de face de quadra",
        "Escore gradual do comprimento de face: 1,0 até 120 m, piso 0,1 "
        "em 250 m (limite legal local).",
        _POR_FEICAO,
        FeatureKey.QUADRA_ID,
    ),
    "road_network.total_length": _P(
        "Extensão viária total",
        "Soma dos comprimentos dos trechos do eixo viário, em metros.",
        _PROJETO,
    ),
    "road_network.existing_length": _P(
        "Extensão de vias existentes",
        "Comprimento total dos trechos classificados como existentes, em metros.",
        _PROJETO,
    ),
    "road_network.proposed_length": _P(
        "Extensão de vias propostas",
        "Comprimento total dos trechos classificados como propostos, em metros.",
        _PROJETO,
    ),
    "road_network.intersection_count": _P(
        "Número de interseções",
        "Nós do grafo viário com grau 3 ou mais.",
        _PROJETO,
    ),
    "road_network.intersection_density": _P(
        "Densidade de interseções",
        "Interseções por km² da área bruta do projeto.",
        _PROJETO,
    ),
    "road_network.link_node_ratio": _P(
        "Relação trechos/nós",
        "Conectividade da malha: número de arestas dividido pelo de nós.",
        _PROJETO,
    ),
    "road_network.proposed_connection_count": _P(
        "Conexões propostas",
        "Ligações entre a rede viária proposta e a existente.",
        _PROJETO,
    ),
    "density.max_computable_area": _P(
        "Potencial construtivo máximo",
        "Soma de área do lote × CA máximo dos lotes com CA válido, "
        "em metros quadrados.",
        _PROJETO,
    ),
    "density.lot_count_with_ca": _P(
        "Lotes com CA definido",
        "Quantidade de lotes com coeficiente de aproveitamento válido.",
        _PROJETO,
    ),
    "density.ca_coverage": _P(
        "Cobertura de CA",
        "Fração da área dos lotes coberta por CA válido.",
        _PROJETO,
    ),
    "lots.frontage_length": _P(
        "Testada por lote",
        "Comprimento do limite do lote junto ao sistema viário "
        "(buffer de 3 m), por lote.",
        _POR_FEICAO,
        FeatureKey.FEATURE_ID,
    ),
    "lots.parceling_efficiency": _P(
        "Eficiência de parcelamento",
        "Área bruta dos lotes dividida pela área da quadra, por quadra.",
        _POR_FEICAO,
        FeatureKey.QUADRA_ID,
    ),
}
