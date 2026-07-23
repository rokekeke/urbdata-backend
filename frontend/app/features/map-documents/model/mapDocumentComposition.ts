import type { components } from "../../../lib/api/schema";
import type { BasemapId, LayerStyleConfig, MapViewport } from "../../../lib/types";
import type { WritableMapDocumentConfig } from "../api/mapDocuments";

export type MapDocumentConfig = components["schemas"]["MapDocumentConfig"];
export type DocumentLayer = components["schemas"]["DocumentLayer"];
type WritableDocumentLayer = NonNullable<WritableMapDocumentConfig["layers"]>[number];

export const DEFAULT_VIEWPORT: MapViewport = {
  longitude: -48.501,
  latitude: -27.611,
  zoom: 12,
  bearing: 0,
  pitch: 0,
};

function hexToRgb(hex: string): [number, number, number] {
  const normalized = hex.replace("#", "").slice(0, 6);
  return [0, 2, 4].map((offset) => Number.parseInt(normalized.slice(offset, offset + 2), 16)) as [number, number, number];
}

function rgbToHex(rgb: [number, number, number]): string {
  return `#${rgb.map((channel) => Math.round(channel).toString(16).padStart(2, "0")).join("")}`;
}

function colorRamp(start: string, end: string, classes = 5): string[] {
  const from = hexToRgb(start);
  const to = hexToRgb(end);
  return Array.from({ length: classes }, (_, index) => {
    const ratio = classes === 1 ? 0 : index / (classes - 1);
    return rgbToHex(from.map((channel, channelIndex) => (
      channel + (to[channelIndex] - channel) * ratio
    )) as [number, number, number]);
  });
}

function layerPalette(layer: LayerStyleConfig): string[] {
  if (layer.mode === "categorical" && layer.categories) return Object.values(layer.categories);
  if (layer.palette?.length) return layer.palette;
  return colorRamp(layer.color, layer.secondaryColor);
}

function serializeRepresentation(layer: LayerStyleConfig): WritableDocumentLayer["representation"] {
  const option = layer.representationOptions.find((item) => item.value === layer.representation);
  if (layer.representation === "single" || !option) {
    return { source: "none", mode: "single", null_behavior: "transparent" };
  }

  const source = option.source === "indicator" ? "indicator" : "property";
  const fieldReference = source === "indicator"
    ? { indicator_code: layer.representation }
    : { field: layer.representation };
  if (layer.mode === "single") {
    return { source, ...fieldReference, mode: "single", null_behavior: "transparent" };
  }

  const palette = layerPalette(layer);
  return {
    source,
    ...fieldReference,
    mode: layer.mode,
    scale: layer.mode === "categorical" ? "ordinal" : "quantize",
    classes: palette.length,
    null_behavior: "transparent",
  };
}

function serializeLayer(layer: LayerStyleConfig): WritableDocumentLayer {
  const representation = serializeRepresentation(layer);
  const usesPalette = representation.mode !== "single";
  return {
    layer_id: layer.id,
    visible: layer.visible,
    representation,
    style: {
      fill: {
        color: usesPalette ? null : layer.color,
        palette: usesPalette ? layerPalette(layer) : null,
        opacity: layer.opacity,
      },
      stroke: {
        color: layer.strokeColor,
        width_px: layer.strokeWidth,
        style: layer.lineStyle,
        opacity: layer.opacity,
      },
      null_color: null,
    },
  };
}

export function serializeMapDocumentConfig(input: {
  name: string;
  layers: LayerStyleConfig[];
  basemap: BasemapId;
  viewport: MapViewport;
}): WritableMapDocumentConfig {
  const name = input.name.trim();
  if (!name) throw new Error("Informe um nome para a composição.");
  return {
    schema_version: "1",
    name,
    title: name,
    basemap_id: input.basemap,
    viewport: input.viewport,
    layers: input.layers.map(serializeLayer),
  };
}

function hydrateLayer(base: LayerStyleConfig, persisted: DocumentLayer): LayerStyleConfig {
  const palette = persisted.style.fill.palette ?? undefined;
  const representation = persisted.representation.field
    ?? persisted.representation.indicator_code
    ?? "single";
  const option = base.representationOptions.find((item) => item.value === representation);
  const representationOptions = option || representation === "single"
    ? base.representationOptions
    : [...base.representationOptions, {
        value: representation,
        label: representation,
        type: persisted.representation.mode === "categorical" ? "text" as const : "number" as const,
        source: persisted.representation.source === "indicator" ? "indicator" as const : "mapped" as const,
      }];
  const categories = option?.distinctValues && palette
    ? Object.fromEntries(option.distinctValues.map((value, index) => [value, palette[index % palette.length]]))
    : undefined;
  return {
    ...base,
    visible: persisted.visible,
    opacity: persisted.style.fill.opacity,
    color: persisted.style.fill.color ?? palette?.[0] ?? base.color,
    secondaryColor: palette?.at(-1) ?? base.secondaryColor,
    palette,
    strokeColor: persisted.style.stroke.color,
    strokeWidth: persisted.style.stroke.width_px,
    lineStyle: persisted.style.stroke.style,
    representation,
    representationOptions,
    mode: persisted.representation.mode,
    categories,
  };
}

export function hydrateMapDocumentLayers(
  availableLayers: LayerStyleConfig[],
  config: MapDocumentConfig,
): LayerStyleConfig[] {
  const availableById = new Map(availableLayers.map((layer) => [layer.id, layer]));
  const persistedIds = new Set(config.layers?.map((layer) => layer.layer_id) ?? []);
  const hydrated = (config.layers ?? []).flatMap((persisted) => {
    const base = availableById.get(persisted.layer_id);
    return base ? [hydrateLayer(base, persisted)] : [];
  });
  const newLayers = availableLayers
    .filter((layer) => !persistedIds.has(layer.id))
    .map((layer) => ({ ...layer, visible: false }));
  return [...hydrated, ...newLayers];
}
