import type { components } from "../../../lib/api/schema";
import { getApiClient } from "../../../lib/api/client";
import { executeApiRequest } from "../../../lib/api/request";
import { createRequestSignal } from "../../../lib/api/requestSignal";
import { normalizeAppError } from "../../../lib/errors";

export type ProjectVersion = components["schemas"]["ProjectVersionOut"];

export async function listProjectVersions(
  projectId: string,
  signal?: AbortSignal,
): Promise<ProjectVersion[]> {
  try {
    return await executeApiRequest<ProjectVersion[], unknown>(() =>
      getApiClient().GET("/v1/projects/{project_id}/versions", {
        params: { path: { project_id: projectId } },
        signal: createRequestSignal(signal),
      }),
    );
  } catch (error) {
    throw normalizeAppError(error);
  }
}
