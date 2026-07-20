"use client";

import { useEffect, useRef } from "react";
import type { Map as MapLibreMap, MapLayerMouseEvent } from "maplibre-gl";
import { sampleGeojson } from "../lib/mockData";
import { compileFillColor, dashArray } from "../lib/styleCompiler";
import { useWorkspaceStore } from "../store/useWorkspaceStore";

interface MapCanvasProps {
  onCanvasReady: (getter: (() => HTMLCanvasElement | null) | null) => void;
}

export default function MapCanvas({ onCanvasReady }: MapCanvasProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<MapLibreMap | null>(null);
  const layers = useWorkspaceStore((state) => state.layers);
  const basemap = useWorkspaceStore((state) => state.basemap);
  const selectLayer = useWorkspaceStore((state) => state.selectLayer);

  useEffect(() => {
    if (!containerRef.current || mapRef.current) return;
    let disposed = false;

    void import("maplibre-gl").then(({ default: maplibregl }) => {
      if (disposed || !containerRef.current) return;
      const map = new maplibregl.Map({
        container: containerRef.current,
        canvasContextAttributes: { preserveDrawingBuffer: true },
        attributionControl: false,
        style: {
          version: 8,
          sources: {
            osm: {
              type: "raster",
              tiles: ["https://tile.openstreetmap.org/{z}/{x}/{y}.png"],
              tileSize: 256,
              attribution: "© OpenStreetMap contributors",
            },
          },
          layers: [
            { id: "background", type: "background", paint: { "background-color": "#e8e6df" } },
            { id: "basemap-osm", type: "raster", source: "osm", layout: { visibility: "none" }, paint: { "raster-opacity": 0.48, "raster-saturation": -0.82, "raster-contrast": -0.12 } },
          ],
        },
        center: [-48.501, -27.611],
        zoom: 14.6,
        pitch: 0,
        bearing: 0,
      });

      map.addControl(new maplibregl.NavigationControl({ showCompass: true }), "top-right");
      map.addControl(new maplibregl.ScaleControl({ unit: "metric", maxWidth: 120 }), "bottom-right");

      map.on("load", () => {
        layers.forEach((layer) => {
          map.addSource(`source-${layer.id}`, { type: "geojson", data: sampleGeojson[layer.id] });
          if (layer.geometry === "polygon") {
            map.addLayer({
              id: `fill-${layer.id}`,
              type: "fill",
              source: `source-${layer.id}`,
              paint: {
                "fill-color": compileFillColor(layer),
                "fill-opacity": layer.opacity,
              },
              layout: { visibility: layer.visible ? "visible" : "none" },
            });
            map.addLayer({
              id: `stroke-${layer.id}`,
              type: "line",
              source: `source-${layer.id}`,
              paint: {
                "line-color": layer.strokeColor,
                "line-width": layer.strokeWidth,
                "line-opacity": layer.opacity,
                ...(dashArray(layer.lineStyle) ? { "line-dasharray": dashArray(layer.lineStyle) } : {}),
              },
              layout: { visibility: layer.visible ? "visible" : "none" },
            });
          } else if (layer.geometry === "line") {
            map.addLayer({
              id: `line-${layer.id}`,
              type: "line",
              source: `source-${layer.id}`,
              paint: {
                "line-color": compileFillColor(layer),
                "line-width": layer.strokeWidth,
                "line-opacity": layer.opacity,
                ...(dashArray(layer.lineStyle) ? { "line-dasharray": dashArray(layer.lineStyle) } : {}),
              },
              layout: { visibility: layer.visible ? "visible" : "none", "line-cap": "round", "line-join": "round" },
            });
          }

          const interactiveIds = [`fill-${layer.id}`, `line-${layer.id}`, `stroke-${layer.id}`].filter((id) => map.getLayer(id));
          interactiveIds.forEach((id) => {
            map.on("click", id, (() => selectLayer(layer.id)) as (event: MapLayerMouseEvent) => void);
            map.on("mouseenter", id, () => { map.getCanvas().style.cursor = "pointer"; });
            map.on("mouseleave", id, () => { map.getCanvas().style.cursor = ""; });
          });
        });
        onCanvasReady(() => map.getCanvas());
      });

      mapRef.current = map;
    });

    return () => {
      disposed = true;
      onCanvasReady(null);
      mapRef.current?.remove();
      mapRef.current = null;
    };
  }, []);

  useEffect(() => {
    const map = mapRef.current;
    if (!map?.isStyleLoaded()) return;
    layers.forEach((layer) => {
      const visibility = layer.visible ? "visible" : "none";
      const ids = [`fill-${layer.id}`, `stroke-${layer.id}`, `line-${layer.id}`];
      ids.forEach((id) => {
        if (!map.getLayer(id)) return;
        map.setLayoutProperty(id, "visibility", visibility);
      });

      if (map.getLayer(`fill-${layer.id}`)) {
        map.setPaintProperty(`fill-${layer.id}`, "fill-color", compileFillColor(layer));
        map.setPaintProperty(`fill-${layer.id}`, "fill-opacity", layer.opacity);
      }
      const lineId = map.getLayer(`line-${layer.id}`) ? `line-${layer.id}` : `stroke-${layer.id}`;
      if (map.getLayer(lineId)) {
        map.setPaintProperty(lineId, "line-color", layer.geometry === "line" ? compileFillColor(layer) : layer.strokeColor);
        map.setPaintProperty(lineId, "line-width", layer.strokeWidth);
        map.setPaintProperty(lineId, "line-opacity", layer.opacity);
        map.setPaintProperty(lineId, "line-dasharray", dashArray(layer.lineStyle) ?? [1, 0]);
      }
    });

    // Mantém o empilhamento do MapLibre sincronizado com a ordem exibida
    // no painel de camadas. O array é percorrido da base para o topo.
    layers.forEach((layer) => {
      const mapLayerIds = layer.geometry === "polygon"
        ? [`fill-${layer.id}`, `stroke-${layer.id}`]
        : [`line-${layer.id}`];

      mapLayerIds.forEach((id) => {
        if (map.getLayer(id)) map.moveLayer(id);
      });
    });
  }, [layers]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map?.isStyleLoaded() || !map.getLayer("basemap-osm")) return;
    map.setLayoutProperty("basemap-osm", "visibility", basemap === "osm" ? "visible" : "none");
    map.setPaintProperty("background", "background-color", basemap === "osm" ? "#e3e2dc" : "#e8e6df");
  }, [basemap]);

  return <div ref={containerRef} className="map-canvas" aria-label="Pré-visualização cartográfica interativa" />;
}
