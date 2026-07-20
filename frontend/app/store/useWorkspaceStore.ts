"use client";

import type { FeatureCollection } from "geojson";
import { create } from "zustand";

import { DEFAULT_VIEWPORT } from "../features/map-documents/model/mapDocumentComposition";
import type { BasemapId, LayerStyleConfig, MapViewport, WorkspaceSection } from "../lib/types";

export interface SelectedFeature {
  layerId: string;
  featureId: string;
  properties: Record<string, unknown>;
}

interface WorkspaceState {
  activeSection: WorkspaceSection;
  activeProjectId: string | null;
  activeVersionId: string | null;
  layers: LayerStyleConfig[];
  layerDefaults: Record<string, LayerStyleConfig>;
  geojsonByLayerId: Record<string, FeatureCollection>;
  selectedLayerId: string | null;
  selectedFeature: SelectedFeature | null;
  basemap: BasemapId;
  viewport: MapViewport;
  hasUnsavedChanges: boolean;
  lastSavedAt: string | null;
  setSection: (section: WorkspaceSection) => void;
  setActiveProject: (id: string | null) => void;
  setActiveVersion: (id: string | null) => void;
  hydrateLayers: (layers: LayerStyleConfig[]) => void;
  hydrateLayer: (layer: LayerStyleConfig) => void;
  setLayerGeojson: (id: string, data: FeatureCollection) => void;
  selectLayer: (id: string) => void;
  selectFeature: (feature: SelectedFeature) => void;
  clearFeatureSelection: () => void;
  toggleLayer: (id: string) => void;
  updateLayer: (id: string, update: Partial<LayerStyleConfig>) => void;
  moveLayer: (id: string, direction: -1 | 1) => void;
  setBasemap: (id: BasemapId) => void;
  setViewport: (viewport: MapViewport) => void;
  hydrateComposition: (input: {
    layers: LayerStyleConfig[];
    basemap: BasemapId;
    viewport: MapViewport;
  }) => void;
  resetLayer: (id: string) => void;
  markChanged: () => void;
  markSaved: () => void;
}

function indexLayers(layers: LayerStyleConfig[]): Record<string, LayerStyleConfig> {
  return Object.fromEntries(layers.map((layer) => [layer.id, layer]));
}

export const useWorkspaceStore = create<WorkspaceState>((set) => ({
  activeSection: "documentacao",
  activeProjectId: null,
  activeVersionId: null,
  layers: [],
  layerDefaults: {},
  geojsonByLayerId: {},
  selectedLayerId: null,
  selectedFeature: null,
  basemap: "none",
  viewport: DEFAULT_VIEWPORT,
  hasUnsavedChanges: false,
  lastSavedAt: null,
  setSection: (activeSection) => set({ activeSection }),
  setActiveProject: (activeProjectId) =>
    set((state) => {
      if (state.activeProjectId === activeProjectId) return state;
      return {
        activeProjectId,
        activeVersionId: null,
        layers: [],
        layerDefaults: {},
        geojsonByLayerId: {},
        selectedLayerId: null,
        selectedFeature: null,
        basemap: "none",
        viewport: DEFAULT_VIEWPORT,
        hasUnsavedChanges: false,
        lastSavedAt: null,
      };
    }),
  setActiveVersion: (activeVersionId) =>
    set((state) => {
      if (state.activeVersionId === activeVersionId) return state;
      return {
        activeVersionId,
        layers: [],
        layerDefaults: {},
        geojsonByLayerId: {},
        selectedLayerId: null,
        selectedFeature: null,
        basemap: "none",
        viewport: DEFAULT_VIEWPORT,
        hasUnsavedChanges: false,
        lastSavedAt: null,
      };
    }),
  hydrateLayers: (incomingLayers) =>
    set((state) => {
      const existingById = indexLayers(state.layers);
      const layers = incomingLayers.map((incoming) => {
        const existing = existingById[incoming.id];
        if (!existing) return incoming;
        return {
          ...incoming,
          visible: existing.visible,
          opacity: existing.opacity,
          color: existing.color,
          secondaryColor: existing.secondaryColor,
          strokeColor: existing.strokeColor,
          strokeWidth: existing.strokeWidth,
          lineStyle: existing.lineStyle,
          representation: existing.representation,
          mode: existing.mode,
          categories: existing.categories,
          range: existing.range,
          representationOptions: existing.representationOptions,
        };
      });
      const selectedLayerId = layers.some((layer) => layer.id === state.selectedLayerId)
        ? state.selectedLayerId
        : (layers[0]?.id ?? null);
      const selectedFeature = state.selectedFeature
        && layers.some((layer) => layer.id === state.selectedFeature?.layerId)
        ? state.selectedFeature
        : null;
      return {
        layers,
        layerDefaults: indexLayers(layers),
        selectedLayerId,
        selectedFeature,
      };
    }),
  hydrateLayer: (incoming) =>
    set((state) => ({
      layers: state.layers.map((layer) => (layer.id === incoming.id ? incoming : layer)),
      layerDefaults: { ...state.layerDefaults, [incoming.id]: incoming },
    })),
  setLayerGeojson: (id, data) =>
    set((state) => ({ geojsonByLayerId: { ...state.geojsonByLayerId, [id]: data } })),
  selectLayer: (selectedLayerId) =>
    set((state) => ({
      selectedLayerId,
      selectedFeature: state.selectedFeature?.layerId === selectedLayerId
        ? state.selectedFeature
        : null,
    })),
  selectFeature: (selectedFeature) =>
    set({ selectedFeature, selectedLayerId: selectedFeature.layerId }),
  clearFeatureSelection: () => set({ selectedFeature: null }),
  toggleLayer: (id) =>
    set((state) => {
      const target = state.layers.find((layer) => layer.id === id);
      const willHide = target?.visible ?? false;
      return {
        layers: state.layers.map((layer) =>
          layer.id === id ? { ...layer, visible: !layer.visible } : layer,
        ),
        selectedFeature: willHide && state.selectedFeature?.layerId === id
          ? null
          : state.selectedFeature,
        hasUnsavedChanges: true,
      };
    }),
  updateLayer: (id, update) =>
    set((state) => ({
      layers: state.layers.map((layer) => (layer.id === id ? { ...layer, ...update } : layer)),
      hasUnsavedChanges: true,
    })),
  moveLayer: (id, direction) =>
    set((state) => {
      const index = state.layers.findIndex((layer) => layer.id === id);
      const nextIndex = index + direction;
      if (index < 0 || nextIndex < 0 || nextIndex >= state.layers.length) return state;
      const layers = [...state.layers];
      [layers[index], layers[nextIndex]] = [layers[nextIndex], layers[index]];
      return { layers, hasUnsavedChanges: true };
    }),
  setBasemap: (basemap) => set({ basemap, hasUnsavedChanges: true }),
  setViewport: (viewport) =>
    set((state) => {
      const unchanged = (Object.keys(viewport) as Array<keyof MapViewport>).every(
        (key) => Math.abs(state.viewport[key] - viewport[key]) < 0.000001,
      );
      return unchanged ? state : { viewport, hasUnsavedChanges: true };
    }),
  hydrateComposition: ({ layers, basemap, viewport }) =>
    set({
      layers,
      selectedLayerId: layers[0]?.id ?? null,
      selectedFeature: null,
      basemap,
      viewport,
      hasUnsavedChanges: false,
      lastSavedAt: null,
    }),
  resetLayer: (id) =>
    set((state) => {
      const baseline = state.layerDefaults[id];
      if (!baseline) return state;
      return {
        layers: state.layers.map((layer) => (layer.id === id ? { ...baseline } : layer)),
        hasUnsavedChanges: true,
      };
    }),
  markChanged: () => set({ hasUnsavedChanges: true }),
  markSaved: () =>
    set({
      hasUnsavedChanges: false,
      lastSavedAt: new Intl.DateTimeFormat("pt-BR", {
        hour: "2-digit",
        minute: "2-digit",
      }).format(new Date()),
    }),
}));
