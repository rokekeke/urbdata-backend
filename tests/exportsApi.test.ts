import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const exportRecord = {
  id: "export-1",
  project_version_id: "version-1",
  analysis_run_id: null,
  format: "png",
  status: "completed" as const,
  config: { document_revision: 1 },
  file_path: "project/export-1.png",
  error: null,
  created_at: "2026-07-20T12:00:00Z",
  completed_at: "2026-07-20T12:01:00Z",
};

describe("API de exportação", () => {
  beforeEach(() => {
    vi.resetModules();
    vi.stubEnv("NEXT_PUBLIC_API_BASE_URL", "http://api.test");
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    vi.unstubAllEnvs();
  });

  it("envia o PNG como multipart sem fixar manualmente o boundary", async () => {
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
    vi.stubGlobal("Request", CapturedRequest);
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify(exportRecord), { status: 200, headers: { "content-type": "application/json" } }),
    );
    vi.stubGlobal("fetch", fetchMock);
    const { deliverExportFile } = await import("../app/features/exports/api/exports");
    await deliverExportFile("project-1", "export-1", new Blob(["png"], { type: "image/png" }));

    const [request] = fetchMock.mock.calls[0] as unknown as [CapturedRequest];
    expect(request.url).toBe("http://api.test/v1/projects/project-1/exports/export-1/file");
    expect(request.headers.get("content-type")).toBeNull();
    expect(request.body).toBeInstanceOf(FormData);
    expect((request.body as FormData).get("file")).toBeInstanceOf(Blob);
  });
});
