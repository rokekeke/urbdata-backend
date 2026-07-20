import type { components } from "../../../lib/api/schema";
import { getApiClient } from "../../../lib/api/client";
import { executeApiRequest } from "../../../lib/api/request";
import { createRequestSignal } from "../../../lib/api/requestSignal";
import { normalizeAppError } from "../../../lib/errors";

export type CatalogIndicator = components["schemas"]["CatalogIndicatorOut"];

export async function listCatalogIndicators(signal?: AbortSignal): Promise<CatalogIndicator[]> {
  try {
    return await executeApiRequest<CatalogIndicator[], unknown>(() =>
      getApiClient().GET("/v1/catalog/indicators", {
        signal: createRequestSignal(signal),
      }),
    );
  } catch (error) {
    throw normalizeAppError(error);
  }
}
