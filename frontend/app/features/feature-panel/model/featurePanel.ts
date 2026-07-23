import type { CatalogIndicator } from "../../catalog/api/listCatalogIndicators";
import type { IndicatorResult } from "../../results/api/listProjectResults";
import type { SelectedFeature } from "../../../store/useWorkspaceStore";

export type FeatureIndicatorStatus = "available" | "no_data" | "not_calculated" | "missing_key";

export interface FeatureIndicatorRow {
  code: string;
  displayName: string;
  theme: string;
  rawValue: unknown;
  formattedValue: string;
  unit: string;
  status: FeatureIndicatorStatus;
  formulaVersion: string;
  metricCrs: string | null;
  warnings: IndicatorResult["warnings"];
}

export interface FeaturePropertyRow {
  key: string;
  label: string;
  rawValue: unknown;
  formattedValue: string;
}

const PROPERTY_PRIORITY = [
  "nome",
  "name",
  "quadra_id",
  "lote_id",
  "id",
  "tipo",
  "uso",
  "categoria",
  "macroarea",
];

export function buildFeatureIndicatorRows({
  catalog,
  results,
  selectedFeature,
  compatibleIndicatorCodes,
}: {
  catalog: CatalogIndicator[];
  results: IndicatorResult[];
  selectedFeature: SelectedFeature;
  compatibleIndicatorCodes: string[];
}): FeatureIndicatorRow[] {
  const compatible = new Set(compatibleIndicatorCodes);
  const resultByCode = new Map(results.map((result) => [result.indicator_code, result]));

  return catalog
    .filter((indicator) =>
      indicator.granularity === "por_feicao"
      && indicator.feature_key !== null
      && compatible.has(indicator.code),
    )
    .map((indicator) => {
      const result = resultByCode.get(indicator.code);
      const joinKey = featureJoinKey(indicator.feature_key, selectedFeature);

      if (!joinKey) {
        return createIndicatorRow(indicator, result, undefined, "missing_key");
      }

      if (!result || !isRecord(result.value) || !hasOwn(result.value, joinKey)) {
        return createIndicatorRow(indicator, result, undefined, "not_calculated");
      }

      const value = result.value[joinKey];
      return createIndicatorRow(
        indicator,
        result,
        value,
        value === null || value === undefined ? "no_data" : "available",
      );
    })
    .sort((left, right) => left.displayName.localeCompare(right.displayName, "pt-BR"));
}

export function selectFeatureProperties(
  properties: Record<string, unknown>,
  limit = 6,
): FeaturePropertyRow[] {
  const entries = Object.entries(properties);
  const priorityIndex = new Map(PROPERTY_PRIORITY.map((key, index) => [key, index]));

  return entries
    .sort(([left], [right]) => {
      const leftPriority = priorityIndex.get(left.toLocaleLowerCase("pt-BR")) ?? PROPERTY_PRIORITY.length;
      const rightPriority = priorityIndex.get(right.toLocaleLowerCase("pt-BR")) ?? PROPERTY_PRIORITY.length;
      return leftPriority - rightPriority || left.localeCompare(right, "pt-BR");
    })
    .slice(0, limit)
    .map(([key, rawValue]) => ({
      key,
      label: humanizeFieldName(key),
      rawValue,
      formattedValue: formatFeatureValue(rawValue),
    }));
}

export function formatFeatureValue(value: unknown): string {
  if (value === null || value === undefined || value === "") return "Sem dado";
  if (typeof value === "number") {
    return new Intl.NumberFormat("pt-BR", { maximumFractionDigits: 2 }).format(value);
  }
  if (typeof value === "boolean") return value ? "Sim" : "Não";
  if (Array.isArray(value)) return value.length ? value.map(formatFeatureValue).join(", ") : "Sem dado";
  if (isRecord(value)) return "Valor composto";
  return String(value);
}

function featureJoinKey(
  featureKey: CatalogIndicator["feature_key"],
  selectedFeature: SelectedFeature,
): string | null {
  if (featureKey === "feature_id") return selectedFeature.featureId;
  if (featureKey === "quadra_id") {
    const value = selectedFeature.properties.quadra_id;
    return typeof value === "string" || typeof value === "number" ? String(value) : null;
  }
  return null;
}

function createIndicatorRow(
  indicator: CatalogIndicator,
  result: IndicatorResult | undefined,
  rawValue: unknown,
  status: FeatureIndicatorStatus,
): FeatureIndicatorRow {
  return {
    code: indicator.code,
    displayName: indicator.display_name,
    theme: indicator.theme,
    rawValue,
    formattedValue: status === "available" ? formatFeatureValue(rawValue) : statusLabel(status),
    unit: result?.unit || indicator.unit,
    status,
    formulaVersion: result?.formula_version || indicator.formula_version,
    metricCrs: result?.metric_crs ?? null,
    warnings: result?.warnings ?? [],
  };
}

function statusLabel(status: Exclude<FeatureIndicatorStatus, "available">): string {
  if (status === "no_data") return "Sem dado";
  if (status === "missing_key") return "Não aplicável";
  return "Não calculado";
}

function humanizeFieldName(value: string): string {
  const sentence = value.replaceAll("_", " ").trim();
  return sentence ? sentence.charAt(0).toLocaleUpperCase("pt-BR") + sentence.slice(1) : value;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function hasOwn(value: Record<string, unknown>, key: string): boolean {
  return Object.prototype.hasOwnProperty.call(value, key);
}
