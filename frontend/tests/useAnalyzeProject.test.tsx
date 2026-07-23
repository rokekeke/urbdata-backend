import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, renderHook } from "@testing-library/react";
import type { PropsWithChildren } from "react";
import { describe, expect, it, vi } from "vitest";

import { useAnalyzeProject } from "../app/features/diagnostics/hooks/useAnalyzeProject";
import { AppError } from "../app/lib/errors";
import { queryKeys } from "../app/lib/query";

const { analyzeProjectMock } = vi.hoisted(() => ({ analyzeProjectMock: vi.fn() }));

vi.mock("../app/features/diagnostics/api/analyzeProject", async (importOriginal) => ({
  ...(await importOriginal<typeof import("../app/features/diagnostics/api/analyzeProject")>()),
  analyzeProject: analyzeProjectMock,
}));

function setup() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  function Wrapper({ children }: PropsWithChildren) {
    return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
  }
  return { queryClient, Wrapper };
}

describe("useAnalyzeProject", () => {
  it("envia os temas e atualiza imediatamente o cache de resultados", async () => {
    const response = {
      analysis_run_id: "run-1",
      status: "completed",
      results: [{
        indicator_code: "territorial.total_area",
        theme: "territorial",
        formula_version: "1.0.0",
        value: 1200,
        unit: "m2",
        metric_crs: "EPSG:31983",
        parameters: {},
        source_layers: ["perimetro"],
        contributing_feature_ids: ["feature-1"],
        warnings: [],
      }],
    };
    analyzeProjectMock.mockResolvedValue(response);
    const { queryClient, Wrapper } = setup();
    const { result } = renderHook(() => useAnalyzeProject("project-1"), { wrapper: Wrapper });

    await act(async () => {
      await result.current.mutateAsync(["territorial"]);
    });

    expect(analyzeProjectMock).toHaveBeenCalledWith("project-1", ["territorial"]);
    expect(queryClient.getQueryData(queryKeys.projects.results("project-1"))).toEqual(response.results);
  });

  it("preserva o erro de domínio e o contexto da camada faltante", async () => {
    const error = new AppError({
      kind: "validation",
      code: "required_layer_missing",
      message: "Required layer is missing for this analysis.",
      context: { layer_type: "perimetro" },
    });
    analyzeProjectMock.mockRejectedValue(error);
    const { Wrapper } = setup();
    const { result } = renderHook(() => useAnalyzeProject("project-1"), { wrapper: Wrapper });

    await act(async () => {
      await expect(result.current.mutateAsync(["territorial"])).rejects.toBe(error);
    });

    expect(result.current.error?.context.layer_type).toBe("perimetro");
  });
});
