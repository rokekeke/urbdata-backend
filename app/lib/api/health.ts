import type { MethodResponse } from "openapi-fetch";

import { getApiClient } from "./client";
import { executeApiRequest } from "./request";

export type ApiHealth = MethodResponse<ReturnType<typeof getApiClient>, "get", "/health">;

/** Minimal typed request used to verify the frontend/backend boundary. */
export function getApiHealth(signal?: AbortSignal): Promise<ApiHealth> {
  return executeApiRequest<ApiHealth, unknown>(() => getApiClient().GET("/health", { signal }));
}
