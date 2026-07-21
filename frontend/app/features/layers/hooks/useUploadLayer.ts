"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";

import { type AppError } from "../../../lib/errors";
import { queryKeys } from "../../../lib/query";
import {
  uploadLayer,
  type ImportProfile,
  type LayerType,
} from "../api/uploadLayer";
import type { ProjectLayer } from "../api/listProjectLayers";

interface UploadLayerInput {
  layerType: LayerType;
  file: File;
  importProfile?: ImportProfile;
  attributesFile?: File;
  attributesJoinKey?: string;
  geometryJoinKey?: string;
}

export function useUploadLayer(projectId: string | null, versionId: string | null) {
  const queryClient = useQueryClient();
  return useMutation<ProjectLayer, AppError, UploadLayerInput>({
    mutationFn: ({
      layerType,
      file,
      importProfile,
      attributesFile,
      attributesJoinKey,
      geometryJoinKey,
    }) =>
      uploadLayer(projectId!, layerType, file, {
        importProfile,
        attributesFile,
        attributesJoinKey,
        geometryJoinKey,
      }),
    onSuccess: async () => {
      if (!projectId || !versionId) return;
      await queryClient.invalidateQueries({
        queryKey: queryKeys.projects.layers(projectId, versionId),
      });
    },
  });
}
