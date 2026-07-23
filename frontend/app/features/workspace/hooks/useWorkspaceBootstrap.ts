"use client";

import { useEffect, useMemo } from "react";

import { useCatalogIndicators } from "../../catalog/hooks/useCatalogIndicators";
import { useBasemaps } from "../../catalog/hooks/useBasemaps";
import { useLayerAttributes } from "../../layers/hooks/useLayerAttributes";
import { useLayerGeojsonQueries } from "../../layers/hooks/useLayerGeojsonQueries";
import { useProjectLayers } from "../../layers/hooks/useProjectLayers";
import { applyLayerAttributes, createLayerStyle } from "../../layers/model/layerStyle";
import { useProjects, useProjectVersions } from "../../projects";
import { useProjectResults } from "../../results/hooks/useProjectResults";
import { useProjectRuns } from "../../results/hooks/useProjectRuns";
import { useWorkspaceStore } from "../../../store/useWorkspaceStore";

export function useWorkspaceBootstrap() {
  const activeProjectId = useWorkspaceStore((state) => state.activeProjectId);
  const activeVersionId = useWorkspaceStore((state) => state.activeVersionId);
  const selectedLayerId = useWorkspaceStore((state) => state.selectedLayerId);
  const setActiveProject = useWorkspaceStore((state) => state.setActiveProject);
  const setActiveVersion = useWorkspaceStore((state) => state.setActiveVersion);
  const hydrateLayers = useWorkspaceStore((state) => state.hydrateLayers);
  const hydrateLayer = useWorkspaceStore((state) => state.hydrateLayer);
  const setLayerGeojson = useWorkspaceStore((state) => state.setLayerGeojson);

  const projects = useProjects();
  const versions = useProjectVersions(activeProjectId);
  const layers = useProjectLayers(activeProjectId, activeVersionId);
  const layerIds = useMemo(() => layers.data?.map((layer) => layer.id) ?? [], [layers.data]);
  const geojson = useLayerGeojsonQueries(activeProjectId, layerIds);
  const attributes = useLayerAttributes(activeProjectId, selectedLayerId);
  const catalog = useCatalogIndicators();
  const basemaps = useBasemaps();
  const results = useProjectResults(activeProjectId);
  const runs = useProjectRuns(activeProjectId);

  useEffect(() => {
    if (!projects.isSuccess) return;
    const available = projects.data;
    if (activeProjectId && available.some((project) => project.id === activeProjectId)) return;

    const requestedProjectId = new URLSearchParams(window.location.search).get("project");
    const requestedExists = available.some((project) => project.id === requestedProjectId);
    setActiveProject(requestedExists ? requestedProjectId : (available[0]?.id ?? null));
  }, [activeProjectId, projects.data, projects.isSuccess, setActiveProject]);

  useEffect(() => {
    if (!activeProjectId) return;
    const url = new URL(window.location.href);
    if (url.searchParams.get("project") === activeProjectId) return;
    url.searchParams.set("project", activeProjectId);
    window.history.replaceState({}, "", url);
  }, [activeProjectId]);

  useEffect(() => {
    if (!versions.isSuccess) return;
    setActiveVersion(versions.currentVersion?.id ?? null);
  }, [setActiveVersion, versions.currentVersion?.id, versions.isSuccess]);

  useEffect(() => {
    if (!layers.data) return;
    hydrateLayers(layers.data.map(createLayerStyle));
  }, [hydrateLayers, layers.data]);

  useEffect(() => {
    if (!attributes.data || !selectedLayerId) return;
    const currentLayer = useWorkspaceStore
      .getState()
      .layers.find((layer) => layer.id === selectedLayerId);
    if (!currentLayer) return;
    hydrateLayer(applyLayerAttributes(currentLayer, attributes.data));
  }, [attributes.data, hydrateLayer, selectedLayerId]);

  useEffect(() => {
    const currentGeojson = useWorkspaceStore.getState().geojsonByLayerId;
    Object.entries(geojson.dataByLayerId).forEach(([layerId, data]) => {
      if (currentGeojson[layerId] !== data) setLayerGeojson(layerId, data);
    });
  }, [geojson.dataByLayerId, setLayerGeojson]);

  const activeProject = projects.data?.find((project) => project.id === activeProjectId) ?? null;
  const activeVersion = versions.currentVersion;
  const versionContractMissing = versions.isSuccess && versions.data.length > 0 && !activeVersion;

  return {
    projects,
    versions,
    layers,
    geojson,
    attributes,
    catalog,
    basemaps,
    results,
    runs,
    activeProject,
    activeVersion,
    activeProjectId,
    activeVersionId,
    selectProject: setActiveProject,
    versionContractMissing,
    isBootstrapping:
      projects.isLoading ||
      Boolean(activeProjectId && versions.isLoading) ||
      Boolean(activeVersionId && layers.isLoading),
  };
}
