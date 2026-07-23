"use client";

import { useQuery } from "@tanstack/react-query";

import { type AppError } from "../../../lib/errors";
import { queryKeys } from "../../../lib/query";
import { listRunResults } from "../api/listRunResults";
import type { IndicatorResult } from "../api/listProjectResults";

export function useRunResults(projectId: string | null, runId: string | null) {
  return useQuery<IndicatorResult[], AppError>({
    queryKey: queryKeys.projects.runResults(projectId ?? "unselected", runId ?? "unselected"),
    queryFn: ({ signal }) => listRunResults(projectId!, runId!, signal),
    enabled: Boolean(projectId) && Boolean(runId),
  });
}
