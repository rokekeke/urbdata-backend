import { describe, expect, it } from "vitest";

import {
  DEFAULT_VIEWPORT,
  hydrateMapDocumentLayers,
  serializeMapDocumentConfig,
} from "../app/features/map-documents/model/mapDocumentComposition";
import type { LayerStyleConfig } from "../app/lib/types";

function layer(overrides: Partial<LayerStyleConfig> = {}): LayerStyleConfig {
  return {
    id: "11111111-1111-4111-8111-111111111111",
    name: "Lotes",
    shortName: "Lotes",
    geometry: "polygon",
    visible: true,
    opacity: 0.72,
    color: "#D6B17B",
    secondaryColor: "#3D6F78",
    strokeColor: "#384541",
    strokeWidth: 1.2,
    lineStyle: "solid",
    representation: "single",
    mode: "single",
    representationOptions: [
      { value: "single", label: "Estilo único", type: "text", source: "source" },
      { value: "zona", label: "zona", type: "text", source: "mapped", distinctValues: ["A", "B"] },
    ],
    ...overrides,
  };
}

describe("contrato da composição cartográfica", () => {
  it("serializa o rascunho simples sem blocos ainda não editáveis", () => {
    const config = serializeMapDocumentConfig({
      name: "Mapa de trabalho",
      layers: [layer()],
      basemap: "positron",
      viewport: DEFAULT_VIEWPORT,
    });

    expect(config).toMatchObject({
      schema_version: "1",
      name: "Mapa de trabalho",
      basemap_id: "positron",
      viewport: DEFAULT_VIEWPORT,
      layers: [{
        visible: true,
        representation: { source: "none", mode: "single" },
        style: { fill: { color: "#D6B17B", palette: null, opacity: 0.72 } },
      }],
    });
    expect(config.layers?.[0]).not.toHaveProperty("interaction");
    expect(config.layers?.[0].style).not.toHaveProperty("labels");
  });

  it("persiste paleta e escala ordinal para uma classificação categórica", () => {
    const config = serializeMapDocumentConfig({
      name: "Zoneamento",
      basemap: "none",
      viewport: DEFAULT_VIEWPORT,
      layers: [layer({
        representation: "zona",
        mode: "categorical",
        palette: ["#D6B17B", "#3D6F78"],
        categories: { A: "#D6B17B", B: "#3D6F78" },
      })],
    });

    expect(config.layers?.[0]).toMatchObject({
      representation: { source: "property", field: "zona", mode: "categorical", scale: "ordinal", classes: 2 },
      style: { fill: { color: null, palette: ["#D6B17B", "#3D6F78"] } },
    });
  });

  it("restaura a ordem salva e mantém novas camadas disponíveis como ocultas", () => {
    const saved = serializeMapDocumentConfig({
      name: "Mapa salvo",
      basemap: "none",
      viewport: DEFAULT_VIEWPORT,
      layers: [layer({ visible: false, strokeWidth: 3 })],
    });
    const extra = layer({ id: "22222222-2222-4222-8222-222222222222", name: "Quadras", shortName: "Quadras" });
    const hydrated = hydrateMapDocumentLayers([extra, layer()], saved);

    expect(hydrated.map((item) => item.id)).toEqual([
      "11111111-1111-4111-8111-111111111111",
      "22222222-2222-4222-8222-222222222222",
    ]);
    expect(hydrated[0]).toMatchObject({ visible: false, strokeWidth: 3 });
    expect(hydrated[1].visible).toBe(false);
  });

  it("impede salvar uma composição sem nome", () => {
    expect(() => serializeMapDocumentConfig({
      name: "   ",
      layers: [layer()],
      basemap: "none",
      viewport: DEFAULT_VIEWPORT,
    })).toThrow("Informe um nome");
  });
});
