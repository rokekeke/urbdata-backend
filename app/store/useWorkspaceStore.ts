"use client";

import { create } from "zustand";
import { initialLayers } from "../lib/mockData";
import type { BasemapId, LayerStyleConfig, WorkspaceSection } from "../lib/types";

interface WorkspaceState {
  activeSection: WorkspaceSection;
  layers: LayerStyleConfig[];
  selectedLayerId: string;
  basemap: BasemapId;
  hasUnsavedChanges: boolean;
  lastSavedAt: string | null;
  setSection: (section: WorkspaceSection) => void;
  selectLayer: (id: string) => void;
  toggleLayer: (id: string) => void;
  updateLayer: (id: string, update: Partial<LayerStyleConfig>) => void;
  moveLayer: (id: string, direction: -1 | 1) => void;
  setBasemap: (id: BasemapId) => void;
  resetLayer: (id: string) => void;
  markSaved: () => void;
}

export const useWorkspaceStore = create<WorkspaceState>((set) => ({
  activeSection: "documentacao",
  layers: initialLayers,
  selectedLayerId: initialLayers[0].id,
  basemap: "none",
  hasUnsavedChanges: false,
  lastSavedAt: null,
  setSection: (activeSection) => set({ activeSection }),
  selectLayer: (selectedLayerId) => set({ selectedLayerId }),
  toggleLayer: (id) =>
    set((state) => ({
      layers: state.layers.map((layer) =>
        layer.id === id ? { ...layer, visible: !layer.visible } : layer,
      ),
      hasUnsavedChanges: true,
    })),
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
  resetLayer: (id) =>
    set((state) => ({
      layers: state.layers.map((layer) =>
        layer.id === id ? { ...initialLayers.find((item) => item.id === id)! } : layer,
      ),
      hasUnsavedChanges: true,
    })),
  markSaved: () =>
    set({
      hasUnsavedChanges: false,
      lastSavedAt: new Intl.DateTimeFormat("pt-BR", {
        hour: "2-digit",
        minute: "2-digit",
      }).format(new Date()),
    }),
}));

