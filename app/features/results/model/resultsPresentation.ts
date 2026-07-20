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
  valueShape: CatalogIndicator["value_shape"];
  categoryFeatureProperty: CatalogIndicator["category_feature_property"];
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

export interface CategoryShareEntry {
  key: string;
  label: string;
  color: string;
  numericValue: number;
  share: number;
  formattedValue: string;
  formattedShare: string;
}

export interface CompoundTableColumn {
  key: string;
  label: string;
}

export interface CompoundTableRow {
  key: string;
  cells: string[];
}

export interface CompoundTable {
  columns: CompoundTableColumn[];
  rows: CompoundTableRow[];
}

export interface NumericResultOverlay {
  kind: "numeric";
  layerId: string;
  featureKey: "feature_id" | "quadra_id";
  values: Record<string, unknown>;
  min: number;
  max: number;
}

export interface CategoricalOverlayEntry {
  key: string;
  normalizedKey: string;
  label: string;
  color: string;
}

export interface CategoricalResultOverlay {
  kind: "categorical";
  layerId: string;
  /** Propriedade da feição no GeoJSON (ex.: macroarea) - carrega o valor
   * BRUTO mapeado, então a junção usa `normalizeCategoryKey` dos dois
   * lados, mesma regra do `normalize_key` do backend. */
  property: string;
  categories: CategoricalOverlayEntry[];
}

export type ResultOverlayDefinition = NumericResultOverlay | CategoricalResultOverlay;

// Vocabulários fechados do backend (macroáreas da ADR 008 e usos do solo de
// land_use_mapping.py); qualquer chave fora deles cai no humanize genérico.
const CATEGORY_LABELS: Record<string, string> = {
  lote: "Lote",
  sistema_viario: "Sistema viário",
  avl: "AVL",
  app: "APP",
  aci: "ACI",
  nulo: "Nulo",
  residencial: "Residencial",
  comercial: "Comercial",
  servicos: "Serviços",
  institucional: "Institucional",
  industrial: "Industrial",
  misto: "Misto",
};

// Paleta categórica alinhada aos tons da interface; atribuída por ordem
// decrescente de participação, então o mapa e a lista de participação
// compartilham as mesmas cores. Fora do vocabulário, cai no cinza neutro.
const CATEGORY_PALETTE = [
  "#3D6F78",
  "#D6B17B",
  "#6D9375",
  "#995044",
  "#4D7390",
  "#8A7A9C",
  "#C78268",
  "#43564F",
];

export const CATEGORY_FALLBACK_COLOR = "#d6d5cf";

// Sub-campos dos valores compostos por feição (quadras.stats e
// min_rotated_rectangle) - a unidade vai no rótulo da coluna, então as
// células ficam só com o número.
const COMPOUND_FIELD_LABELS: Record<string, string> = {
  area_m2: "Área (m²)",
  perimetro_m: "Perímetro (m)",
  quantidade_lotes: "Lotes",
  comprimento_m: "Comprimento (m)",
  largura_m: "Largura (m)",
};

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
        valueShape: indicator.value_shape,
        categoryFeatureProperty: indicator.category_feature_property,
        featureKey: indicator.feature_key,
        requiredLayers: indicator.required_layers,
        rawValue: result.value,
        valueKind,
        formattedValue: summarizeResultValue(result.value, result.unit, indicator.value_shape),
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

function orderedNumericCategories(
  view: ResultIndicatorView,
): Array<{ key: string; numericValue: number }> {
  if (!isRecord(view.rawValue)) return [];
  return Object.entries(view.rawValue)
    .map(([key, rawValue]) => ({ key, numericValue: finiteNumber(rawValue) }))
    .filter((entry): entry is { key: string; numericValue: number } => entry.numericValue !== null)
    .sort((left, right) => right.numericValue - left.numericValue);
}

function categoryColorFor(index: number): string {
  return CATEGORY_PALETTE[index] ?? CATEGORY_FALLBACK_COLOR;
}

export function buildCategoryShares(view: ResultIndicatorView): CategoryShareEntry[] {
  const numericEntries = orderedNumericCategories(view);
  const total = numericEntries.reduce((sum, entry) => sum + entry.numericValue, 0);
  if (total <= 0) return [];
  return numericEntries.map((entry, index) => {
    const share = entry.numericValue / total;
    return {
      key: entry.key,
      label: categoryLabel(entry.key),
      color: categoryColorFor(index),
      numericValue: entry.numericValue,
      share,
      formattedValue: formatScalarValue(entry.numericValue, view.unit),
      formattedShare: `${new Intl.NumberFormat("pt-BR", { maximumFractionDigits: 1 }).format(share * 100)} %`,
    };
  });
}

export function buildCompoundTable(view: ResultIndicatorView): CompoundTable | null {
  if (!isRecord(view.rawValue)) return null;
  const compoundRows = Object.entries(view.rawValue).filter(
    (entry): entry is [string, Record<string, unknown>] => isRecord(entry[1]),
  );
  if (compoundRows.length === 0) return null;

  const columnKeys: string[] = [];
  for (const [, record] of compoundRows) {
    for (const key of Object.keys(record)) {
      if (!columnKeys.includes(key)) columnKeys.push(key);
    }
  }

  return {
    columns: columnKeys.map((key) => ({ key, label: compoundFieldLabel(key) })),
    rows: compoundRows
      .map(([key, record]) => ({
        key,
        cells: columnKeys.map((columnKey) => formatCompoundCell(record[columnKey])),
      }))
      .sort((left, right) => left.key.localeCompare(right.key, "pt-BR", { numeric: true })),
  };
}

export function formatCompoundRecord(record: Record<string, unknown>): string {
  const parts = Object.entries(record)
    .map(([key, value]) => `${compoundFieldLabel(key)} ${formatCompoundCell(value)}`);
  return parts.length ? parts.join(" · ") : "Sem dado";
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

/** Espelha `normalize_key` do backend: minúsculas, sem acentos, só
 * alfanumérico - "SISTEMA VIÁRIO" (valor bruto do GeoJSON) e
 * "sistema_viario" (chave do resultado) convergem para "sistemaviario". */
export function normalizeCategoryKey(value: string): string {
  return value
    .normalize("NFKD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase()
    .replace(/[^a-z0-9]/g, "");
}

export function buildResultOverlay(
  view: ResultIndicatorView,
  layers: LayerStyleConfig[],
): ResultOverlayDefinition | null {
  if (!isRecord(view.rawValue)) return null;

  if (view.valueShape === "category_breakdown" && view.categoryFeatureProperty) {
    const targetLayer = layers.find((layer) => view.requiredLayers.includes(layer.layerType ?? ""));
    if (!targetLayer) return null;
    const categories = orderedNumericCategories(view).map((entry, index) => ({
      key: entry.key,
      normalizedKey: normalizeCategoryKey(entry.key),
      label: categoryLabel(entry.key),
      color: categoryColorFor(index),
    }));
    if (categories.length === 0) return null;
    return {
      kind: "categorical",
      layerId: targetLayer.id,
      property: view.categoryFeatureProperty,
      categories,
    };
  }

  if (view.granularity !== "por_feicao" || !view.featureKey) return null;
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
    kind: "numeric",
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
  return {
    status: "available",
    formattedValue: isScalar(rawValue)
      ? formatScalarValue(rawValue, view.unit)
      : isRecord(rawValue)
        ? formatCompoundRecord(rawValue)
        : "Valor composto",
  };
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
  valueShape: CatalogIndicator["value_shape"],
): string {
  if (value === null || value === "") {
    // Empate ou universo vazio é um desfecho legítimo do cálculo (o aviso
    // acompanha o resultado), não um dado ausente genérico.
    return valueShape === "categorical_label" ? "Sem categoria predominante" : "Sem dado";
  }
  if (typeof value === "string" && valueShape === "categorical_label") {
    return categoryLabel(value);
  }
  if (typeof value === "number" || typeof value === "string") return formatScalarValue(value, unit);
  const count = Object.keys(value).length;
  if (count === 0) return "Sem dado";
  return valueShape === "category_breakdown"
    ? `${count.toLocaleString("pt-BR")} categorias`
    : `${count.toLocaleString("pt-BR")} feições`;
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

export function categoryLabel(value: string): string {
  return CATEGORY_LABELS[value] ?? humanize(value);
}

function compoundFieldLabel(key: string): string {
  return COMPOUND_FIELD_LABELS[key] ?? humanize(key);
}

function formatCompoundCell(value: unknown): string {
  if (value === null || value === undefined) return "—";
  if (typeof value === "number" && Number.isFinite(value)) {
    return new Intl.NumberFormat("pt-BR", { maximumFractionDigits: 2 }).format(value);
  }
  if (typeof value === "string") return value || "—";
  if (Array.isArray(value)) return value.length.toLocaleString("pt-BR");
  return "—";
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
