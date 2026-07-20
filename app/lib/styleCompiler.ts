import type { ExpressionSpecification } from "maplibre-gl";
import type { LayerStyleConfig } from "./types";

export function compileFillColor(layer: LayerStyleConfig): string | ExpressionSpecification {
  if (layer.mode === "single" || layer.representation === "single") return layer.color;

  if (layer.mode === "categorical" && layer.categories) {
    const pairs = Object.entries(layer.categories).flatMap(([value, color]) => [value, color]);
    return ["match", ["to-string", ["get", layer.representation]], ...pairs, "#b7b5ae"] as ExpressionSpecification;
  }

  const [min, max] = layer.range ?? [0, 100];
  return [
    "interpolate",
    ["linear"],
    ["to-number", ["get", layer.representation], min],
    min,
    layer.color,
    max,
    layer.secondaryColor,
  ] as ExpressionSpecification;
}

export function dashArray(style: LayerStyleConfig["lineStyle"]): number[] | undefined {
  if (style === "dashed") return [3, 2];
  if (style === "dotted") return [0.5, 1.6];
  return undefined;
}

