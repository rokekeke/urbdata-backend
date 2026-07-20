"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";

import { type AppError } from "../../../lib/errors";
import { queryKeys } from "../../../lib/query";
import { analyzeProject, type AnalyzeResponse } from "../api/analyzeProject";

export function useAnalyzeProject(projectId: string | null) {
  const queryClient = useQueryClient();
  return useMutation<AnalyzeResponse, AppError, string[]>({
    mutationFn: (themes) => analyzeProject(projectId!, themes),
    onSuccess: async (response) => {
      if (!projectId) return;
      queryClient.setQueryData(queryKeys.projects.results(projectId), response.results);
      await queryClient.invalidateQueries({ queryKey: queryKeys.projects.runs(projectId) });
    },
  });
}
