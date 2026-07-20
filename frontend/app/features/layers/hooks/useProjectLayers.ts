"use client";

import { useQuery } from "@tanstack/react-query";

import { type AppError } from "../../../lib/errors";
import { queryKeys } from "../../../lib/query";
import { listProjectLayers, type ProjectLayer } from "../api/listProjectLayers";

export function useProjectLayers(projectId: string | null, versionId: string | null) {
  const query = useQuery<ProjectLayer[], AppError>({
    queryKey: queryKeys.projects.layers(projectId ?? "unselected", versionId ?? "unselected"),
    queryFn: ({ signal }) => listProjectLayers(projectId!, versionId!, signal),
    enabled: Boolean(projectId && versionId),
  });

  return {
    ...query,
    isEmpty: query.isSuccess && query.data.length === 0,
  };
}
