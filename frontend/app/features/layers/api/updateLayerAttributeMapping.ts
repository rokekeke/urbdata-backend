import type { components } from "../../../lib/api/schema";
import { getApiClient } from "../../../lib/api/client";
import { executeApiRequest } from "../../../lib/api/request";
import { normalizeAppError } from "../../../lib/errors";

export type LayerAttributeMappingResult = components["schemas"]["LayerAttributeMappingOut"];

export async function updateLayerAttributeMapping(
  projectId: string,
  layerId: string,
  mappings: Record<string, string | null>,
): Promise<LayerAttributeMappingResult> {
  try {
    return await executeApiRequest<LayerAttributeMappingResult, unknown>(() =>
      getApiClient().PATCH("/v1/projects/{project_id}/layers/{layer_id}/attributes", {
        params: { path: { project_id: projectId, layer_id: layerId } },
        body: { mappings },
      }),
    );
  } catch (error) {
    throw normalizeAppError(error);
  }
}
