import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderHook, waitFor } from "@testing-library/react";
import type { PropsWithChildren } from "react";
import { describe, expect, it, vi } from "vitest";

import { useProjectRuns } from "../app/features/results/hooks/useProjectRuns";

const { listProjectRunsMock } = vi.hoisted(() => ({ listProjectRunsMock: vi.fn() }));

vi.mock("../app/features/results/api/listProjectRuns", async (importOriginal) => ({
  ...(await importOriginal<typeof import("../app/features/results/api/listProjectRuns")>()),
  listProjectRuns: listProjectRunsMock,
}));

function createWrapper() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return function Wrapper({ children }: PropsWithChildren) {
    return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
  };
}

describe("useProjectRuns", () => {
  it("não consulta histórico enquanto nenhum projeto estiver selecionado", () => {
    const { result } = renderHook(() => useProjectRuns(null), { wrapper: createWrapper() });
    expect(result.current.fetchStatus).toBe("idle");
    expect(listProjectRunsMock).not.toHaveBeenCalled();
  });

  it("expõe lista vazia como resposta válida", async () => {
    listProjectRunsMock.mockResolvedValue([]);
    const { result } = renderHook(() => useProjectRuns("project-1"), { wrapper: createWrapper() });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data).toEqual([]);
  });
});
