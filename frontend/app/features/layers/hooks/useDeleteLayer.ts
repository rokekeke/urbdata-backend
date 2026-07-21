"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";

import { type AppError } from "../../../lib/errors";
import { queryKeys } from "../../../lib/query";
import { deleteLayer } from "../api/deleteLayer";

export function useDeleteLayer(projectId: string | null, versionId: string | null) {
  const queryClient = useQueryClient();
  return useMutation<void, AppError, string>({
    mutationFn: (layerId) => deleteLayer(projectId!, layerId),
    onSuccess: async () => {
      if (!projectId || !versionId) return;
      await queryClient.invalidateQueries({
        queryKey: queryKeys.projects.layers(projectId, versionId),
      });
    },
  });
}
