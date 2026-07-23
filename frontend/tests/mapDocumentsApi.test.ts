import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const config = {
  schema_version: "1" as const,
  name: "Mapa",
  title: "Mapa",
  basemap_id: "none",
  viewport: { longitude: -48.5, latitude: -27.6, zoom: 12, bearing: 0, pitch: 0 },
  layers: [],
};

describe("API de documentos cartográficos", () => {
  beforeEach(() => {
    vi.resetModules();
    vi.stubEnv("NEXT_PUBLIC_API_BASE_URL", "http://api.test");
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    vi.unstubAllEnvs();
  });

  it("lista as composições no escopo explícito de projeto e versão", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response("[]", { status: 200, headers: { "content-type": "application/json" } }),
    );
    vi.stubGlobal("fetch", fetchMock);
    const { listMapDocuments } = await import("../app/features/map-documents/api/mapDocuments");

    await expect(listMapDocuments("project-1", "version-1")).resolves.toEqual([]);
    const [request] = fetchMock.mock.calls[0];
    expect(request).toBeInstanceOf(Request);
    expect((request as Request).url).toBe("http://api.test/v1/projects/project-1/versions/version-1/documents");
  });

  it("preserva o documento atual retornado no conflito de revisão", async () => {
    const currentDocument = {
      id: "document-1",
      project_version_id: "version-1",
      name: "Mapa do servidor",
      config,
      revision: 3,
      schema_version: "1",
      created_at: "2026-07-20T12:00:00Z",
      updated_at: "2026-07-20T12:10:00Z",
    };
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(
      new Response(JSON.stringify({
        detail: {
          error: "map_document_revision_conflict",
          message: "A composição possui uma revisão mais recente.",
          context: { current_revision: 3, current_document: currentDocument },
        },
      }), { status: 409, headers: { "content-type": "application/json" } }),
    ));
    const { updateMapDocument } = await import("../app/features/map-documents/api/mapDocuments");

    await expect(updateMapDocument("project-1", "document-1", {
      name: "Meu rascunho",
      config: { ...config, name: "Meu rascunho" },
      expected_revision: 2,
    })).rejects.toMatchObject({
      kind: "conflict",
      code: "map_document_revision_conflict",
      context: { current_revision: 3, current_document: currentDocument },
    });
  });
});
