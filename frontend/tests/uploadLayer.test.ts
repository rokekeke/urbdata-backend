import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const layerRecord = {
  id: "layer-1",
  project_version_id: "version-1",
  layer_type: "territorio" as const,
  source_filename: "territorio.geojson",
  geometry_type: "Polygon",
  feature_count: 1,
  status: "uploaded" as const,
  uploaded_at: "2026-07-21T12:00:00Z",
  import_profile: "combined" as const,
  attributes_filename: null,
  attributes_join_key: null,
  geometry_join_key: null,
  join_summary: null,
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

function stubFetchReturning(record: unknown) {
  const fetchMock = vi.fn().mockResolvedValue(
    new Response(JSON.stringify(record), {
      status: 201,
      headers: { "content-type": "application/json" },
    }),
  );
  vi.stubGlobal("Request", CapturedRequest);
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

describe("API de upload de camada", () => {
  beforeEach(() => {
    vi.resetModules();
    vi.stubEnv("NEXT_PUBLIC_API_BASE_URL", "http://api.test");
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    vi.unstubAllEnvs();
  });

  it("envia somente layer_type e file quando nenhum atributo split e informado", async () => {
    const fetchMock = stubFetchReturning(layerRecord);
    const { uploadLayer } = await import("../app/features/layers/api/uploadLayer");
    const file = new File(["{}"], "t.geojson", { type: "application/geo+json" });

    await uploadLayer("project-1", "territorio", file);

    const [request] = fetchMock.mock.calls[0] as unknown as [CapturedRequest];
    expect(request.body).toBeInstanceOf(FormData);
    const form = request.body as FormData;
    expect(form.get("layer_type")).toBe("territorio");
    expect(form.get("file")).toBeInstanceOf(Blob);
    expect(form.get("import_profile")).toBeNull();
    expect(form.get("attributes_file")).toBeNull();
    expect(form.get("attributes_join_key")).toBeNull();
    expect(form.get("geometry_join_key")).toBeNull();
  });

  it("envia os campos do perfil split quando informados", async () => {
    const fetchMock = stubFetchReturning({
      ...layerRecord,
      import_profile: "split",
      attributes_filename: "a.csv",
      attributes_join_key: "Name",
      join_summary: { geometry_count: 1, attribute_count: 1, matched: 1 },
    });
    const { uploadLayer } = await import("../app/features/layers/api/uploadLayer");
    const geometryFile = new File(["{}"], "t.geojson", { type: "application/geo+json" });
    const attributesFile = new File(["Name;Area\nL01;100\n"], "a.csv", { type: "text/csv" });

    await uploadLayer("project-1", "territorio", geometryFile, {
      importProfile: "split",
      attributesFile,
      attributesJoinKey: "Name",
      geometryJoinKey: "URBDATA_ID",
    });

    const [request] = fetchMock.mock.calls[0] as unknown as [CapturedRequest];
    const form = request.body as FormData;
    expect(form.get("import_profile")).toBe("split");
    expect(form.get("attributes_file")).toBeInstanceOf(Blob);
    expect(form.get("attributes_join_key")).toBe("Name");
    expect(form.get("geometry_join_key")).toBe("URBDATA_ID");
  });
});
