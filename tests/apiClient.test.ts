import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

describe("cliente OpenAPI", () => {
  beforeEach(() => {
    vi.resetModules();
    vi.stubEnv("NEXT_PUBLIC_API_BASE_URL", "http://api.test");
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    vi.unstubAllEnvs();
  });

  it("consulta o health tipado sem acessar a rede", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ status: "ok" }), {
        status: 200,
        headers: { "content-type": "application/json" },
      }),
    );
    vi.stubGlobal("fetch", fetchMock);

    const { getApiHealth } = await import("../app/lib/api/health");
    const health = await getApiHealth();

    expect(health.status).toBe("ok");
    expect(fetchMock).toHaveBeenCalledOnce();
    const [request] = fetchMock.mock.calls[0];
    expect(request).toBeInstanceOf(Request);
    if (!(request instanceof Request)) throw new Error("O cliente não criou um Request.");
    expect(request.url).toBe("http://api.test/health");
  });

  it("preserva erro de domínio retornado pela API", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(
          JSON.stringify({
            detail: {
              error: "project_not_found",
              message: "Projeto não encontrado.",
              context: { project_id: "missing" },
            },
          }),
          { status: 404, headers: { "content-type": "application/json" } },
        ),
      ),
    );

    const { getApiHealth } = await import("../app/lib/api/health");
    await expect(getApiHealth()).rejects.toMatchObject({
      name: "ApiRequestError",
      kind: "http",
      status: 404,
      code: "project_not_found",
      message: "Projeto não encontrado.",
      context: { project_id: "missing" },
    });
  });

  it("diferencia falha de rede", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("offline")));
    const { getApiHealth } = await import("../app/lib/api/health");
    await expect(getApiHealth()).rejects.toMatchObject({
      name: "ApiRequestError",
      kind: "network",
    });
  });
});
