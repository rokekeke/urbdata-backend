import type { components } from "../../../lib/api/schema";
import { getApiClient } from "../../../lib/api/client";
import { executeApiRequest } from "../../../lib/api/request";
import { normalizeAppError } from "../../../lib/errors";
import type { Project } from "./listProjects";

export type ProjectCreateInput = components["schemas"]["ProjectCreate"];

export async function createProject(payload: ProjectCreateInput): Promise<Project> {
  try {
    return await executeApiRequest<Project, unknown>(() =>
      getApiClient().POST("/v1/projects", { body: payload }),
    );
  } catch (error) {
    throw normalizeAppError(error);
  }
}
