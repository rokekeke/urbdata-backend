import { QueryClient } from "@tanstack/react-query";

import { normalizeAppError } from "../errors";

export const DEFAULT_QUERY_STALE_TIME_MS = 30_000;

export function shouldRetryQuery(failureCount: number, error: unknown): boolean {
  const appError = normalizeAppError(error);
  return appError.canRetry && failureCount < 1;
}

export function createQueryClient(): QueryClient {
  return new QueryClient({
    defaultOptions: {
      queries: {
        staleTime: DEFAULT_QUERY_STALE_TIME_MS,
        gcTime: 5 * 60_000,
        retry: shouldRetryQuery,
        refetchOnWindowFocus: false,
      },
      mutations: {
        retry: false,
      },
    },
  });
}
