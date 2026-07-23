import type { components } from "../../../lib/api/schema";
import { getApiClient } from "../../../lib/api/client";
import { executeApiRequest } from "../../../lib/api/request";
import { createRequestSignal } from "../../../lib/api/requestSignal";
import { normalizeAppError } from "../../../lib/errors";

export type ExportCreate = components["schemas"]["ExportCreateIn"];
export type ExportRecord = components["schemas"]["ExportOut"];
type ExportFileBody = components["schemas"]["Body_deliver_export_file_v1_projects__project_id__exports__export_id__file_post"];

export async function createExport(
  projectId: string,
  documentId: string,
  payload: ExportCreate,
): Promise<ExportRecord> {
  try {
    return await executeApiRequest<ExportRecord, unknown>(() =>
      getApiClient().POST("/v1/projects/{project_id}/documents/{document_id}/exports", {
        params: { path: { project_id: projectId, document_id: documentId } },
        body: payload,
      }),
    );
  } catch (error) {
    throw normalizeAppError(error);
  }
}

export async function deliverExportFile(
  projectId: string,
  exportId: string,
  png: Blob,
): Promise<ExportRecord> {
  const form = new FormData();
  form.append("file", png, `${exportId}.png`);
  try {
    return await executeApiRequest<ExportRecord, unknown>(() =>
      getApiClient().POST("/v1/projects/{project_id}/exports/{export_id}/file", {
        params: { path: { project_id: projectId, export_id: exportId } },
        body: form as unknown as ExportFileBody,
      }),
    );
  } catch (error) {
    throw normalizeAppError(error);
  }
}

export async function getExport(
  projectId: string,
  exportId: string,
  signal?: AbortSignal,
): Promise<ExportRecord> {
  try {
    return await executeApiRequest<ExportRecord, unknown>(() =>
      getApiClient().GET("/v1/projects/{project_id}/exports/{export_id}", {
        params: { path: { project_id: projectId, export_id: exportId } },
        signal: createRequestSignal(signal),
      }),
    );
  } catch (error) {
    throw normalizeAppError(error);
  }
}
