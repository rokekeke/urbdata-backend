import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, renderHook } from "@testing-library/react";
import type { PropsWithChildren } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { useExportWorkflow } from "../app/features/exports/hooks/useExportWorkflow";

const mocks = vi.hoisted(() => ({
  createExport: vi.fn(),
  deliverExportFile: vi.fn(),
  getExport: vi.fn(),
}));

vi.mock("../app/features/exports/api/exports", async (importOriginal) => ({
  ...(await importOriginal<typeof import("../app/features/exports/api/exports")>()),
  ...mocks,
}));

function setup() {
  const queryClient = new QueryClient({ defaultOptions: { mutations: { retry: false } } });
  function Wrapper({ children }: PropsWithChildren) {
    return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
  }
  return Wrapper;
}

function record(revision: number, status: "pending" | "completed") {
  return {
    id: "export-1",
    project_version_id: "version-1",
    analysis_run_id: null,
    format: "png",
    status,
    config: { document_revision: revision },
    file_path: status === "completed" ? "project/export-1.png" : null,
    error: null,
    created_at: "2026-07-20T12:00:00Z",
    completed_at: status === "completed" ? "2026-07-20T12:01:00Z" : null,
  };
}

describe("useExportWorkflow", () => {
  beforeEach(() => vi.clearAllMocks());

  it("congela, renderiza, entrega e confirma o PNG nesta ordem", async () => {
    const events: string[] = [];
    mocks.createExport.mockImplementation(async () => { events.push("snapshot"); return record(2, "pending"); });
    mocks.deliverExportFile.mockImplementation(async () => { events.push("upload"); return record(2, "completed"); });
    mocks.getExport.mockImplementation(async () => { events.push("verify"); return record(2, "completed"); });
    const render = vi.fn(async () => { events.push("render"); return new Blob(["png"], { type: "image/png" }); });
    const { result } = renderHook(() => useExportWorkflow("project-1"), { wrapper: setup() });

    await act(async () => {
      await result.current.start({
        documentId: "document-1",
        expectedRevision: 2,
        legend: true,
        image: { ratio_id: "screen", resolution_id: "1x", width_px: 1440, height_px: 900 },
        analysisRunId: null,
        render,
      });
    });

    expect(events).toEqual(["snapshot", "render", "upload", "verify"]);
    expect(result.current.stage).toBe("completed");
  });

  it("interrompe antes da renderização quando o servidor congelou outra revisão", async () => {
    mocks.createExport.mockResolvedValue(record(3, "pending"));
    const render = vi.fn();
    const { result } = renderHook(() => useExportWorkflow("project-1"), { wrapper: setup() });

    await act(async () => {
      await expect(result.current.start({
        documentId: "document-1",
        expectedRevision: 2,
        legend: true,
        image: { ratio_id: "screen", resolution_id: "1x", width_px: 1440, height_px: 900 },
        analysisRunId: null,
        render,
      })).rejects.toMatchObject({ code: "export_document_revision_mismatch", kind: "conflict" });
    });

    expect(render).not.toHaveBeenCalled();
    expect(mocks.deliverExportFile).not.toHaveBeenCalled();
  });
});
