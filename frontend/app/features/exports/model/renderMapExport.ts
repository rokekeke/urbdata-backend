import type { FeatureCollection } from "geojson";
import type { Map as MapLibreMap, StyleSpecification } from "maplibre-gl";

import type { Basemap } from "../../catalog/api/listBasemaps";
import type { LayerStyleConfig, MapViewport } from "../../../lib/types";
import { compileFillColor, dashArray, resolveLayerPresentation } from "../../../lib/styleCompiler";
import type { ExportImageSpec } from "./exportPresets";

interface RenderMapExportInput {
  image: ExportImageSpec;
  viewport: MapViewport;
  layers: LayerStyleConfig[];
  geojsonByLayerId: Record<string, FeatureCollection>;
  basemap: Basemap | null;
  legend: boolean;
  projectName: string;
  documentName: string;
}

const EMPTY_STYLE: StyleSpecification = {
  version: 8,
  sources: {},
  layers: [{ id: "background", type: "background", paint: { "background-color": "#e8e6df" } }],
};

function waitForLoad(map: MapLibreMap): Promise<void> {
  return new Promise((resolve, reject) => {
    const timeout = window.setTimeout(() => {
      cleanup();
      reject(new Error("O mapa-base demorou demais para preparar a exportação."));
    }, 20_000);
    const onLoad = () => { cleanup(); resolve(); };
    const onError = (event: { error?: Error }) => {
      if (!map.loaded()) { cleanup(); reject(event.error ?? new Error("Falha ao preparar o mapa-base.")); }
    };
    const cleanup = () => {
      window.clearTimeout(timeout);
      map.off("load", onLoad);
      map.off("error", onError);
    };
    map.on("load", onLoad);
    map.on("error", onError);
  });
}

function waitForIdle(map: MapLibreMap): Promise<void> {
  return new Promise((resolve, reject) => {
    const timeout = window.setTimeout(() => {
      cleanup();
      reject(new Error("Nem todos os elementos do mapa ficaram prontos a tempo. Tente novamente."));
    }, 20_000);
    const onReady = () => {
      window.requestAnimationFrame(() => {
        cleanup();
        resolve();
      });
    };
    const eventName = map.loaded() ? "render" : "idle";
    const cleanup = () => {
      window.clearTimeout(timeout);
      map.off(eventName, onReady);
    };
    map.on(eventName, onReady);
    map.triggerRepaint();
  });
}

function addOperationalLayers(map: MapLibreMap, input: RenderMapExportInput) {
  input.layers.forEach((layer) => {
    const collection = input.geojsonByLayerId[layer.id];
    if (!collection) return;
    const renderLayer = resolveLayerPresentation(layer, collection);
    const sourceId = `urbdata-export-source-${layer.id}`;
    map.addSource(sourceId, { type: "geojson", data: collection });
    const visibility = layer.visible ? "visible" : "none";

    if (layer.geometry === "polygon") {
      map.addLayer({
        id: `urbdata-export-fill-${layer.id}`,
        type: "fill",
        source: sourceId,
        layout: { visibility },
        paint: { "fill-color": compileFillColor(renderLayer), "fill-opacity": layer.opacity },
      });
      map.addLayer({
        id: `urbdata-export-stroke-${layer.id}`,
        type: "line",
        source: sourceId,
        layout: { visibility },
        paint: {
          "line-color": layer.strokeColor,
          "line-width": layer.strokeWidth,
          "line-opacity": layer.opacity,
          "line-dasharray": dashArray(layer.lineStyle) ?? [1, 0],
        },
      });
      return;
    }
    if (layer.geometry === "point") {
      map.addLayer({
        id: `urbdata-export-point-${layer.id}`,
        type: "circle",
        source: sourceId,
        layout: { visibility },
        paint: {
          "circle-color": compileFillColor(renderLayer),
          "circle-radius": Math.max(4, layer.strokeWidth * 2),
          "circle-opacity": layer.opacity,
          "circle-stroke-color": layer.strokeColor,
          "circle-stroke-width": 1,
        },
      });
      return;
    }
    map.addLayer({
      id: `urbdata-export-line-${layer.id}`,
      type: "line",
      source: sourceId,
      layout: { visibility, "line-cap": "round", "line-join": "round" },
      paint: {
        "line-color": compileFillColor(renderLayer),
        "line-width": layer.strokeWidth,
        "line-opacity": layer.opacity,
        "line-dasharray": dashArray(layer.lineStyle) ?? [1, 0],
      },
    });
  });
}

function drawFurniture(
  context: CanvasRenderingContext2D,
  input: RenderMapExportInput,
  scale: number,
) {
  const unit = (value: number) => value * scale;
  context.save();
  context.textBaseline = "top";

  context.fillStyle = "rgba(251,250,247,.94)";
  context.fillRect(unit(18), unit(18), unit(390), unit(66));
  context.fillStyle = "#66726e";
  context.font = `600 ${unit(9)}px Arial, sans-serif`;
  context.fillText(input.projectName.toUpperCase(), unit(32), unit(31), unit(360));
  context.fillStyle = "#172a25";
  context.font = `600 ${unit(18)}px Arial, sans-serif`;
  context.fillText(input.documentName, unit(32), unit(48), unit(360));

  const northX = input.image.width_px - unit(42);
  context.fillStyle = "rgba(251,250,247,.9)";
  context.fillRect(northX - unit(18), unit(18), unit(36), unit(58));
  context.fillStyle = "#172a25";
  context.font = `700 ${unit(10)}px Arial, sans-serif`;
  context.textAlign = "center";
  context.fillText("N", northX, unit(27));
  context.beginPath();
  context.moveTo(northX, unit(43));
  context.lineTo(northX - unit(7), unit(66));
  context.lineTo(northX + unit(7), unit(66));
  context.closePath();
  context.fill();

  if (input.legend) {
    const visible = input.layers.filter((layer) => layer.visible);
    const shown = visible.slice(0, 12);
    const legendHeight = unit(40 + shown.length * 22 + (visible.length > shown.length ? 18 : 0));
    const legendY = input.image.height_px - legendHeight - unit(22);
    context.textAlign = "left";
    context.fillStyle = "rgba(251,250,247,.94)";
    context.fillRect(unit(18), legendY, unit(250), legendHeight);
    context.fillStyle = "#66726e";
    context.font = `700 ${unit(9)}px Arial, sans-serif`;
    context.fillText("LEGENDA", unit(32), legendY + unit(16));
    shown.forEach((layer, index) => {
      const y = legendY + unit(37 + index * 22);
      context.fillStyle = layer.color;
      context.strokeStyle = layer.strokeColor;
      context.lineWidth = unit(Math.max(1, layer.strokeWidth));
      if (layer.geometry === "line") {
        context.beginPath();
        context.moveTo(unit(33), y + unit(6));
        context.lineTo(unit(48), y + unit(6));
        context.stroke();
      } else {
        context.fillRect(unit(33), y, unit(13), unit(13));
        context.strokeRect(unit(33), y, unit(13), unit(13));
      }
      context.fillStyle = "#384541";
      context.font = `500 ${unit(10)}px Arial, sans-serif`;
      context.fillText(layer.shortName, unit(58), y, unit(190));
    });
    if (visible.length > shown.length) {
      context.fillStyle = "#66726e";
      context.font = `500 ${unit(9)}px Arial, sans-serif`;
      context.fillText(`+ ${visible.length - shown.length} camadas`, unit(33), legendY + legendHeight - unit(20));
    }
  }

  if (input.basemap?.attribution) {
    context.textAlign = "right";
    context.font = `500 ${unit(8)}px Arial, sans-serif`;
    const x = input.image.width_px - unit(10);
    const y = input.image.height_px - unit(14);
    const width = context.measureText(input.basemap.attribution).width;
    context.fillStyle = "rgba(255,255,255,.78)";
    context.fillRect(x - width - unit(5), y - unit(2), width + unit(7), unit(13));
    context.fillStyle = "#555f5b";
    context.fillText(input.basemap.attribution, x, y);
  }
  context.restore();
}

function canvasToPng(canvas: HTMLCanvasElement): Promise<Blob> {
  return new Promise((resolve, reject) => {
    canvas.toBlob((blob) => {
      if (blob) resolve(blob);
      else reject(new Error("O navegador não conseguiu gerar o arquivo PNG."));
    }, "image/png");
  });
}

export async function renderMapExport(input: RenderMapExportInput): Promise<Blob> {
  const { default: maplibregl } = await import("maplibre-gl");
  const scale = input.image.resolution_id === "2x" ? 2 : 1;
  const container = document.createElement("div");
  Object.assign(container.style, {
    position: "fixed",
    left: "-100000px",
    top: "0",
    width: `${input.image.width_px / scale}px`,
    height: `${input.image.height_px / scale}px`,
    pointerEvents: "none",
  });
  document.body.appendChild(container);

  const map = new maplibregl.Map({
    container,
    style: input.basemap?.style_url ?? EMPTY_STYLE,
    center: [input.viewport.longitude, input.viewport.latitude],
    zoom: input.viewport.zoom,
    bearing: input.viewport.bearing,
    pitch: input.viewport.pitch,
    interactive: false,
    attributionControl: false,
    canvasContextAttributes: { preserveDrawingBuffer: true },
  });
  map.setPixelRatio(scale);

  try {
    await waitForLoad(map);
    addOperationalLayers(map, input);
    await waitForIdle(map);
    const output = document.createElement("canvas");
    output.width = input.image.width_px;
    output.height = input.image.height_px;
    const context = output.getContext("2d");
    if (!context) throw new Error("O navegador não disponibilizou o canvas de exportação.");
    context.drawImage(map.getCanvas(), 0, 0, output.width, output.height);
    drawFurniture(context, input, scale);
    return await canvasToPng(output);
  } finally {
    map.remove();
    container.remove();
  }
}
