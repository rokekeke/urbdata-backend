"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { type AppError } from "../../../lib/errors";
import { queryKeys } from "../../../lib/query";
import {
  createMapDocument,
  deleteMapDocument,
  getMapDocument,
  listMapDocuments,
  updateMapDocument,
  type MapDocument,
  type MapDocumentCreate,
  type MapDocumentUpdate,
  type MapDocumentWithWarnings,
} from "../api/mapDocuments";

export function useMapDocuments(projectId: string | null, versionId: string | null) {
  return useQuery<MapDocument[], AppError>({
    queryKey: queryKeys.projects.documents(projectId ?? "unselected", versionId ?? "unselected"),
    queryFn: ({ signal }) => listMapDocuments(projectId!, versionId!, signal),
    enabled: Boolean(projectId && versionId),
  });
}

export function useOpenMapDocument(projectId: string | null) {
  return useMutation<MapDocumentWithWarnings, AppError, string>({
    mutationFn: (documentId) => getMapDocument(projectId!, documentId),
  });
}

export function useCreateMapDocument(projectId: string | null, versionId: string | null) {
  const queryClient = useQueryClient();
  return useMutation<MapDocument, AppError, MapDocumentCreate>({
    mutationFn: (payload) => createMapDocument(projectId!, versionId!, payload),
    onSuccess: (document) => {
      if (!projectId || !versionId) return;
      queryClient.setQueryData<MapDocument[]>(
        queryKeys.projects.documents(projectId, versionId),
        (current = []) => [document, ...current.filter((item) => item.id !== document.id)],
      );
    },
  });
}

export function useUpdateMapDocument(projectId: string | null, versionId: string | null) {
  const queryClient = useQueryClient();
  return useMutation<
    MapDocument,
    AppError,
    { documentId: string; payload: MapDocumentUpdate }
  >({
    mutationFn: ({ documentId, payload }) => updateMapDocument(projectId!, documentId, payload),
    onSuccess: (document) => {
      if (!projectId || !versionId) return;
      queryClient.setQueryData<MapDocument[]>(
        queryKeys.projects.documents(projectId, versionId),
        (current = []) => current.map((item) => (item.id === document.id ? document : item)),
      );
    },
  });
}

export function useDeleteMapDocument(projectId: string | null, versionId: string | null) {
  const queryClient = useQueryClient();
  return useMutation<void, AppError, string>({
    mutationFn: (documentId) => deleteMapDocument(projectId!, documentId),
    onSuccess: (_, documentId) => {
      if (!projectId || !versionId) return;
      queryClient.setQueryData<MapDocument[]>(
        queryKeys.projects.documents(projectId, versionId),
        (current = []) => current.filter((item) => item.id !== documentId),
      );
    },
  });
}
