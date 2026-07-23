import { getApiClient } from "../../../lib/api/client";
import { executeApiRequest } from "../../../lib/api/request";
import { createRequestSignal } from "../../../lib/api/requestSignal";
import { normalizeAppError } from "../../../lib/errors";
import type { IndicatorResult } from "./listProjectResults";

export async function listRunResults(
  projectId: string,
  runId: string,
  signal?: AbortSignal,
): Promise<IndicatorResult[]> {
  try {
    return await executeApiRequest<IndicatorResult[], unknown>(() =>
      getApiClient().GET("/v1/projects/{project_id}/runs/{run_id}/results", {
        params: { path: { project_id: projectId, run_id: runId } },
        signal: createRequestSignal(signal),
      }),
    );
  } catch (error) {
    throw normalizeAppError(error);
  }
}
