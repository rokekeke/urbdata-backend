import type { ExpressionSpecification } from "maplibre-gl";
import type { FeatureCollection } from "geojson";
import type { LayerStyleConfig } from "./types";

export function compileFillColor(layer: LayerStyleConfig): string | ExpressionSpecification {
  if (layer.mode === "single" || layer.representation === "single") return layer.color;

  if (layer.mode === "categorical" && layer.categories) {
    const pairs = Object.entries(layer.categories).flatMap(([value, color]) => [value, color]);
    return ["match", ["to-string", ["get", layer.representation]], ...pairs, "#b7b5ae"] as ExpressionSpecification;
  }

  const [min, max] = layer.range ?? [0, 100];
  if (layer.mode === "diverging") {
    const midpoint = min + (max - min) / 2;
    return [
      "interpolate",
      ["linear"],
      ["to-number", ["get", layer.representation], midpoint],
      min,
      layer.color,
      midpoint,
      "#f4f2ed",
      max,
      layer.secondaryColor,
    ] as ExpressionSpecification;
  }
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

export function resolveLayerPresentation(
  layer: LayerStyleConfig,
  collection: FeatureCollection | undefined,
): LayerStyleConfig {
  if (!collection || layer.representation === "single") return layer;
  const values = collection.features
    .map((feature) => feature.properties?.[layer.representation])
    .filter((value) => value !== null && value !== undefined && value !== "");

  if (layer.mode === "categorical" && !layer.categories && layer.palette?.length) {
    const palette = layer.palette;
    const distinct = [...new Set(values.map(String))].sort((left, right) => left.localeCompare(right, "pt-BR"));
    return {
      ...layer,
      categories: Object.fromEntries(
        distinct.map((value, index) => [value, palette[index % palette.length]]),
      ),
    };
  }

  if ((layer.mode === "sequential" || layer.mode === "diverging") && !layer.range) {
    const numeric = values
      .map(Number)
      .filter((value) => Number.isFinite(value));
    if (numeric.length > 0) return { ...layer, range: [Math.min(...numeric), Math.max(...numeric)] };
  }
  return layer;
}
