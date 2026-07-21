import type { components } from "../../../lib/api/schema";
import { getApiClient } from "../../../lib/api/client";
import { executeApiRequest } from "../../../lib/api/request";
import { normalizeAppError } from "../../../lib/errors";
import type { ProjectLayer } from "./listProjectLayers";

export type LayerType = components["schemas"]["LayerType"];
type UploadLayerBody =
  components["schemas"]["Body_upload_layer_v1_projects__project_id__layers_post"];

export async function uploadLayer(
  projectId: string,
  layerType: LayerType,
  file: File,
): Promise<ProjectLayer> {
  const form = new FormData();
  form.append("layer_type", layerType);
  form.append("file", file);
  try {
    return await executeApiRequest<ProjectLayer, unknown>(() =>
      getApiClient().POST("/v1/projects/{project_id}/layers", {
        params: { path: { project_id: projectId } },
        body: form as unknown as UploadLayerBody,
      }),
    );
  } catch (error) {
    throw normalizeAppError(error);
  }
}
