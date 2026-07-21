import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const mappingResult = {
  layer_id: "layer-1",
  status: "mapped",
  features_updated: 12,
  warnings: [{ feature_id: "feature-1", message: "Area com unidade nao reconhecida." }],
};

class CapturedRequest {
  readonly url: string;
  readonly headers: Headers;
  readonly method: string;
  readonly body: BodyInit | null;

  constructor(input: string | URL, init?: RequestInit) {
    this.url = String(input);
    this.headers = new Headers(init?.headers);
    this.method = init?.method ?? "GET";
    this.body = init?.body ?? null;
  }
}

describe("API de mapeamento de atributos (f5.1)", () => {
  beforeEach(() => {
    vi.resetModules();
    vi.stubEnv("NEXT_PUBLIC_API_BASE_URL", "http://api.test");
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    vi.unstubAllEnvs();
  });

  it("envia PATCH com o corpo mappings e devolve os warnings", async () => {
    vi.stubGlobal("Request", CapturedRequest);
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify(mappingResult), {
        status: 200,
        headers: { "content-type": "application/json" },
      }),
    );
    vi.stubGlobal("fetch", fetchMock);
    const { updateLayerAttributeMapping } = await import(
      "../app/features/layers/api/updateLayerAttributeMapping"
    );

    const result = await updateLayerAttributeMapping("project-1", "layer-1", {
      macroarea: "Comments",
      quadra_id: null,
    });

    const [request] = fetchMock.mock.calls[0] as unknown as [CapturedRequest];
    expect(request.method).toBe("PATCH");
    expect(request.url).toBe(
      "http://api.test/v1/projects/project-1/layers/layer-1/attributes",
    );
    expect(JSON.parse(request.body as string)).toEqual({
      mappings: { macroarea: "Comments", quadra_id: null },
    });
    expect(result.warnings).toHaveLength(1);
    expect(result.features_updated).toBe(12);
  });
});
