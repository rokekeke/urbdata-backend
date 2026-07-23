"use client";

import { useEffect, useRef, useState } from "react";
import type { FeatureCollection } from "geojson";
import type { ExpressionSpecification, GeoJSONSource, Map as MapLibreMap } from "maplibre-gl";

import { useBasemaps } from "../features/catalog/hooks/useBasemaps";
import {
  CATEGORY_FALLBACK_COLOR,
  normalizeCategoryKey,
  type ResultOverlayDefinition,
} from "../features/results/model/resultsPresentation";
import { compileFillColor, dashArray, resolveLayerPresentation } from "../lib/styleCompiler";
import type { LayerStyleConfig } from "../lib/types";
import { useWorkspaceStore } from "../store/useWorkspaceStore";

interface MapCanvasProps {
  onCanvasReady?: (getter: (() => HTMLCanvasElement | null) | null) => void;
  resultOverlay?: MapResultOverlay | null;
}

export type MapResultOverlay = ResultOverlayDefinition;

const RESULT_PROPERTY = "__urbdata_result";
const EMPTY_MAP_STYLE = {
  version: 8 as const,
  sources: {},
  layers: [
    { id: "background", type: "background" as const, paint: { "background-color": "#e8e6df" } },
  ],
};

function mapLayerIds(layer: LayerStyleConfig): string[] {
  if (layer.geometry === "polygon") return [`fill-${layer.id}`, `stroke-${layer.id}`];
  if (layer.geometry === "point") return [`point-${layer.id}`];
  return [`line-${layer.id}`];
}

function selectionLayerId(layerId: string): string {
  return `selection-${layerId}`;
}

function dataBounds(collections: FeatureCollection[]): [[number, number], [number, number]] | null {
  let minX = Number.POSITIVE_INFINITY;
  let minY = Number.POSITIVE_INFINITY;
  let maxX = Number.NEGATIVE_INFINITY;
  let maxY = Number.NEGATIVE_INFINITY;

  function visit(value: unknown) {
    if (!Array.isArray(value)) return;
    if (value.length >= 2 && typeof value[0] === "number" && typeof value[1] === "number") {
      minX = Math.min(minX, value[0]);
      minY = Math.min(minY, value[1]);
      maxX = Math.max(maxX, value[0]);
      maxY = Math.max(maxY, value[1]);
      return;
    }
    value.forEach(visit);
  }

  collections.forEach((collection) => {
    collection.features.forEach((feature) => {
      if (feature.geometry.type === "GeometryCollection") {
        feature.geometry.geometries.forEach((geometry) => {
          if ("coordinates" in geometry) visit(geometry.coordinates);
        });
      } else {
        visit(feature.geometry.coordinates);
      }
    });
  });

  return Number.isFinite(minX) ? [[minX, minY], [maxX, maxY]] : null;
}

function collectionWithResult(
  collection: FeatureCollection,
  overlay: MapResultOverlay | null | undefined,
  layerId: string,
): FeatureCollection {
  if (!overlay || overlay.layerId !== layerId) return collection;

  if (overlay.kind === "categorical") {
    // A propriedade carrega o valor bruto mapeado ("SISTEMA VIÁRIO");
    // a junção normaliza dos dois lados, espelhando o normalize_key do
    // backend, e grava a chave canônica da categoria na feição.
    const byNormalized = new Map(
      overlay.categories.map((category) => [category.normalizedKey, category.key]),
    );
    return {
      ...collection,
      features: collection.features.map((feature) => {
        const properties = feature.properties ?? {};
        const rawValue = properties[overlay.property];
        const categoryKey = typeof rawValue === "string" && rawValue
          ? byNormalized.get(normalizeCategoryKey(rawValue))
          : undefined;
        return {
          ...feature,
          properties: categoryKey === undefined
            ? properties
            : { ...properties, [RESULT_PROPERTY]: categoryKey },
        };
      }),
    };
  }

  return {
    ...collection,
    features: collection.features.map((feature) => {
      const properties = feature.properties ?? {};
      const key = overlay.featureKey === "feature_id" ? feature.id : properties.quadra_id;
      const rawValue = typeof key === "string" || typeof key === "number"
        ? overlay.values[String(key)]
        : undefined;
      const numericValue = typeof rawValue === "number" && Number.isFinite(rawValue)
        ? rawValue
        : undefined;
      return {
        ...feature,
        properties: numericValue === undefined
          ? properties
          : { ...properties, [RESULT_PROPERTY]: numericValue },
      };
    }),
  };
}

function resultColor(overlay: MapResultOverlay): ExpressionSpecification {
  if (overlay.kind === "categorical") {
    const matchPairs = overlay.categories.flatMap((category) => [category.key, category.color]);
    // `matchPairs` nunca é vazio (buildResultOverlay devolve null sem
    // categorias), mas o spread impede o TS de provar a aridade mínima da
    // tupla "match" - daí o cast em duas etapas.
    const matchExpression = [
      "match",
      ["get", RESULT_PROPERTY],
      ...matchPairs,
      CATEGORY_FALLBACK_COLOR,
    ] as unknown as ExpressionSpecification;
    return [
      "case",
      ["has", RESULT_PROPERTY],
      matchExpression,
      CATEGORY_FALLBACK_COLOR,
    ] as ExpressionSpecification;
  }
  return [
    "case",
    ["has", RESULT_PROPERTY],
    [
      "interpolate",
      ["linear"],
      ["to-number", ["get", RESULT_PROPERTY], overlay.min],
      overlay.min,
      "#d8e7e6",
      overlay.max,
      "#29545d",
    ],
    "#d6d5cf",
  ] as ExpressionSpecification;
}

export default function MapCanvas({ onCanvasReady, resultOverlay }: MapCanvasProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<MapLibreMap | null>(null);
  const onCanvasReadyRef = useRef(onCanvasReady);
  const selectLayerRef = useRef(useWorkspaceStore.getState().selectLayer);
  const selectFeatureRef = useRef(useWorkspaceStore.getState().selectFeature);
  const clearFeatureSelectionRef = useRef(useWorkspaceStore.getState().clearFeatureSelection);
  const interactiveLayerIdsRef = useRef<string[]>([]);
  const geojsonByLayerIdRef = useRef(useWorkspaceStore.getState().geojsonByLayerId);
  const fittedDataSignature = useRef("");
  const activeBasemapStyleRef = useRef("none");
  const setViewportRef = useRef(useWorkspaceStore.getState().setViewport);
  const initialViewportRef = useRef(useWorkspaceStore.getState().viewport);
  const [isMapReady, setIsMapReady] = useState(false);
  const [styleRevision, setStyleRevision] = useState(0);
  const layers = useWorkspaceStore((state) => state.layers);
  const geojsonByLayerId = useWorkspaceStore((state) => state.geojsonByLayerId);
  const basemap = useWorkspaceStore((state) => state.basemap);
  const viewport = useWorkspaceStore((state) => state.viewport);
  const selectedFeature = useWorkspaceStore((state) => state.selectedFeature);
  const basemaps = useBasemaps();

  useEffect(() => {
    onCanvasReadyRef.current = onCanvasReady;
  }, [onCanvasReady]);

  useEffect(() => {
    geojsonByLayerIdRef.current = geojsonByLayerId;
  }, [geojsonByLayerId]);

  useEffect(() => {
    if (!containerRef.current || mapRef.current) return;
    let disposed = false;

    void import("maplibre-gl").then(({ default: maplibregl }) => {
      if (disposed || !containerRef.current) return;
      const initialViewport = initialViewportRef.current;
      const map = new maplibregl.Map({
        container: containerRef.current,
        canvasContextAttributes: { preserveDrawingBuffer: true },
        attributionControl: false,
        style: EMPTY_MAP_STYLE,
        center: [initialViewport.longitude, initialViewport.latitude],
        zoom: initialViewport.zoom,
        pitch: initialViewport.pitch,
        bearing: initialViewport.bearing,
      });

      map.addControl(new maplibregl.NavigationControl({ showCompass: true }), "top-right");
      map.addControl(new maplibregl.ScaleControl({ unit: "metric", maxWidth: 120 }), "bottom-right");
      map.on("load", () => {
        setIsMapReady(true);
        onCanvasReadyRef.current?.(() => map.getCanvas());
      });
      map.on("click", (event) => {
        const interactiveLayers = interactiveLayerIdsRef.current.filter((id) => map.getLayer(id));
        if (interactiveLayers.length === 0) {
          clearFeatureSelectionRef.current();
          return;
        }
        const features = map.queryRenderedFeatures(event.point, { layers: interactiveLayers });
        if (features.length === 0) clearFeatureSelectionRef.current();
      });
      map.on("moveend", () => {
        const center = map.getCenter();
        setViewportRef.current({
          longitude: center.lng,
          latitude: center.lat,
          zoom: map.getZoom(),
          bearing: map.getBearing(),
          pitch: map.getPitch(),
        });
      });
      mapRef.current = map;
    });

    return () => {
      disposed = true;
      setIsMapReady(false);
      onCanvasReadyRef.current?.(null);
      mapRef.current?.remove();
      mapRef.current = null;
    };
  }, []);

  useEffect(() => {
    const map = mapRef.current;
    if (!map || !isMapReady) return;
    const center = map.getCenter();
    const current = {
      longitude: center.lng,
      latitude: center.lat,
      zoom: map.getZoom(),
      bearing: map.getBearing(),
      pitch: map.getPitch(),
    };
    const differs = (Object.keys(viewport) as Array<keyof typeof viewport>).some(
      (key) => Math.abs(current[key] - viewport[key]) >= 0.000001,
    );
    if (differs) map.jumpTo({ center: [viewport.longitude, viewport.latitude], ...viewport });
  }, [isMapReady, viewport]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map || !isMapReady || activeBasemapStyleRef.current === basemap) return;
    const styleUrl = basemaps.data?.find((item) => item.id === basemap)?.style_url;
    if (basemap !== "none" && !styleUrl) return;

    activeBasemapStyleRef.current = basemap;
    map.once("style.load", () => {
      setStyleRevision((current) => current + 1);
      onCanvasReadyRef.current?.(() => map.getCanvas());
    });
    map.setStyle(styleUrl ?? EMPTY_MAP_STYLE);
  }, [basemap, basemaps.data, isMapReady]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map || !isMapReady) return;

    const expectedSourceIds = new Set(layers.map((layer) => `source-${layer.id}`));
    Object.keys(map.getStyle().sources)
      .filter((sourceId) => sourceId.startsWith("source-") && !expectedSourceIds.has(sourceId))
      .forEach((sourceId) => {
        const layerId = sourceId.slice("source-".length);
        [`fill-${layerId}`, `stroke-${layerId}`, `line-${layerId}`, `point-${layerId}`, selectionLayerId(layerId)].forEach((id) => {
          if (map.getLayer(id)) map.removeLayer(id);
        });
        if (map.getSource(sourceId)) map.removeSource(sourceId);
      });

    layers.forEach((layer) => {
      const sourceData = geojsonByLayerId[layer.id];
      const renderLayer = resolveLayerPresentation(layer, sourceData);
      const data = sourceData ? collectionWithResult(sourceData, resultOverlay, layer.id) : undefined;
      if (!data) return;
      const sourceId = `source-${layer.id}`;
      const existingSource = map.getSource(sourceId) as GeoJSONSource | undefined;
      if (existingSource) existingSource.setData(data);
      else map.addSource(sourceId, { type: "geojson", data });

      const newInteractiveIds: string[] = [];
      if (layer.geometry === "polygon") {
        if (!map.getLayer(`fill-${layer.id}`)) {
          map.addLayer({ id: `fill-${layer.id}`, type: "fill", source: sourceId });
          newInteractiveIds.push(`fill-${layer.id}`);
        }
        if (!map.getLayer(`stroke-${layer.id}`)) {
          map.addLayer({ id: `stroke-${layer.id}`, type: "line", source: sourceId });
          newInteractiveIds.push(`stroke-${layer.id}`);
        }
      } else if (layer.geometry === "point") {
        if (!map.getLayer(`point-${layer.id}`)) {
          map.addLayer({ id: `point-${layer.id}`, type: "circle", source: sourceId });
          newInteractiveIds.push(`point-${layer.id}`);
        }
      } else if (!map.getLayer(`line-${layer.id}`)) {
        map.addLayer({ id: `line-${layer.id}`, type: "line", source: sourceId, layout: { "line-cap": "round", "line-join": "round" } });
        newInteractiveIds.push(`line-${layer.id}`);
      }

      const highlightId = selectionLayerId(layer.id);
      if (!map.getLayer(highlightId)) {
        if (layer.geometry === "polygon") {
          map.addLayer({
            id: highlightId,
            type: "line",
            source: sourceId,
            filter: ["==", ["id"], "__urbdata_none__"],
            paint: { "line-color": "#F4C35A", "line-width": 4, "line-opacity": 1 },
          });
        } else if (layer.geometry === "point") {
          map.addLayer({
            id: highlightId,
            type: "circle",
            source: sourceId,
            filter: ["==", ["id"], "__urbdata_none__"],
            paint: {
              "circle-color": "#F4C35A",
              "circle-radius": Math.max(7, layer.strokeWidth * 3),
              "circle-opacity": 0.45,
              "circle-stroke-color": "#172A25",
              "circle-stroke-width": 2,
            },
          });
        } else {
          map.addLayer({
            id: highlightId,
            type: "line",
            source: sourceId,
            filter: ["==", ["id"], "__urbdata_none__"],
            paint: { "line-color": "#F4C35A", "line-width": Math.max(6, layer.strokeWidth + 4), "line-opacity": 1 },
            layout: { "line-cap": "round", "line-join": "round" },
          });
        }
      }

      newInteractiveIds.forEach((id) => {
        map.on("click", id, (event) => {
          selectLayerRef.current(layer.id);
          const feature = event.features?.[0];
          if (feature?.id === undefined || feature.id === null) return;
          const featureId = String(feature.id);
          const sourceFeature = geojsonByLayerIdRef.current[layer.id]?.features.find(
            (item) => String(item.id) === featureId,
          );
          selectFeatureRef.current({
            layerId: layer.id,
            featureId,
            properties: sourceFeature?.properties ?? feature.properties ?? {},
          });
        });
        map.on("mouseenter", id, () => { map.getCanvas().style.cursor = "pointer"; });
        map.on("mouseleave", id, () => { map.getCanvas().style.cursor = ""; });
      });

      const visibility = layer.visible ? "visible" : "none";
      mapLayerIds(layer).forEach((id) => {
        if (map.getLayer(id)) map.setLayoutProperty(id, "visibility", visibility);
      });

      if (map.getLayer(`fill-${layer.id}`)) {
        map.setPaintProperty(
          `fill-${layer.id}`,
          "fill-color",
          resultOverlay?.layerId === layer.id ? resultColor(resultOverlay) : compileFillColor(renderLayer),
        );
        map.setPaintProperty(`fill-${layer.id}`, "fill-opacity", layer.opacity);
      }
      if (map.getLayer(`point-${layer.id}`)) {
        map.setPaintProperty(
          `point-${layer.id}`,
          "circle-color",
          resultOverlay?.layerId === layer.id ? resultColor(resultOverlay) : compileFillColor(renderLayer),
        );
        map.setPaintProperty(`point-${layer.id}`, "circle-radius", Math.max(4, layer.strokeWidth * 2));
        map.setPaintProperty(`point-${layer.id}`, "circle-opacity", layer.opacity);
        map.setPaintProperty(`point-${layer.id}`, "circle-stroke-color", layer.strokeColor);
        map.setPaintProperty(`point-${layer.id}`, "circle-stroke-width", 1);
      }
      const lineId = map.getLayer(`line-${layer.id}`) ? `line-${layer.id}` : `stroke-${layer.id}`;
      if (map.getLayer(lineId)) {
        map.setPaintProperty(
          lineId,
          "line-color",
          resultOverlay?.layerId === layer.id
            ? resultColor(resultOverlay)
            : layer.geometry === "line" ? compileFillColor(renderLayer) : layer.strokeColor,
        );
        map.setPaintProperty(lineId, "line-width", layer.strokeWidth);
        map.setPaintProperty(lineId, "line-opacity", layer.opacity);
        map.setPaintProperty(lineId, "line-dasharray", dashArray(layer.lineStyle) ?? [1, 0]);
      }
    });

    layers.forEach((layer) => {
      mapLayerIds(layer).forEach((id) => {
        if (map.getLayer(id)) map.moveLayer(id);
      });
    });
    interactiveLayerIdsRef.current = layers.flatMap(mapLayerIds);
    layers.forEach((layer) => {
      const id = selectionLayerId(layer.id);
      if (map.getLayer(id)) map.moveLayer(id);
    });

    const loadedCollections = layers
      .map((layer) => geojsonByLayerId[layer.id])
      .filter((data): data is FeatureCollection => Boolean(data));
    const signature = layers
      .map((layer) => `${layer.id}:${geojsonByLayerId[layer.id]?.features.length ?? 0}`)
      .join("|");
    if (signature && signature !== fittedDataSignature.current) {
      const bounds = dataBounds(loadedCollections);
      if (bounds) map.fitBounds(bounds, { padding: 54, duration: 0, maxZoom: 17 });
      fittedDataSignature.current = signature;
    }
    if (!signature) fittedDataSignature.current = "";
  }, [geojsonByLayerId, isMapReady, layers, resultOverlay, styleRevision]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map || !isMapReady) return;
    layers.forEach((layer) => {
      const id = selectionLayerId(layer.id);
      if (!map.getLayer(id)) return;
      const isSelectedLayer = selectedFeature?.layerId === layer.id;
      map.setFilter(
        id,
        ["==", ["id"], isSelectedLayer ? selectedFeature.featureId : "__urbdata_none__"],
      );
      map.setLayoutProperty(id, "visibility", layer.visible && isSelectedLayer ? "visible" : "none");
    });
  }, [isMapReady, layers, selectedFeature]);

  return <div ref={containerRef} className="map-canvas" aria-label="Pré-visualização cartográfica interativa" />;
}
