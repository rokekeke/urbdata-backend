import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderHook, waitFor } from "@testing-library/react";
import type { PropsWithChildren } from "react";
import { describe, expect, it, vi } from "vitest";

import { useProjectVersions } from "../app/features/projects/hooks/useProjectVersions";
import type { ProjectVersion } from "../app/features/projects/api/listProjectVersions";

const { listProjectVersionsMock } = vi.hoisted(() => ({ listProjectVersionsMock: vi.fn() }));

vi.mock("../app/features/projects/api/listProjectVersions", async (importOriginal) => ({
  ...(await importOriginal<typeof import("../app/features/projects/api/listProjectVersions")>()),
  listProjectVersions: listProjectVersionsMock,
}));

function wrapper() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return function Wrapper({ children }: PropsWithChildren) {
    return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
  };
}

const versions: ProjectVersion[] = [
  {
    id: "22222222-2222-4222-8222-222222222222",
    project_id: "11111111-1111-4111-8111-111111111111",
    name: "Versão arquivada",
    number: 2,
    description: null,
    parent_version_id: null,
    status: "archived",
    created_at: "2026-07-20T12:00:00Z",
    is_current: false,
  },
  {
    id: "33333333-3333-4333-8333-333333333333",
    project_id: "11111111-1111-4111-8111-111111111111",
    name: "Versão ativa",
    number: 1,
    description: null,
    parent_version_id: null,
    status: "active",
    created_at: "2026-07-19T12:00:00Z",
    is_current: true,
  },
];

describe("useProjectVersions", () => {
  it("resolve a versão ativa por is_current, sem depender da ordem", async () => {
    listProjectVersionsMock.mockResolvedValue(versions);
    const { result } = renderHook(
      () => useProjectVersions("11111111-1111-4111-8111-111111111111"),
      { wrapper: wrapper() },
    );

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.currentVersion?.id).toBe("33333333-3333-4333-8333-333333333333");
  });

  it("não consulta versões sem projeto selecionado", () => {
    listProjectVersionsMock.mockClear();
    const { result } = renderHook(() => useProjectVersions(null), { wrapper: wrapper() });
    expect(result.current.fetchStatus).toBe("idle");
    expect(listProjectVersionsMock).not.toHaveBeenCalled();
  });
});
