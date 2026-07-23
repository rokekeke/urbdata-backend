import { describe, expect, it } from "vitest";

import type { CatalogIndicator } from "../app/features/catalog/api/listCatalogIndicators";
import type { AnalysisRun } from "../app/features/results/api/listProjectRuns";
import type { IndicatorResult } from "../app/features/results/api/listProjectResults";
import {
  buildCategoryShares,
  buildCompoundTable,
  buildDistributionEntries,
  buildResultIndicatorViews,
  buildResultOverlay,
  findGreenAreaPair,
  formatDuration,
  formatScalarValue,
  normalizeCategoryKey,
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
    value_shape: "scalar",
    category_feature_property: null,
    feature_key: null,
    internal: false,
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
      kind: "numeric",
      layerId: layer.id,
      featureKey: "feature_id",
      values: { "feature-1": 12, "feature-2": 0 },
      min: 0,
      max: 12,
    });
  });

  it("cria sobreposição categórica para distribuição com propriedade de feição", () => {
    const [view] = buildResultIndicatorViews(
      [catalogIndicator("territorial.area_by_category", {
        value_shape: "category_breakdown",
        category_feature_property: "macroarea",
        unit: "m2",
      })],
      [result("territorial.area_by_category", { lote: 6000, sistema_viario: 3000 }, "m2")],
    );
    const overlay = buildResultOverlay(view, [layer]);

    expect(overlay).toMatchObject({
      kind: "categorical",
      layerId: layer.id,
      property: "macroarea",
    });
    if (overlay?.kind !== "categorical") throw new Error("overlay categórico esperado");
    expect(overlay.categories.map((category) => category.key)).toEqual(["lote", "sistema_viario"]);
    expect(overlay.categories[1].normalizedKey).toBe("sistemaviario");
    expect(new Set(overlay.categories.map((category) => category.color)).size).toBe(2);
  });

  it("normaliza valor bruto e chave de categoria para a mesma forma", () => {
    expect(normalizeCategoryKey("SISTEMA VIÁRIO")).toBe("sistemaviario");
    expect(normalizeCategoryKey("sistema_viario")).toBe("sistemaviario");
    expect(normalizeCategoryKey("LOTE")).toBe("lote");
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

  it("monta participação por categoria com rótulos do vocabulário e soma 100%", () => {
    const [view] = buildResultIndicatorViews(
      [catalogIndicator("territorial.area_by_category", { value_shape: "category_breakdown", unit: "m2" })],
      [result("territorial.area_by_category", { lote: 6000, sistema_viario: 3000, avl: 1000 }, "m2")],
    );
    const shares = buildCategoryShares(view);

    expect(shares.map((entry) => entry.label)).toEqual(["Lote", "Sistema viário", "AVL"]);
    expect(shares[0].formattedShare).toBe("60 %");
    expect(shares[0].formattedValue).toBe("6.000 m²");
    expect(shares.reduce((total, entry) => total + entry.share, 0)).toBeCloseTo(1);
  });

  it("monta tabela composta com colunas rotuladas e valores por quadra", () => {
    const [view] = buildResultIndicatorViews(
      [catalogIndicator("quadras.stats", {
        theme: "quadras",
        value_shape: "feature_compound",
        granularity: "por_feicao",
        feature_key: "quadra_id",
        unit: "composto",
      })],
      [result("quadras.stats", {
        "Q-B": { area_m2: 2400.5, perimetro_m: 220, quantidade_lotes: 12 },
        "Q-A": { area_m2: 1800, perimetro_m: 180, quantidade_lotes: 8 },
      }, "composto")],
    );
    const table = buildCompoundTable(view);

    expect(table?.columns.map((column) => column.label)).toEqual([
      "Área (m²)",
      "Perímetro (m)",
      "Lotes",
    ]);
    expect(table?.rows.map((row) => row.key)).toEqual(["Q-A", "Q-B"]);
    expect(table?.rows[1].cells).toEqual(["2.400,5", "220", "12"]);
  });

  it("apresenta rótulo categórico e distingue empate de dado ausente", () => {
    const [predominant] = buildResultIndicatorViews(
      [catalogIndicator("land_use.predominant_use", { value_shape: "categorical_label", unit: "categoria" })],
      [result("land_use.predominant_use", "residencial", "categoria")],
    );
    const [tie] = buildResultIndicatorViews(
      [catalogIndicator("land_use.predominant_use", { value_shape: "categorical_label", unit: "categoria" })],
      [result("land_use.predominant_use", null, "categoria")],
    );

    expect(predominant.formattedValue).toBe("Residencial");
    expect(tie.formattedValue).toBe("Sem categoria predominante");
  });

  it("resolve valor composto da feição selecionada com rótulos legíveis", () => {
    const [view] = buildResultIndicatorViews(
      [catalogIndicator("quadras.stats", {
        theme: "quadras",
        value_shape: "feature_compound",
        granularity: "por_feicao",
        feature_key: "quadra_id",
        unit: "composto",
      })],
      [result("quadras.stats", { "Q-A": { area_m2: 1800, quantidade_lotes: 8 } }, "composto")],
    );

    expect(selectedFeatureResult(view, {
      layerId: layer.id,
      featureId: "feature-x",
      properties: { quadra_id: "Q-A" },
    })).toEqual({ status: "available", formattedValue: "Área (m²) 1.800 · Lotes 8" });
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

  it("propaga o campo internal do catálogo para a view (nota 88/97)", () => {
    const views = buildResultIndicatorViews(
      [
        catalogIndicator("quadras.face_length_score", { internal: true }),
        catalogIndicator("territorial.total_area", { internal: false }),
      ],
      [
        result("quadras.face_length_score", 0.8, "score"),
        result("territorial.total_area", 12000, "m2"),
      ],
    );

    expect(views.find((view) => view.code === "quadras.face_length_score")?.internal).toBe(true);
    expect(views.find((view) => view.code === "territorial.total_area")?.internal).toBe(false);
  });

  it("encontra o par AVL/AVL+APP e calcula o ganho, em qualquer direção", () => {
    const views = buildResultIndicatorViews(
      [
        catalogIndicator("green_areas.total_area", { theme: "green_areas", unit: "m2" }),
        catalogIndicator("green_areas.total_area_with_app", { theme: "green_areas", unit: "m2" }),
      ],
      [
        result("green_areas.total_area", 300, "m2"),
        result("green_areas.total_area_with_app", 784, "m2"),
      ],
    );
    const avlOnly = views.find((view) => view.code === "green_areas.total_area")!;
    const withApp = views.find((view) => view.code === "green_areas.total_area_with_app")!;

    const fromAvlOnly = findGreenAreaPair(avlOnly, views);
    const fromWithApp = findGreenAreaPair(withApp, views);

    expect(fromAvlOnly).toMatchObject({ avlOnlyValue: 300, withAppValue: 784, deltaFormatted: "484 m²" });
    expect(fromWithApp).toMatchObject({ avlOnlyValue: 300, withAppValue: 784, deltaFormatted: "484 m²" });
  });

  it("não forma par de área verde sem o parceiro na lista de views", () => {
    const views = buildResultIndicatorViews(
      [catalogIndicator("green_areas.total_area", { theme: "green_areas", unit: "m2" })],
      [result("green_areas.total_area", 300, "m2")],
    );

    expect(findGreenAreaPair(views[0], views)).toBeNull();
  });

  it("não forma par de área verde para indicadores fora da lista aditiva", () => {
    const views = buildResultIndicatorViews(
      [catalogIndicator("territorial.total_area")],
      [result("territorial.total_area", 12000, "m2")],
    );

    expect(findGreenAreaPair(views[0], views)).toBeNull();
  });
});
