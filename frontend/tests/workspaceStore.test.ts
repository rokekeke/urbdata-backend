import { beforeEach, describe, expect, it } from "vitest";

import type { LayerStyleConfig } from "../app/lib/types";
import { useWorkspaceStore } from "../app/store/useWorkspaceStore";

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
  representation: "single",
  mode: "single",
  representationOptions: [
    { value: "single", label: "Estilo único", type: "text", source: "source" },
  ],
};

beforeEach(() => {
  useWorkspaceStore.setState({
    activeProjectId: null,
    activeVersionId: null,
    layers: [],
    layerDefaults: {},
    geojsonByLayerId: {},
    selectedLayerId: null,
    selectedFeature: null,
    basemap: "none",
    viewport: { longitude: -48.501, latitude: -27.611, zoom: 12, bearing: 0, pitch: 0 },
    hasUnsavedChanges: false,
    lastSavedAt: null,
  });
});

describe("seleção territorial do workspace", () => {
  it("seleciona a camada junto com o elemento territorial", () => {
    useWorkspaceStore.getState().hydrateLayers([layer]);
    useWorkspaceStore.getState().selectFeature({
      layerId: layer.id,
      featureId: "feature-1",
      properties: { quadra: "Q01" },
    });

    expect(useWorkspaceStore.getState().selectedLayerId).toBe(layer.id);
    expect(useWorkspaceStore.getState().selectedFeature).toMatchObject({
      featureId: "feature-1",
      properties: { quadra: "Q01" },
    });
  });

  it("limpa a seleção quando a camada é ocultada", () => {
    useWorkspaceStore.getState().hydrateLayers([layer]);
    useWorkspaceStore.getState().selectFeature({ layerId: layer.id, featureId: "feature-1", properties: {} });
    useWorkspaceStore.getState().toggleLayer(layer.id);

    expect(useWorkspaceStore.getState().selectedFeature).toBeNull();
    expect(useWorkspaceStore.getState().layers[0].visible).toBe(false);
  });

  it("limpa a seleção ao trocar de projeto", () => {
    useWorkspaceStore.getState().hydrateLayers([layer]);
    useWorkspaceStore.getState().selectFeature({ layerId: layer.id, featureId: "feature-1", properties: {} });
    useWorkspaceStore.getState().setActiveProject("project-2");

    expect(useWorkspaceStore.getState().selectedFeature).toBeNull();
    expect(useWorkspaceStore.getState().layers).toEqual([]);
  });

  it("hidrata uma composição salva sem marcar alterações locais", () => {
    useWorkspaceStore.getState().hydrateLayers([layer]);
    useWorkspaceStore.getState().hydrateComposition({
      layers: [{ ...layer, visible: false }],
      basemap: "voyager",
      viewport: { longitude: -49, latitude: -28, zoom: 14, bearing: 8, pitch: 20 },
    });

    expect(useWorkspaceStore.getState()).toMatchObject({
      basemap: "voyager",
      viewport: { longitude: -49, latitude: -28, zoom: 14, bearing: 8, pitch: 20 },
      hasUnsavedChanges: false,
    });
    expect(useWorkspaceStore.getState().layers[0].visible).toBe(false);
  });

  it("marca o enquadramento como alterado apenas quando a câmera muda", () => {
    const viewport = useWorkspaceStore.getState().viewport;
    useWorkspaceStore.getState().setViewport(viewport);
    expect(useWorkspaceStore.getState().hasUnsavedChanges).toBe(false);

    useWorkspaceStore.getState().setViewport({ ...viewport, zoom: viewport.zoom + 1 });
    expect(useWorkspaceStore.getState().hasUnsavedChanges).toBe(true);
  });
});
