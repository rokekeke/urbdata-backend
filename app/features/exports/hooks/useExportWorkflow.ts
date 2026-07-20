"use client";

import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import maplibrePackage from "maplibre-gl/package.json";
import frontendPackage from "../../../../package.json";

import { AppError } from "../../../lib/errors";
import {
  createExport,
  deliverExportFile,
  getExport,
  type ExportCreate,
  type ExportRecord,
} from "../api/exports";

export type ExportStage = "idle" | "snapshot" | "rendering" | "uploading" | "verifying" | "completed" | "failed";

interface ExportWorkflowInput {
  documentId: string;
  expectedRevision: number;
  legend: boolean;
  image: ExportCreate["image"];
  analysisRunId: string | null;
  render: () => Promise<Blob>;
}

export interface ExportWorkflowResult {
  record: ExportRecord;
  png: Blob;
}

interface RetryPayload {
  exportId: string;
  png: Blob;
}

function snapshotRevision(record: ExportRecord): number | null {
  const revision = record.config.document_revision;
  return typeof revision === "number" ? revision : null;
}

export function useExportWorkflow(projectId: string | null) {
  const [stage, setStage] = useState<ExportStage>("idle");
  const [retryPayload, setRetryPayload] = useState<RetryPayload | null>(null);

  const workflow = useMutation<ExportWorkflowResult, AppError, ExportWorkflowInput>({
    mutationFn: async (input) => {
      setStage("snapshot");
      setRetryPayload(null);
      const pending = await createExport(projectId!, input.documentId, {
        legend: input.legend,
        image: input.image,
        renderer: {
          maplibre_version: maplibrePackage.version,
          frontend_version: frontendPackage.version,
        },
        analysis_run_id: input.analysisRunId,
      });
      const frozenRevision = snapshotRevision(pending);
      if (frozenRevision !== input.expectedRevision) {
        throw new AppError({
          kind: "conflict",
          code: "export_document_revision_mismatch",
          message: "A composição mudou no servidor antes da exportação. Reabra a revisão atual e tente novamente.",
          context: { expected_revision: input.expectedRevision, current_revision: frozenRevision },
        });
      }

      setStage("rendering");
      const png = await input.render();
      setRetryPayload({ exportId: pending.id, png });
      setStage("uploading");
      await deliverExportFile(projectId!, pending.id, png);
      setStage("verifying");
      const record = await getExport(projectId!, pending.id);
      if (record.status !== "completed") {
        throw new AppError({
          kind: "server",
          code: "export_not_completed",
          message: "O arquivo foi enviado, mas a exportação ainda não foi concluída pelo servidor.",
          context: { export_id: record.id, status: record.status },
          canRetry: true,
        });
      }
      setRetryPayload(null);
      return { record, png };
    },
    onSuccess: () => setStage("completed"),
    onError: () => setStage("failed"),
  });

  const retry = useMutation<ExportWorkflowResult, AppError, void>({
    mutationFn: async () => {
      if (!retryPayload) {
        throw new AppError({
          kind: "bad_request",
          code: "export_retry_unavailable",
          message: "Não existe um arquivo renderizado disponível para reenvio.",
        });
      }
      setStage("uploading");
      await deliverExportFile(projectId!, retryPayload.exportId, retryPayload.png);
      setStage("verifying");
      const record = await getExport(projectId!, retryPayload.exportId);
      if (record.status !== "completed") {
        throw new AppError({
          kind: "server",
          code: "export_not_completed",
          message: "O reenvio terminou, mas o servidor não confirmou a conclusão.",
          canRetry: true,
        });
      }
      return { record, png: retryPayload.png };
    },
    onSuccess: () => {
      workflow.reset();
      setRetryPayload(null);
      setStage("completed");
    },
    onError: () => setStage("failed"),
  });

  function reset() {
    workflow.reset();
    retry.reset();
    setRetryPayload(null);
    setStage("idle");
  }

  return {
    stage,
    start: workflow.mutateAsync,
    retry: retry.mutateAsync,
    canRetryUpload: Boolean(retryPayload),
    isPending: workflow.isPending || retry.isPending,
    data: retry.data ?? workflow.data,
    error: retry.error ?? workflow.error,
    reset,
  };
}
