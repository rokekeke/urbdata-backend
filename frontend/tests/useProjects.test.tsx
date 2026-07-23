import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderHook, waitFor } from "@testing-library/react";
import type { PropsWithChildren } from "react";
import { describe, expect, it, vi } from "vitest";

import { AppError } from "../app/lib/errors";
import { useProjects } from "../app/features/projects/hooks/useProjects";
import { projectFixtures } from "./fixtures/projects";

const { listProjectsMock } = vi.hoisted(() => ({ listProjectsMock: vi.fn() }));

vi.mock("../app/features/projects/api/listProjects", async (importOriginal) => ({
  ...(await importOriginal<typeof import("../app/features/projects/api/listProjects")>()),
  listProjects: listProjectsMock,
}));

function createWrapper() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });

  return function Wrapper({ children }: PropsWithChildren) {
    return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
  };
}

describe("useProjects", () => {
  it("diferencia carregamento e sucesso", async () => {
    let resolveProjects!: (projects: typeof projectFixtures) => void;
    listProjectsMock.mockReturnValue(
      new Promise((resolve) => {
        resolveProjects = resolve;
      }),
    );

    const { result } = renderHook(() => useProjects(), { wrapper: createWrapper() });
    expect(result.current.isLoading).toBe(true);

    resolveProjects(projectFixtures);
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data).toEqual(projectFixtures);
    expect(result.current.isEmpty).toBe(false);
  });

  it("identifica lista vazia", async () => {
    listProjectsMock.mockResolvedValue([]);
    const { result } = renderHook(() => useProjects(), { wrapper: createWrapper() });
    await waitFor(() => expect(result.current.isEmpty).toBe(true));
    expect(result.current.data).toEqual([]);
  });

  it("expõe AppError sem acessar a rede", async () => {
    const error = new AppError({
      kind: "network",
      code: "network",
      message: "API indisponível",
      canRetry: true,
      presentation: "global",
    });
    listProjectsMock.mockRejectedValue(error);

    const { result } = renderHook(() => useProjects(), { wrapper: createWrapper() });
    await waitFor(() => expect(result.current.isError).toBe(true));
    expect(result.current.error).toBe(error);
    expect(result.current.isEmpty).toBe(false);
  });
});
