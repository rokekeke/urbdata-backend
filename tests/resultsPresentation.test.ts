import { describe, expect, it } from "vitest";

import type { CatalogIndicator } from "../app/features/catalog/api/listCatalogIndicators";
import type { AnalysisRun } from "../app/features/results/api/listProjectRuns";
import type { IndicatorResult } from "../app/features/results/api/listProjectResults";
import {
  buildDistributionEntries,
  buildResultIndicatorViews,
  buildResultOverlay,
  formatDuration,
  formatScalarValue,
  numericDistributionSummary,
  runStatusLabel,
  runThemes,
  selectedFeatureResult,
} from "../app/features/results/model/resultsPresentation";
import type { LayerStyleConfig } from "../app/lib/types";

function catalogIndicator(
  code: string,
  options: Partial<CatalogIndicator> = {},
): CatalogIndicator {
  return {
    code,
    theme: "territorial",
    display_name: `Indicador ${code}`,
    description: "Descrição urbanística",
    unit: "ratio",
    formula_version: "1.0.0",
    granularity: "projeto",
    feature_key: null,
    required_layers: ["territorio"],
    optional_layers: [],
    ...options,
  };
}

function result(
  code: string,
  value: IndicatorResult["value"],
  unit = "ratio",
): IndicatorResult {
  return {
    indicator_code: code,
    theme: "territorial",
    formula_version: "1.1.0",
    value,
    unit,
    metric_crs: "EPSG:31983",
    parameters: { denominator: "project_area" },
    source_layers: ["territorio"],
    contributing_feature_ids: ["feature-1"],
    warnings: [],
  };
}

const layer: LayerStyleConfig = {
  id: "layer-territorio",
  name: "Território",
  shortName: "Território",
  geometry: "polygon",
  visible: true,
  opacity: 0.8,
  color: "#3d6f78",
  secondaryColor: "#d5b178",
  strokeColor: "#172a25",
  strokeWidth: 1,
  lineStyle: "solid",
  representation: "single",
  mode: "single",
  representationOptions: [],
  layerType: "territorio",
  featureCount: 10,
};

describe("resultsPresentation", () => {
  it("combina catálogo e resultado e preserva zero como resultado válido", () => {
    const views = buildResultIndicatorViews(
      [catalogIndicator("green_areas.percent_of_project")],
      [result("green_areas.percent_of_project", 0)],
    );

    expect(views[0]).toMatchObject({
      formattedValue: "0 %",
      valueKind: "scalar",
      formulaVersion: "1.1.0",
    });
  });

  it("formata razões como percentual somente na apresentação", () => {
    expect(formatScalarValue(0.125, "ratio")).toBe("12,5 %");
    expect(formatScalarValue(1250.5, "m2")).toBe("1.250,5 m²");
  });

  it("calcula resumo e ordena uma distribuição numérica sem alterar valores brutos", () => {
    const [view] = buildResultIndicatorViews(
      [catalogIndicator("territorial.percent_by_category")],
      [result("territorial.percent_by_category", { lote: 0.6, avl: 0.1, aci: 0.3 })],
    );
    const entries = buildDistributionEntries(view);
    const summary = numericDistributionSummary(entries);

    expect(entries.map((entry) => entry.key)).toEqual(["lote", "aci", "avl"]);
    expect(entries[0].formattedValue).toBe("60 %");
    expect(summary).toEqual({ count: 3, min: 0.1, max: 0.6, mean: expect.closeTo(1 / 3) });
  });

  it("cria sobreposição cartográfica apenas para resultado numérico por feição", () => {
    const [view] = buildResultIndicatorViews(
      [catalogIndicator("lots.frontage_length", { granularity: "por_feicao", feature_key: "feature_id", unit: "m" })],
      [result("lots.frontage_length", { "feature-1": 12, "feature-2": 0 }, "m")],
    );

    expect(buildResultOverlay(view, [layer])).toEqual({
      layerId: layer.id,
      featureKey: "feature_id",
      values: { "feature-1": 12, "feature-2": 0 },
      min: 0,
      max: 12,
    });
  });

  it("resolve valor da feição selecionada por UUID sem converter zero em ausência", () => {
    const [view] = buildResultIndicatorViews(
      [catalogIndicator("lots.frontage_length", { granularity: "por_feicao", feature_key: "feature_id", unit: "m" })],
      [result("lots.frontage_length", { "feature-1": 0 }, "m")],
    );

    expect(selectedFeatureResult(view, {
      layerId: layer.id,
      featureId: "feature-1",
      properties: {},
    })).toEqual({ status: "available", formattedValue: "0 m" });
  });

  it("apresenta metadados do histórico sem inferir temas ausentes", () => {
    const run: AnalysisRun = {
      id: "run-1",
      project_version_id: "version-1",
      status: "failed",
      run_at: "2026-07-20T12:00:00Z",
      started_at: "2026-07-20T12:00:01Z",
      completed_at: "2026-07-20T12:00:03Z",
      duration_ms: 2340,
      config: { themes: ["territorial", "road_network"] },
      error: { message: "Camada obrigatória ausente" },
    };

    expect(runStatusLabel(run.status)).toBe("Falhou");
    expect(runThemes(run)).toEqual(["Território", "Sistema viário"]);
    expect(formatDuration(run.duration_ms)).toBe("2,3 s");
  });
});
