export const DEFAULT_API_TIMEOUT_MS = 15_000;

/** Combines TanStack Query cancellation with a deterministic request timeout. */
export function createRequestSignal(
  parentSignal?: AbortSignal,
  timeoutMs = DEFAULT_API_TIMEOUT_MS,
): AbortSignal {
  const timeoutSignal = AbortSignal.timeout(timeoutMs);
  return parentSignal ? AbortSignal.any([parentSignal, timeoutSignal]) : timeoutSignal;
}
