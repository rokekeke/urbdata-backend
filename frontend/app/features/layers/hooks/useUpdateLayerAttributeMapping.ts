"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";

import { type AppError } from "../../../lib/errors";
import { queryKeys } from "../../../lib/query";
import {
  updateLayerAttributeMapping,
  type LayerAttributeMappingResult,
} from "../api/updateLayerAttributeMapping";

interface UpdateLayerAttributeMappingInput {
  layerId: string;
  mappings: Record<string, string | null>;
}

export function useUpdateLayerAttributeMapping(projectId: string | null) {
  const queryClient = useQueryClient();
  return useMutation<LayerAttributeMappingResult, AppError, UpdateLayerAttributeMappingInput>({
    mutationFn: ({ layerId, mappings }) =>
      updateLayerAttributeMapping(projectId!, layerId, mappings),
    onSuccess: async (_result, { layerId }) => {
      if (!projectId) return;
      await queryClient.invalidateQueries({
        queryKey: queryKeys.layers.attributes(projectId, layerId),
      });
    },
  });
}
