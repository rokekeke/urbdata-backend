"use client";

import { useQuery } from "@tanstack/react-query";

import { type AppError } from "../../../lib/errors";
import { queryKeys } from "../../../lib/query";
import {
  listProjectVersions,
  type ProjectVersion,
} from "../api/listProjectVersions";

export function useProjectVersions(projectId: string | null) {
  const query = useQuery<ProjectVersion[], AppError>({
    queryKey: queryKeys.projects.versions(projectId ?? "unselected"),
    queryFn: ({ signal }) => listProjectVersions(projectId!, signal),
    enabled: Boolean(projectId),
  });
  const currentVersion = query.data?.find((version) => version.is_current) ?? null;

  return {
    ...query,
    currentVersion,
    isEmpty: query.isSuccess && query.data.length === 0,
  };
}
