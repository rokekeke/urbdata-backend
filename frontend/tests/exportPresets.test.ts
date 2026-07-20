import { describe, expect, it } from "vitest";

import { exportFileName, exportImageSpec } from "../app/features/exports/model/exportPresets";
import { resolveLayerPresentation } from "../app/lib/styleCompiler";
import type { LayerStyleConfig } from "../app/lib/types";

const layer: LayerStyleConfig = {
  id: "layer-1",
  name: "Lotes",
  shortName: "Lotes",
  geometry: "polygon",
  visible: true,
  opacity: 0.7,
  color: "#D6B17B",
  secondaryColor: "#3D6F78",
  strokeColor: "#384541",
  strokeWidth: 1,
  lineStyle: "solid",
  representation: "zona",
  mode: "categorical",
  palette: ["#D6B17B", "#3D6F78"],
  representationOptions: [],
};

describe("presets de exportação", () => {
  it("aplica a escala 2x sem alterar a proporção", () => {
    expect(exportImageSpec("four_by_three", "2x")).toEqual({
      ratio_id: "four_by_three",
      resolution_id: "2x",
      width_px: 2400,
      height_px: 1800,
    });
  });

  it("gera nome de arquivo seguro e legível", () => {
    expect(exportFileName("Diagnóstico territorial · São José")).toBe("diagnostico-territorial-sao-jose.png");
  });

  it("resolve categorias diretamente dos dados quando o documento só possui a paleta", () => {
    const resolved = resolveLayerPresentation(layer, {
      type: "FeatureCollection",
      features: [
        { type: "Feature", properties: { zona: "B" }, geometry: { type: "Point", coordinates: [0, 0] } },
        { type: "Feature", properties: { zona: "A" }, geometry: { type: "Point", coordinates: [1, 1] } },
      ],
    });
    expect(resolved.categories).toEqual({ A: "#D6B17B", B: "#3D6F78" });
  });

  it("resolve o domínio numérico usado pelo gradiente", () => {
    const resolved = resolveLayerPresentation({ ...layer, mode: "sequential", categories: undefined }, {
      type: "FeatureCollection",
      features: [
        { type: "Feature", properties: { zona: 12 }, geometry: { type: "Point", coordinates: [0, 0] } },
        { type: "Feature", properties: { zona: 42 }, geometry: { type: "Point", coordinates: [1, 1] } },
      ],
    });
    expect(resolved.range).toEqual([12, 42]);
  });
});
