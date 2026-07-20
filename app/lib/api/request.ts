export type ApiFailureKind =
  | "http"
  | "network"
  | "timeout"
  | "cancelled"
  | "invalid_response";

interface ApiRequestErrorOptions {
  kind: ApiFailureKind;
  message: string;
  status?: number;
  code?: string;
  context?: Record<string, unknown>;
  payload?: unknown;
  cause?: unknown;
}

export class ApiRequestError extends Error {
  readonly kind: ApiFailureKind;
  readonly status: number | null;
  readonly code: string;
  readonly context: Record<string, unknown>;
  readonly payload: unknown;

  constructor(options: ApiRequestErrorOptions) {
    super(options.message, { cause: options.cause });
    this.name = "ApiRequestError";
    this.kind = options.kind;
    this.status = options.status ?? null;
    this.code = options.code ?? options.kind;
    this.context = options.context ?? {};
    this.payload = options.payload;
  }
}

type ApiFetchResult<TData, TError> =
  | { data: TData; response: Response }
  | { error: TError; response: Response };

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function readDomainError(payload: unknown): {
  code?: string;
  message?: string;
  context?: Record<string, unknown>;
} {
  if (!isRecord(payload) || !isRecord(payload.detail)) return {};

  const detail = payload.detail;
  return {
    code: typeof detail.error === "string" ? detail.error : undefined,
    message: typeof detail.message === "string" ? detail.message : undefined,
    context: isRecord(detail.context) ? detail.context : undefined,
  };
}

function httpError(response: Response, payload: unknown): ApiRequestError {
  const detail = readDomainError(payload);
  return new ApiRequestError({
    kind: "http",
    status: response.status,
    code: detail.code ?? `http_${response.status}`,
    message: detail.message ?? `A API respondeu com o status HTTP ${response.status}.`,
    context: detail.context,
    payload,
  });
}

function isAbortError(error: unknown): boolean {
  return error instanceof Error && error.name === "AbortError";
}

function isTimeoutError(error: unknown): boolean {
  return error instanceof Error && error.name === "TimeoutError";
}

/** Converts openapi-fetch results and transport failures into one typed boundary. */
export async function executeApiRequest<TData, TError>(
  request: () => Promise<ApiFetchResult<TData, TError>>,
): Promise<TData> {
  try {
    const result = await request();
    if ("error" in result) {
      throw httpError(result.response, result.error);
    }
    return result.data;
  } catch (error) {
    if (error instanceof ApiRequestError) throw error;

    if (isTimeoutError(error)) {
      throw new ApiRequestError({
        kind: "timeout",
        message: "A API demorou mais que o esperado para responder.",
        cause: error,
      });
    }

    if (isAbortError(error)) {
      throw new ApiRequestError({
        kind: "cancelled",
        message: "A solicitação foi cancelada.",
        cause: error,
      });
    }

    if (error instanceof SyntaxError) {
      throw new ApiRequestError({
        kind: "invalid_response",
        message: "A API retornou uma resposta que não pôde ser interpretada.",
        cause: error,
      });
    }

    throw new ApiRequestError({
      kind: "network",
      message: "Não foi possível se comunicar com a API do URBDATA.",
      cause: error,
    });
  }
}
