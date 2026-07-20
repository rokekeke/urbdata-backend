import type { components } from "../../../lib/api/schema";
import { getApiClient } from "../../../lib/api/client";
import { executeApiRequest } from "../../../lib/api/request";
import { createRequestSignal } from "../../../lib/api/requestSignal";
import { normalizeAppError } from "../../../lib/errors";

export type IndicatorResult = components["schemas"]["IndicatorResultOut"];

export async function listProjectResults(
  projectId: string,
  signal?: AbortSignal,
): Promise<IndicatorResult[]> {
  try {
    return await executeApiRequest<IndicatorResult[], unknown>(() =>
      getApiClient().GET("/v1/projects/{project_id}/results", {
        params: { path: { project_id: projectId } },
        signal: createRequestSignal(signal),
      }),
    );
  } catch (error) {
    throw normalizeAppError(error);
  }
}
