"use client";

import { useQueries } from "@tanstack/react-query";
import type { FeatureCollection } from "geojson";

import { type AppError } from "../../../lib/errors";
import { queryKeys } from "../../../lib/query";
import { getLayerGeojson } from "../api/getLayerGeojson";

export type LayerGeojsonStatus = "loading" | "ready" | "empty" | "stale" | "error";

export interface LayerGeojsonViewState {
  status: LayerGeojsonStatus;
  error: AppError | null;
  isRefreshing: boolean;
  featureCount: number | null;
}

export function useLayerGeojsonQueries(projectId: string | null, layerIds: string[]) {
  const queries = useQueries({
    queries: layerIds.map((layerId) => ({
      queryKey: queryKeys.layers.geojson(projectId ?? "unselected", layerId),
      queryFn: ({ signal }: { signal: AbortSignal }) =>
        getLayerGeojson(projectId!, layerId, signal),
      enabled: Boolean(projectId),
    })),
  });

  const dataByLayerId: Record<string, FeatureCollection> = {};
  const stateByLayerId: Record<string, LayerGeojsonViewState> = {};
  const errors: AppError[] = [];

  queries.forEach((query, index) => {
    const layerId = layerIds[index];
    if (query.data) dataByLayerId[layerId] = query.data;
    if (query.error) errors.push(query.error as AppError);

    const featureCount = query.data?.features.length ?? null;
    const status: LayerGeojsonStatus = query.isError && query.data
      ? "stale"
      : query.isError
        ? "error"
      : query.data
        ? featureCount === 0 ? "empty" : "ready"
        : "loading";
    stateByLayerId[layerId] = {
      status,
      error: query.error as AppError | null,
      isRefreshing: query.isFetching && Boolean(query.data),
      featureCount,
    };
  });

  async function retryLayer(layerId: string): Promise<void> {
    const index = layerIds.indexOf(layerId);
    if (index < 0) return;
    await queries[index].refetch();
  }

  async function retryFailedLayers(): Promise<void> {
    await Promise.all(
      queries
        .filter((query) => query.isError)
        .map((query) => query.refetch()),
    );
  }

  return {
    dataByLayerId,
    stateByLayerId,
    errors,
    retryLayer,
    retryFailedLayers,
    isFetching: queries.some((query) => query.isFetching),
    loadedCount: Object.keys(dataByLayerId).length,
    readyCount: Object.values(stateByLayerId).filter((state) => state.status === "ready" || state.status === "stale").length,
    emptyCount: Object.values(stateByLayerId).filter((state) => state.status === "empty").length,
  };
}
