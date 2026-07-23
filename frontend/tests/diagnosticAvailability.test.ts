import { describe, expect, it } from "vitest";

import type { CatalogIndicator } from "../app/features/catalog/api/listCatalogIndicators";
import {
  buildDiagnosticThemes,
  selectedBackendThemes,
} from "../app/features/diagnostics/model/diagnosticAvailability";
import type { LayerStyleConfig } from "../app/lib/types";

function indicator(theme: string, requiredLayers: string[]): CatalogIndicator {
  return {
    code: `${theme}.test`,
    theme,
    display_name: `Indicador ${theme}`,
    description: "Indicador de teste",
    unit: "m2",
    formula_version: "1.0.0",
    granularity: "projeto",
    value_shape: "scalar",
    category_feature_property: null,
    feature_key: null,
    internal: false,
    required_layers: requiredLayers,
    optional_layers: [],
  };
}

function layer(layerType: NonNullable<LayerStyleConfig["layerType"]>, status: NonNullable<LayerStyleConfig["status"]> = "mapped"): LayerStyleConfig {
  return {
    id: `layer-${layerType}`,
    name: layerType,
    shortName: layerType,
    geometry: layerType === "sistema_viario" ? "line" : "polygon",
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
    layerType,
    status,
  };
}

const catalog = [
  indicator("territorial", ["perimetro", "territorio"]),
  indicator("land_use", ["territorio"]),
  indicator("density", ["territorio"]),
  indicator("quadras", ["territorio"]),
  indicator("lots", ["territorio"]),
  indicator("green_areas", ["territorio", "perimetro"]),
  indicator("road_network", ["sistema_viario"]),
];

describe("diagnosticAvailability", () => {
  it("aplica o perímetro como requisito global de todos os temas", () => {
    const themes = buildDiagnosticThemes(catalog, [layer("territorio"), layer("sistema_viario")]);
    expect(themes.every((theme) => theme.status === "blocked")).toBe(true);
    expect(themes[0].requirements.some((requirement) => requirement.layerType === "perimetro" && requirement.state === "missing")).toBe(true);
  });

  it("libera temas com camadas mapeadas e mantém o viário bloqueado quando falta o eixo", () => {
    const themes = buildDiagnosticThemes(catalog, [layer("perimetro"), layer("territorio")]);
    expect(themes.find((theme) => theme.id === "territorio")?.status).toBe("available");
    expect(themes.find((theme) => theme.id === "quadras-lotes")?.status).toBe("available");
    expect(themes.find((theme) => theme.id === "sistema-viario")).toMatchObject({
      status: "blocked",
      nextAction: "Abra Dados para adicionar ou corrigir as bases indicadas.",
    });
  });

  it("diferencia camada presente sem mapeamento confirmado de camada com erro", () => {
    const attention = buildDiagnosticThemes(catalog, [layer("perimetro"), layer("territorio", "uploaded")]);
    const blocked = buildDiagnosticThemes(catalog, [layer("perimetro"), layer("territorio", "error")]);
    expect(attention.find((theme) => theme.id === "densidade")?.status).toBe("attention");
    expect(blocked.find((theme) => theme.id === "densidade")?.status).toBe("blocked");
  });

  it("converte o agrupamento Quadras e lotes nos dois temas aceitos pelo backend", () => {
    const themes = buildDiagnosticThemes(catalog, [layer("perimetro"), layer("territorio")]);
    expect(selectedBackendThemes(themes, ["quadras-lotes", "sistema-viario"])).toEqual(["quadras", "lots"]);
  });
});
