import type { components } from "../../../lib/api/schema";
import { getApiClient } from "../../../lib/api/client";
import { executeApiRequest } from "../../../lib/api/request";
import { createRequestSignal } from "../../../lib/api/requestSignal";
import { normalizeAppError } from "../../../lib/errors";

export type MapDocument = components["schemas"]["MapDocumentOut"];
export type MapDocumentWithWarnings = components["schemas"]["MapDocumentWithWarningsOut"];
type WritableLayerStyle = Omit<components["schemas"]["LayerStyle"], "labels"> & { labels?: never };
type WritableInteraction = Omit<components["schemas"]["Interaction"], "filters"> & { filters?: never };
type WritableDocumentLayer = Omit<components["schemas"]["DocumentLayer"], "style" | "interaction"> & {
  style: WritableLayerStyle;
  interaction?: WritableInteraction;
};
export type WritableMapDocumentConfig = Omit<components["schemas"]["MapDocumentConfig"], "layers"> & {
  layers?: WritableDocumentLayer[];
};
export interface MapDocumentCreate {
  name: string;
  config: WritableMapDocumentConfig;
}
export interface MapDocumentUpdate extends MapDocumentCreate {
  expected_revision: number;
}

export async function listMapDocuments(
  projectId: string,
  versionId: string,
  signal?: AbortSignal,
): Promise<MapDocument[]> {
  try {
    return await executeApiRequest<MapDocument[], unknown>(() =>
      getApiClient().GET("/v1/projects/{project_id}/versions/{version_id}/documents", {
        params: { path: { project_id: projectId, version_id: versionId } },
        signal: createRequestSignal(signal),
      }),
    );
  } catch (error) {
    throw normalizeAppError(error);
  }
}

export async function getMapDocument(
  projectId: string,
  documentId: string,
  signal?: AbortSignal,
): Promise<MapDocumentWithWarnings> {
  try {
    return await executeApiRequest<MapDocumentWithWarnings, unknown>(() =>
      getApiClient().GET("/v1/projects/{project_id}/documents/{document_id}", {
        params: { path: { project_id: projectId, document_id: documentId } },
        signal: createRequestSignal(signal),
      }),
    );
  } catch (error) {
    throw normalizeAppError(error);
  }
}

export async function createMapDocument(
  projectId: string,
  versionId: string,
  payload: MapDocumentCreate,
): Promise<MapDocument> {
  try {
    return await executeApiRequest<MapDocument, unknown>(() =>
      getApiClient().POST("/v1/projects/{project_id}/versions/{version_id}/documents", {
        params: { path: { project_id: projectId, version_id: versionId } },
        body: payload,
      }),
    );
  } catch (error) {
    throw normalizeAppError(error);
  }
}

export async function updateMapDocument(
  projectId: string,
  documentId: string,
  payload: MapDocumentUpdate,
): Promise<MapDocument> {
  try {
    return await executeApiRequest<MapDocument, unknown>(() =>
      getApiClient().PUT("/v1/projects/{project_id}/documents/{document_id}", {
        params: { path: { project_id: projectId, document_id: documentId } },
        body: payload,
      }),
    );
  } catch (error) {
    throw normalizeAppError(error);
  }
}

export async function deleteMapDocument(projectId: string, documentId: string): Promise<void> {
  try {
    await executeApiRequest<void, unknown>(() =>
      getApiClient().DELETE("/v1/projects/{project_id}/documents/{document_id}", {
        params: { path: { project_id: projectId, document_id: documentId } },
      }),
    );
  } catch (error) {
    throw normalizeAppError(error);
  }
}
