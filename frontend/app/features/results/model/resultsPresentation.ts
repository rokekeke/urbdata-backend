import type { LayerStyleConfig } from "../../../lib/types";
import type { SelectedFeature } from "../../../store/useWorkspaceStore";
import type { CatalogIndicator } from "../../catalog/api/listCatalogIndicators";
import type { AnalysisRun } from "../api/listProjectRuns";
import type { IndicatorResult } from "../api/listProjectResults";

export type ResultValueKind = "empty" | "scalar" | "numeric_record" | "composite_record";

export interface ResultIndicatorView {
  code: string;
  displayName: string;
  description: string;
  theme: string;
  themeLabel: string;
  granularity: CatalogIndicator["granularity"];
  featureKey: CatalogIndicator["feature_key"];
  requiredLayers: string[];
  rawValue: IndicatorResult["value"];
  valueKind: ResultValueKind;
  formattedValue: string;
  unit: string;
  unitLabel: string;
  formulaVersion: string;
  metricCrs: string | null;
  sourceLayers: string[];
  contributingFeatureIds: string[];
  warnings: IndicatorResult["warnings"];
  parameters: Record<string, unknown>;
}

export interface ResultDistributionEntry {
  key: string;
  rawValue: unknown;
  formattedValue: string;
  numericValue: number | null;
}

export interface ResultOverlayDefinition {
  layerId: string;
  featureKey: "feature_id" | "quadra_id";
  values: Record<string, unknown>;
  min: number;
  max: number;
}

const THEME_LABELS: Record<string, string> = {
  territorial: "Território",
  land_use: "Uso do solo",
  density: "Densidade e potencial",
  quadras: "Quadras",
  lots: "Lotes",
  green_areas: "Áreas verdes",
  road_network: "Sistema viário",
};

const RUN_STATUS_LABELS: Record<AnalysisRun["status"], string> = {
  pending: "Na fila",
  running: "Em processamento",
  completed: "Concluída",
  failed: "Falhou",
};

export function buildResultIndicatorViews(
  catalog: CatalogIndicator[],
  results: IndicatorResult[],
): ResultIndicatorView[] {
  const catalogByCode = new Map(catalog.map((indicator) => [indicator.code, indicator]));

  return results
    .map((result) => {
      const indicator = catalogByCode.get(result.indicator_code);
      if (!indicator) return null;
      const valueKind = classifyResultValue(result.value);
      return {
        code: indicator.code,
        displayName: indicator.display_name,
        description: indicator.description,
        theme: indicator.theme,
        themeLabel: themeLabel(indicator.theme),
        granularity: indicator.granularity,
        featureKey: indicator.feature_key,
        requiredLayers: indicator.required_layers,
        rawValue: result.value,
        valueKind,
        formattedValue: summarizeResultValue(result.value, result.unit, indicator.granularity),
        unit: result.unit,
        unitLabel: unitLabel(result.unit),
        formulaVersion: result.formula_version,
        metricCrs: result.metric_crs,
        sourceLayers: result.source_layers,
        contributingFeatureIds: result.contributing_feature_ids,
        warnings: result.warnings,
        parameters: result.parameters,
      } satisfies ResultIndicatorView;
    })
    .filter((item): item is ResultIndicatorView => item !== null)
    .sort((left, right) =>
      left.themeLabel.localeCompare(right.themeLabel, "pt-BR")
      || left.displayName.localeCompare(right.displayName, "pt-BR"),
    );
}

export function buildDistributionEntries(view: ResultIndicatorView): ResultDistributionEntry[] {
  if (!isRecord(view.rawValue)) return [];
  return Object.entries(view.rawValue)
    .map(([key, rawValue]) => ({
      key,
      rawValue,
      formattedValue: isScalar(rawValue)
        ? formatScalarValue(rawValue, view.unit)
        : "Valor composto",
      numericValue: finiteNumber(rawValue),
    }))
    .sort((left, right) => {
      if (left.numericValue !== null && right.numericValue !== null) {
        return right.numericValue - left.numericValue;
      }
      return left.key.localeCompare(right.key, "pt-BR");
    });
}

export function numericDistributionSummary(entries: ResultDistributionEntry[]) {
  const values = entries
    .map((entry) => entry.numericValue)
    .filter((value): value is number => value !== null);
  if (values.length === 0) return null;
  return {
    count: values.length,
    min: Math.min(...values),
    max: Math.max(...values),
    mean: values.reduce((total, value) => total + value, 0) / values.length,
  };
}

export function buildResultOverlay(
  view: ResultIndicatorView,
  layers: LayerStyleConfig[],
): ResultOverlayDefinition | null {
  if (view.granularity !== "por_feicao" || !view.featureKey || !isRecord(view.rawValue)) {
    return null;
  }
  const numericValues = Object.values(view.rawValue)
    .map(finiteNumber)
    .filter((value): value is number => value !== null);
  if (numericValues.length === 0) return null;

  const targetLayer = view.featureKey === "quadra_id"
    ? layers.find((layer) => layer.layerType === "quadras")
    : layers.find((layer) => view.requiredLayers.includes(layer.layerType ?? ""));
  if (!targetLayer) return null;

  const min = Math.min(...numericValues);
  const max = Math.max(...numericValues);
  return {
    layerId: targetLayer.id,
    featureKey: view.featureKey,
    values: view.rawValue,
    min,
    max: min === max ? min + 1 : max,
  };
}

export function selectedFeatureResult(
  view: ResultIndicatorView,
  selectedFeature: SelectedFeature | null,
): { status: "available" | "no_data" | "not_applicable"; formattedValue: string } | null {
  if (!selectedFeature || view.granularity !== "por_feicao" || !view.featureKey || !isRecord(view.rawValue)) {
    return null;
  }
  const key = view.featureKey === "feature_id"
    ? selectedFeature.featureId
    : selectedFeature.properties.quadra_id;
  if (typeof key !== "string" && typeof key !== "number") {
    return { status: "not_applicable", formattedValue: "Não aplicável" };
  }
  const rawValue = view.rawValue[String(key)];
  if (rawValue === null || rawValue === undefined) {
    return { status: "no_data", formattedValue: "Sem dado" };
  }
  return { status: "available", formattedValue: isScalar(rawValue) ? formatScalarValue(rawValue, view.unit) : "Valor composto" };
}

export function themeLabel(theme: string): string {
  return THEME_LABELS[theme] ?? humanize(theme);
}

export function runStatusLabel(status: AnalysisRun["status"]): string {
  return RUN_STATUS_LABELS[status];
}

export function runThemes(run: AnalysisRun): string[] {
  const themes = run.config.themes;
  if (!Array.isArray(themes)) return [];
  return themes.filter((theme): theme is string => typeof theme === "string").map(themeLabel);
}

export function formatDuration(durationMs: number | null): string {
  if (durationMs === null) return "Duração indisponível";
  if (durationMs < 1_000) return `${durationMs} ms`;
  return `${new Intl.NumberFormat("pt-BR", { maximumFractionDigits: 1 }).format(durationMs / 1_000)} s`;
}

export function formatRunDate(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "Data indisponível";
  return new Intl.DateTimeFormat("pt-BR", {
    day: "2-digit",
    month: "short",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  }).format(date);
}

export function formatScalarValue(value: number | string, unit: string): string {
  if (typeof value === "string") return value || "Sem dado";
  const presentedValue = unit === "ratio" ? value * 100 : value;
  const formatted = new Intl.NumberFormat("pt-BR", { maximumFractionDigits: 2 }).format(presentedValue);
  const suffix = unitLabel(unit);
  return suffix ? `${formatted} ${suffix}` : formatted;
}

function classifyResultValue(value: IndicatorResult["value"]): ResultValueKind {
  if (value === null || value === "") return "empty";
  if (typeof value === "number" || typeof value === "string") return "scalar";
  const values = Object.values(value);
  if (values.length === 0) return "empty";
  return values.every((item) => finiteNumber(item) !== null) ? "numeric_record" : "composite_record";
}

function summarizeResultValue(
  value: IndicatorResult["value"],
  unit: string,
  granularity: CatalogIndicator["granularity"],
): string {
  if (value === null || value === "") return "Sem dado";
  if (typeof value === "number" || typeof value === "string") return formatScalarValue(value, unit);
  const count = Object.keys(value).length;
  if (count === 0) return "Sem dado";
  return granularity === "por_feicao"
    ? `${count.toLocaleString("pt-BR")} feições`
    : `${count.toLocaleString("pt-BR")} categorias`;
}

function unitLabel(unit: string): string {
  const labels: Record<string, string> = {
    m2: "m²",
    m: "m",
    ratio: "%",
    count: "",
    "count/km2": "interseções/km²",
    adimensional: "",
    categoria: "",
    composto: "",
  };
  return labels[unit] ?? unit;
}

function finiteNumber(value: unknown): number | null {
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

function isScalar(value: unknown): value is number | string {
  return typeof value === "number" || typeof value === "string";
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function humanize(value: string): string {
  const normalized = value.replaceAll("_", " ");
  return normalized.charAt(0).toLocaleUpperCase("pt-BR") + normalized.slice(1);
}
