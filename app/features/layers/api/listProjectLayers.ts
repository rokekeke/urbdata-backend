import type { components } from "../../../lib/api/schema";
import { getApiClient } from "../../../lib/api/client";
import { executeApiRequest } from "../../../lib/api/request";
import { createRequestSignal } from "../../../lib/api/requestSignal";
import { AppError, normalizeAppError } from "../../../lib/errors";

export type ProjectLayer = components["schemas"]["LayerOut"];

export async function listProjectLayers(
  projectId: string,
  expectedVersionId: string,
  signal?: AbortSignal,
): Promise<ProjectLayer[]> {
  try {
    const layers = await executeApiRequest<ProjectLayer[], unknown>(() =>
      getApiClient().GET("/v1/projects/{project_id}/layers", {
        params: { path: { project_id: projectId } },
        signal: createRequestSignal(signal),
      }),
    );
    const mismatchedLayer = layers.find(
      (layer) => layer.project_version_id !== expectedVersionId,
    );
    if (mismatchedLayer) {
      throw new AppError({
        kind: "invalid_response",
        code: "layer_version_mismatch",
        message: "As camadas recebidas não pertencem à versão ativa do projeto.",
        context: {
          expected_version_id: expectedVersionId,
          received_version_id: mismatchedLayer.project_version_id,
          layer_id: mismatchedLayer.id,
        },
        canRetry: true,
        presentation: "global",
      });
    }
    return layers;
  } catch (error) {
    throw normalizeAppError(error);
  }
}
