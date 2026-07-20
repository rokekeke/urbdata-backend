"use client";

import { useQuery } from "@tanstack/react-query";

import { type AppError } from "../../../lib/errors";
import { queryKeys } from "../../../lib/query";
import { getLayerAttributes, type LayerAttributes } from "../api/getLayerAttributes";

export function useLayerAttributes(projectId: string | null, layerId: string | null) {
  return useQuery<LayerAttributes, AppError>({
    queryKey: queryKeys.layers.attributes(projectId ?? "unselected", layerId ?? "unselected"),
    queryFn: ({ signal }) => getLayerAttributes(projectId!, layerId!, signal),
    enabled: Boolean(projectId && layerId),
  });
}
