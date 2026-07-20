"use client";

import { useQuery } from "@tanstack/react-query";

import { type AppError } from "../../../lib/errors";
import { queryKeys } from "../../../lib/query";
import { listProjectResults, type IndicatorResult } from "../api/listProjectResults";

export function useProjectResults(projectId: string | null) {
  return useQuery<IndicatorResult[], AppError>({
    queryKey: queryKeys.projects.results(projectId ?? "unselected"),
    queryFn: ({ signal }) => listProjectResults(projectId!, signal),
    enabled: Boolean(projectId),
  });
}
