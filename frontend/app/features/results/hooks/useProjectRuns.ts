"use client";

import { useQuery } from "@tanstack/react-query";

import { type AppError } from "../../../lib/errors";
import { queryKeys } from "../../../lib/query";
import { listProjectRuns, type AnalysisRun } from "../api/listProjectRuns";

export function useProjectRuns(projectId: string | null) {
  return useQuery<AnalysisRun[], AppError>({
    queryKey: queryKeys.projects.runs(projectId ?? "unselected"),
    queryFn: ({ signal }) => listProjectRuns(projectId!, signal),
    enabled: Boolean(projectId),
    refetchInterval: (query) => {
      const runs = query.state.data;
      return runs?.some((run) => run.status === "pending" || run.status === "running")
        ? 5_000
        : false;
    },
  });
}
