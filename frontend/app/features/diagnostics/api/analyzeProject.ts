import type { components } from "../../../lib/api/schema";
import { getApiClient } from "../../../lib/api/client";
import { executeApiRequest } from "../../../lib/api/request";
import { normalizeAppError } from "../../../lib/errors";

export type AnalyzeResponse = components["schemas"]["AnalyzeResponse"];

export async function analyzeProject(
  projectId: string,
  themes: string[],
): Promise<AnalyzeResponse> {
  try {
    return await executeApiRequest<AnalyzeResponse, unknown>(() =>
      getApiClient().POST("/v1/projects/{project_id}/analyze", {
        params: { path: { project_id: projectId } },
        body: { themes },
      }),
    );
  } catch (error) {
    throw normalizeAppError(error);
  }
}
