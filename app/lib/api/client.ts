import createClient, { type Client, type Middleware } from "openapi-fetch";

import { getApiBaseUrl } from "../runtimeConfig";
import type { paths } from "./schema";

let client: Client<paths> | undefined;
const registeredMiddleware = new Set<Middleware>();

/** Returns the only API client instance used by the application. */
export function getApiClient(): Client<paths> {
  if (!client) {
    client = createClient<paths>({ baseUrl: getApiBaseUrl() });
    if (registeredMiddleware.size > 0) {
      client.use(...registeredMiddleware);
    }
  }

  return client;
}

/**
 * Extension point for tracing or future authentication. The MVP registers no
 * authentication middleware and never invents a token.
 */
export function registerApiMiddleware(...middleware: Middleware[]): void {
  for (const item of middleware) {
    registeredMiddleware.add(item);
  }
  client?.use(...middleware);
}

export function ejectApiMiddleware(...middleware: Middleware[]): void {
  for (const item of middleware) {
    registeredMiddleware.delete(item);
  }
  client?.eject(...middleware);
}
