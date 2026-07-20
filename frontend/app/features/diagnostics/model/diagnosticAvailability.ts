import type { CatalogIndicator } from "../../catalog/api/listCatalogIndicators";
import type { LayerStyleConfig } from "../../../lib/types";

export type DiagnosticAvailabilityStatus = "available" | "attention" | "blocked";

export interface DiagnosticLayerRequirement {
  layerType: string;
  label: string;
  state: "ready" | "attention" | "missing" | "error";
  detail: string;
}

export interface DiagnosticTheme {
  id: string;
  label: string;
  description: string;
  outcome: string;
  backendThemes: string[];
  indicators: CatalogIndicator[];
  requirements: DiagnosticLayerRequirement[];
  status: DiagnosticAvailabilityStatus;
  statusLabel: string;
  blockerSummary: string | null;
  nextAction: string | null;
}

interface ThemeDefinition {
  id: string;
  label: string;
  description: string;
  outcome: string;
  backendThemes: string[];
}

const THEME_DEFINITIONS: ThemeDefinition[] = [
  {
    id: "territorio",
    label: "Território",
    description: "Dimensões gerais e composição das macroáreas do projeto.",
    outcome: "Área total, perímetro, compacidade e distribuição territorial.",
    backendThemes: ["territorial"],
  },
  {
    id: "uso-solo",
    label: "Uso do solo",
    description: "Composição e diversidade dos usos classificados nos lotes.",
    outcome: "Áreas, percentuais, uso predominante e diversidade de usos.",
    backendThemes: ["land_use"],
  },
  {
    id: "densidade",
    label: "Densidade e potencial",
    description: "Leitura do potencial construtivo informado para os lotes.",
    outcome: "Potencial máximo, lotes com CA e cobertura do coeficiente.",
    backendThemes: ["density"],
  },
  {
    id: "quadras-lotes",
    label: "Quadras e lotes",
    description: "Forma urbana, dimensões das quadras e relação dos lotes com o viário.",
    outcome: "Compacidade, dimensões, faces, testadas e eficiência de parcelamento.",
    backendThemes: ["quadras", "lots"],
  },
  {
    id: "areas-verdes",
    label: "Áreas verdes",
    description: "Participação das áreas verdes de lazer no território do projeto.",
    outcome: "Área verde total e percentual sobre a área bruta do projeto.",
    backendThemes: ["green_areas"],
  },
  {
    id: "sistema-viario",
    label: "Sistema viário",
    description: "Estrutura e conectividade da rede de eixos viários.",
    outcome: "Extensões, interseções, conectividade e ligações propostas.",
    backendThemes: ["road_network"],
  },
];

const LAYER_LABELS: Record<string, string> = {
  perimetro: "Perímetro da matrícula",
  territorio: "Macroáreas territoriais",
  quadras: "Quadras derivadas",
  lotes: "Lotes",
  sistema_viario: "Eixos do sistema viário",
  uso_solo: "Uso do solo",
  areas_verdes: "Áreas verdes",
  equipamentos: "Equipamentos",
  edificacoes: "Edificações",
  desconexoes_viarias: "Desconexões viárias",
};

export function buildDiagnosticThemes(
  catalog: CatalogIndicator[],
  layers: LayerStyleConfig[],
): DiagnosticTheme[] {
  return THEME_DEFINITIONS.map((definition) => {
    const indicators = catalog.filter((indicator) => definition.backendThemes.includes(indicator.theme));
    const requiredTypes = Array.from(new Set([
      "perimetro",
      ...indicators.flatMap((indicator) => indicator.required_layers),
    ])).sort((left, right) => layerLabel(left).localeCompare(layerLabel(right), "pt-BR"));
    const requirements = requiredTypes.map((layerType) => requirementFor(layerType, layers));
    const hasMissing = requirements.some((requirement) => requirement.state === "missing");
    const hasError = requirements.some((requirement) => requirement.state === "error");
    const hasAttention = requirements.some((requirement) => requirement.state === "attention");
    const status: DiagnosticAvailabilityStatus = indicators.length === 0 || hasMissing || hasError
      ? "blocked"
      : hasAttention ? "attention" : "available";
    const blockers = requirements.filter((requirement) => requirement.state === "missing" || requirement.state === "error");

    return {
      ...definition,
      indicators,
      requirements,
      status,
      statusLabel: status === "available" ? "Disponível" : status === "attention" ? "Revisar base" : "Bloqueado",
      blockerSummary: indicators.length === 0
        ? "O tema não possui indicadores publicados no catálogo."
        : blockers.length
          ? blockers.map((requirement) => `${requirement.label}: ${requirement.detail}`).join("; ")
          : null,
      nextAction: indicators.length === 0
        ? "Solicite a publicação do tema no catálogo do backend."
        : blockers.length
          ? "Abra Dados para adicionar ou corrigir as bases indicadas."
          : hasAttention
            ? "Revise o mapeamento dos campos antes de processar, se necessário."
            : null,
    };
  });
}

export function selectedBackendThemes(
  themes: DiagnosticTheme[],
  selectedIds: string[],
): string[] {
  const selected = new Set(selectedIds);
  return themes
    .filter((theme) => selected.has(theme.id) && theme.status !== "blocked")
    .flatMap((theme) => theme.backendThemes);
}

function requirementFor(
  layerType: string,
  layers: LayerStyleConfig[],
): DiagnosticLayerRequirement {
  const layer = layers.find((item) => item.layerType === layerType);
  if (!layer) {
    return {
      layerType,
      label: layerLabel(layerType),
      state: "missing",
      detail: "camada ausente",
    };
  }
  if (layer.status === "error") {
    return {
      layerType,
      label: layerLabel(layerType),
      state: "error",
      detail: "camada com erro",
    };
  }
  if (layer.status === "uploaded") {
    return {
      layerType,
      label: layerLabel(layerType),
      state: "attention",
      detail: "camada presente; mapeamento ainda não confirmado",
    };
  }
  return {
    layerType,
    label: layerLabel(layerType),
    state: "ready",
    detail: layer.status === "validated" ? "camada validada" : "camada mapeada",
  };
}

function layerLabel(layerType: string): string {
  return LAYER_LABELS[layerType] ?? layerType.replaceAll("_", " ");
}
