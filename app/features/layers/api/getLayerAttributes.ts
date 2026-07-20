import type { components } from "../../../lib/api/schema";
import { getApiClient } from "../../../lib/api/client";
import { executeApiRequest } from "../../../lib/api/request";
import { createRequestSignal } from "../../../lib/api/requestSignal";
import { normalizeAppError } from "../../../lib/errors";

export type LayerAttributes = components["schemas"]["LayerAttributesOut"];

export async function getLayerAttributes(
  projectId: string,
  layerId: string,
  signal?: AbortSignal,
): Promise<LayerAttributes> {
  try {
    return await executeApiRequest<LayerAttributes, unknown>(() =>
      getApiClient().GET("/v1/projects/{project_id}/layers/{layer_id}/attributes", {
        params: { path: { project_id: projectId, layer_id: layerId } },
        signal: createRequestSignal(signal),
      }),
    );
  } catch (error) {
    throw normalizeAppError(error);
  }
}
