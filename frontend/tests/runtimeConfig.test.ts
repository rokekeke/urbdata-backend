import { describe, expect, it } from "vitest";

import { RuntimeConfigError, resolveApiBaseUrl } from "../app/lib/runtimeConfig";

describe("resolveApiBaseUrl", () => {
  it("normaliza espaços e barras finais", () => {
    expect(resolveApiBaseUrl("  http://localhost:8000///  ")).toBe("http://localhost:8000");
  });

  it.each([
    [undefined, "não foi configurada"],
    ["not a url", "URL absoluta"],
    ["ftp://localhost:8000", "http ou https"],
    ["https://user:password@example.com", "não pode conter usuário"],
    ["https://example.com?token=public", "query string"],
    ["https://example.com#api", "fragmento"],
  ])("rejeita configuração inválida %#", (value, message) => {
    expect(() => resolveApiBaseUrl(value)).toThrow(RuntimeConfigError);
    expect(() => resolveApiBaseUrl(value)).toThrow(message);
  });
});
