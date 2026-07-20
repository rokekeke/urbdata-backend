import { getApiClient } from "../../../lib/api/client";
import { executeApiRequest } from "../../../lib/api/request";
import { normalizeAppError } from "../../../lib/errors";

export async function deleteLayer(projectId: string, layerId: string): Promise<void> {
  try {
    await executeApiRequest<void, unknown>(() =>
      getApiClient().DELETE("/v1/projects/{project_id}/layers/{layer_id}", {
        params: { path: { project_id: projectId, layer_id: layerId } },
      }),
    );
  } catch (error) {
    throw normalizeAppError(error);
  }
}
