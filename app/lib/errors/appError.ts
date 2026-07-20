import { ApiRequestError } from "../api/request";

export type AppErrorKind =
  | "bad_request"
  | "not_found"
  | "conflict"
  | "payload_too_large"
  | "validation"
  | "server"
  | "network"
  | "timeout"
  | "cancelled"
  | "invalid_response"
  | "unknown";

export type ErrorPresentation = "inline" | "global" | "silent";

interface AppErrorOptions {
  kind: AppErrorKind;
  message: string;
  code: string;
  status?: number | null;
  context?: Record<string, unknown>;
  canRetry?: boolean;
  presentation?: ErrorPresentation;
  cause?: unknown;
}

export class AppError extends Error {
  readonly kind: AppErrorKind;
  readonly code: string;
  readonly status: number | null;
  readonly context: Record<string, unknown>;
  readonly canRetry: boolean;
  readonly presentation: ErrorPresentation;

  constructor(options: AppErrorOptions) {
    super(options.message, { cause: options.cause });
    this.name = "AppError";
    this.kind = options.kind;
    this.code = options.code;
    this.status = options.status ?? null;
    this.context = options.context ?? {};
    this.canRetry = options.canRetry ?? false;
    this.presentation = options.presentation ?? "inline";
  }
}

interface HttpErrorDefaults {
  kind: AppErrorKind;
  message: string;
  canRetry: boolean;
  presentation: ErrorPresentation;
}

const HTTP_DEFAULTS: Record<number, HttpErrorDefaults> = {
  400: {
    kind: "bad_request",
    message: "Não foi possível concluir a solicitação com os dados informados.",
    canRetry: false,
    presentation: "inline",
  },
  404: {
    kind: "not_found",
    message: "O recurso solicitado não foi encontrado.",
    canRetry: false,
    presentation: "inline",
  },
  409: {
    kind: "conflict",
    message: "Este conteúdo foi alterado em outra sessão. Recarregue os dados antes de continuar.",
    canRetry: false,
    presentation: "inline",
  },
  413: {
    kind: "payload_too_large",
    message: "O arquivo excede o tamanho permitido.",
    canRetry: false,
    presentation: "inline",
  },
  422: {
    kind: "validation",
    message: "Revise os campos informados e tente novamente.",
    canRetry: false,
    presentation: "inline",
  },
};

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function extractValidationIssues(payload: unknown): Array<Record<string, unknown>> {
  if (!isRecord(payload) || !Array.isArray(payload.detail)) return [];

  return payload.detail.filter(isRecord).map((issue) => ({
    location: Array.isArray(issue.loc) ? issue.loc : [],
    message: typeof issue.msg === "string" ? issue.msg : "Valor inválido.",
    type: typeof issue.type === "string" ? issue.type : "validation_error",
  }));
}

function actionableBackendMessage(error: ApiRequestError): string | undefined {
  return error.kind === "http" && !error.code.startsWith("http_") ? error.message : undefined;
}

function fromHttpError(error: ApiRequestError): AppError {
  const status = error.status ?? 500;
  const defaults = HTTP_DEFAULTS[status] ?? {
    kind: "server" as const,
    message: "O URBDATA encontrou um problema ao processar a solicitação.",
    canRetry: status >= 500,
    presentation: "global" as const,
  };
  const validationIssues = status === 422 ? extractValidationIssues(error.payload) : [];

  return new AppError({
    ...defaults,
    status,
    code: error.code,
    message: actionableBackendMessage(error) ?? defaults.message,
    context:
      validationIssues.length > 0
        ? { ...error.context, validation_issues: validationIssues }
        : error.context,
    cause: error,
  });
}

export function normalizeAppError(error: unknown): AppError {
  if (error instanceof AppError) return error;

  if (error instanceof ApiRequestError) {
    if (error.kind === "http") return fromHttpError(error);

    const transportDefaults: Record<Exclude<ApiRequestError["kind"], "http">, AppErrorOptions> = {
      network: {
        kind: "network",
        code: error.code,
        message: error.message,
        canRetry: true,
        presentation: "global",
      },
      timeout: {
        kind: "timeout",
        code: error.code,
        message: error.message,
        canRetry: true,
        presentation: "global",
      },
      cancelled: {
        kind: "cancelled",
        code: error.code,
        message: error.message,
        canRetry: false,
        presentation: "silent",
      },
      invalid_response: {
        kind: "invalid_response",
        code: error.code,
        message: error.message,
        canRetry: true,
        presentation: "global",
      },
    };

    return new AppError({ ...transportDefaults[error.kind], cause: error });
  }

  return new AppError({
    kind: "unknown",
    code: "unexpected_error",
    message: "Ocorreu um erro inesperado. Tente novamente.",
    canRetry: false,
    presentation: "global",
    cause: error,
  });
}
