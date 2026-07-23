import type { components } from "../../../lib/api/schema";
import { getApiClient } from "../../../lib/api/client";
import { executeApiRequest } from "../../../lib/api/request";
import { normalizeAppError } from "../../../lib/errors";
import type { ProjectLayer } from "./listProjectLayers";

export type LayerType = components["schemas"]["LayerType"];
export type ImportProfile = components["schemas"]["ImportProfile"];
type UploadLayerBody =
  components["schemas"]["Body_upload_layer_v1_projects__project_id__layers_post"];

export interface UploadLayerAttributesInput {
  importProfile?: ImportProfile;
  attributesFile?: File;
  attributesJoinKey?: string;
  geometryJoinKey?: string;
}

export async function uploadLayer(
  projectId: string,
  layerType: LayerType,
  file: File,
  attributesInput?: UploadLayerAttributesInput,
): Promise<ProjectLayer> {
  const form = new FormData();
  form.append("layer_type", layerType);
  form.append("file", file);
  if (attributesInput?.importProfile) {
    form.append("import_profile", attributesInput.importProfile);
  }
  if (attributesInput?.attributesFile) {
    form.append("attributes_file", attributesInput.attributesFile);
  }
  if (attributesInput?.attributesJoinKey) {
    form.append("attributes_join_key", attributesInput.attributesJoinKey);
  }
  if (attributesInput?.geometryJoinKey) {
    form.append("geometry_join_key", attributesInput.geometryJoinKey);
  }
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
