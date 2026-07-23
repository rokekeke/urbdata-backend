import type { components } from "../../../lib/api/schema";
import { getApiClient } from "../../../lib/api/client";
import { executeApiRequest } from "../../../lib/api/request";
import { createRequestSignal } from "../../../lib/api/requestSignal";
import { normalizeAppError } from "../../../lib/errors";

export type Project = components["schemas"]["ProjectOut"];

export async function listProjects(signal?: AbortSignal): Promise<Project[]> {
  try {
    return await executeApiRequest<Project[], unknown>(() =>
      getApiClient().GET("/v1/projects", { signal: createRequestSignal(signal) }),
    );
  } catch (error) {
    throw normalizeAppError(error);
  }
}
