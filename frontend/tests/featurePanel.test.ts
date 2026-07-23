import { describe, expect, it } from "vitest";

import type { CatalogIndicator } from "../app/features/catalog/api/listCatalogIndicators";
import {
  buildFeatureIndicatorRows,
  formatFeatureValue,
  selectFeatureProperties,
} from "../app/features/feature-panel/model/featurePanel";
import type { IndicatorResult } from "../app/features/results/api/listProjectResults";
import type { SelectedFeature } from "../app/store/useWorkspaceStore";

const feature: SelectedFeature = {
  layerId: "layer-1",
  featureId: "71a3929f-55c1-4cef-8d8a-351c918aa228",
  properties: { nome: "Quadra Central", quadra_id: 42, zona: "ZC", vazio: null },
};

function indicator(
  code: string,
  featureKey: CatalogIndicator["feature_key"] = "feature_id",
  granularity: CatalogIndicator["granularity"] = "por_feicao",
): CatalogIndicator {
  return {
    code,
    theme: "território",
    display_name: `Indicador ${code}`,
    description: "Indicador para teste",
    unit: "%",
    formula_version: "1.0.0",
    granularity,
    value_shape: granularity === "por_feicao" ? "feature_series" : "scalar",
    category_feature_property: null,
    feature_key: featureKey,
    internal: false,
    required_layers: ["territorio"],
    optional_layers: [],
  };
}

function result(code: string, value: IndicatorResult["value"]): IndicatorResult {
  return {
    indicator_code: code,
    theme: "território",
    formula_version: "1.1.0",
    value,
    unit: "%",
    metric_crs: "EPSG:31983",
    parameters: {},
    source_layers: ["layer-1"],
    contributing_feature_ids: [feature.featureId],
    warnings: [],
  };
}

describe("featurePanel", () => {
  it("associa resultados por feature.id e preserva zero como valor disponível", () => {
    const rows = buildFeatureIndicatorRows({
      catalog: [indicator("ocupacao")],
      results: [result("ocupacao", { [feature.featureId]: 0 })],
      selectedFeature: feature,
      compatibleIndicatorCodes: ["ocupacao"],
    });

    expect(rows).toHaveLength(1);
    expect(rows[0]).toMatchObject({ status: "available", rawValue: 0, formattedValue: "0" });
  });

  it("usa a propriedade quadra_id quando o catálogo declara essa chave", () => {
    const rows = buildFeatureIndicatorRows({
      catalog: [indicator("densidade", "quadra_id")],
      results: [result("densidade", { "42": 138.456 })],
      selectedFeature: feature,
      compatibleIndicatorCodes: ["densidade"],
    });

    expect(rows[0]).toMatchObject({ status: "available", rawValue: 138.456, formattedValue: "138,46" });
  });

  it("distingue sem dado, não calculado e não aplicável", () => {
    const rows = buildFeatureIndicatorRows({
      catalog: [
        indicator("sem_dado"),
        indicator("nao_calculado"),
        indicator("sem_quadra", "quadra_id"),
      ],
      results: [result("sem_dado", { [feature.featureId]: null })],
      selectedFeature: { ...feature, properties: {} },
      compatibleIndicatorCodes: ["sem_dado", "nao_calculado", "sem_quadra"],
    });

    expect(Object.fromEntries(rows.map((row) => [row.code, row.status]))).toEqual({
      nao_calculado: "not_calculated",
      sem_dado: "no_data",
      sem_quadra: "missing_key",
    });
  });

  it("exclui indicadores de projeto e indicadores incompatíveis com a camada", () => {
    const rows = buildFeatureIndicatorRows({
      catalog: [indicator("compativel"), indicator("projeto", null, "projeto"), indicator("outra_camada")],
      results: [],
      selectedFeature: feature,
      compatibleIndicatorCodes: ["compativel", "projeto"],
    });

    expect(rows.map((row) => row.code)).toEqual(["compativel"]);
  });

  it("prioriza campos territoriais e formata valores sem inventar conteúdo", () => {
    const rows = selectFeatureProperties({
      observacao: "Centro",
      area_m2: 1234.5,
      nome: "Quadra A",
      quadra_id: 8,
      ativo: false,
      vazio: null,
      adicional: "fora do limite",
    });

    expect(rows.map((row) => row.key)).toEqual([
      "nome",
      "quadra_id",
      "adicional",
      "area_m2",
      "ativo",
      "observacao",
    ]);
    expect(formatFeatureValue(null)).toBe("Sem dado");
    expect(formatFeatureValue(false)).toBe("Não");
    expect(formatFeatureValue({ total: 2 })).toBe("Valor composto");
  });
});
