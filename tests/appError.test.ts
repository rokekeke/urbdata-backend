import { describe, expect, it } from "vitest";

import { ApiRequestError } from "../app/lib/api/request";
import { AppError, normalizeAppError } from "../app/lib/errors";
import { shouldRetryQuery } from "../app/lib/query";

describe("normalizeAppError", () => {
  it("preserva mensagem e contexto acionáveis do backend", () => {
    const source = new ApiRequestError({
      kind: "http",
      status: 422,
      code: "required_layer_missing",
      message: "A camada de perímetro é obrigatória.",
      context: { layer_type: "perimetro" },
      payload: {
        detail: {
          error: "required_layer_missing",
          message: "A camada de perímetro é obrigatória.",
          context: { layer_type: "perimetro" },
        },
      },
    });

    const error = normalizeAppError(source);
    expect(error).toMatchObject({
      kind: "validation",
      code: "required_layer_missing",
      message: "A camada de perímetro é obrigatória.",
      context: { layer_type: "perimetro" },
      presentation: "inline",
      canRetry: false,
    });
  });

  it("transforma o 422 nativo do FastAPI sem perder os campos inválidos", () => {
    const source = new ApiRequestError({
      kind: "http",
      status: 422,
      code: "http_422",
      message: "A API respondeu com o status HTTP 422.",
      payload: {
        detail: [
          { loc: ["body", "themes"], msg: "Field required", type: "missing" },
        ],
      },
    });

    const error = normalizeAppError(source);
    expect(error.kind).toBe("validation");
    expect(error.message).toBe("Revise os campos informados e tente novamente.");
    expect(error.context.validation_issues).toEqual([
      { location: ["body", "themes"], message: "Field required", type: "missing" },
    ]);
  });

  it.each([
    [400, "bad_request", "inline", false],
    [404, "not_found", "inline", false],
    [409, "conflict", "inline", false],
    [413, "payload_too_large", "inline", false],
    [500, "server", "global", true],
  ] as const)("mapeia HTTP %i para %s", (status, kind, presentation, canRetry) => {
    const error = normalizeAppError(
      new ApiRequestError({
        kind: "http",
        status,
        code: `http_${status}`,
        message: `HTTP ${status}`,
      }),
    );

    expect(error).toMatchObject({ kind, presentation, canRetry, status });
  });

  it.each([
    ["network", "network", "global", true],
    ["timeout", "timeout", "global", true],
    ["cancelled", "cancelled", "silent", false],
    ["invalid_response", "invalid_response", "global", true],
  ] as const)("mapeia falha de transporte %s", (sourceKind, kind, presentation, canRetry) => {
    const error = normalizeAppError(
      new ApiRequestError({ kind: sourceKind, message: `Falha ${sourceKind}` }),
    );
    expect(error).toMatchObject({ kind, presentation, canRetry });
  });

  it("mantém AppError idempotente e normaliza falhas inesperadas", () => {
    const original = new AppError({
      kind: "not_found",
      code: "missing",
      message: "Ausente",
    });
    expect(normalizeAppError(original)).toBe(original);
    expect(normalizeAppError(new Error("boom"))).toMatchObject({
      kind: "unknown",
      code: "unexpected_error",
      presentation: "global",
    });
  });
});

describe("shouldRetryQuery", () => {
  it("repete somente uma vez erros recuperáveis", () => {
    const networkError = new ApiRequestError({ kind: "network", message: "offline" });
    expect(shouldRetryQuery(0, networkError)).toBe(true);
    expect(shouldRetryQuery(1, networkError)).toBe(false);
  });

  it("não repete validação", () => {
    const validationError = new ApiRequestError({
      kind: "http",
      status: 422,
      code: "http_422",
      message: "inválido",
    });
    expect(shouldRetryQuery(0, validationError)).toBe(false);
  });
});
