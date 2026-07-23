import type { components } from "../../../lib/api/schema";
import { getApiClient } from "../../../lib/api/client";
import { executeApiRequest } from "../../../lib/api/request";
import { createRequestSignal } from "../../../lib/api/requestSignal";
import { normalizeAppError } from "../../../lib/errors";

export type Basemap = components["schemas"]["BasemapOut"];

export async function listBasemaps(signal?: AbortSignal): Promise<Basemap[]> {
  try {
    return await executeApiRequest<Basemap[], unknown>(() =>
      getApiClient().GET("/v1/map-basemaps", {
        signal: createRequestSignal(signal),
      }),
    );
  } catch (error) {
    throw normalizeAppError(error);
  }
}
