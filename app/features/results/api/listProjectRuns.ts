import type { components } from "../../../lib/api/schema";
import { getApiClient } from "../../../lib/api/client";
import { executeApiRequest } from "../../../lib/api/request";
import { createRequestSignal } from "../../../lib/api/requestSignal";
import { normalizeAppError } from "../../../lib/errors";

export type AnalysisRun = components["schemas"]["AnalysisRunOut"];

export async function listProjectRuns(
  projectId: string,
  signal?: AbortSignal,
): Promise<AnalysisRun[]> {
  try {
    return await executeApiRequest<AnalysisRun[], unknown>(() =>
      getApiClient().GET("/v1/projects/{project_id}/runs", {
        params: { path: { project_id: projectId } },
        signal: createRequestSignal(signal),
      }),
    );
  } catch (error) {
    throw normalizeAppError(error);
  }
}
