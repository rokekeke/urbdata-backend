import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, renderHook, waitFor } from "@testing-library/react";
import type { FeatureCollection } from "geojson";
import type { PropsWithChildren } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { useLayerGeojsonQueries } from "../app/features/layers/hooks/useLayerGeojsonQueries";
import { AppError } from "../app/lib/errors";

const { getLayerGeojsonMock } = vi.hoisted(() => ({ getLayerGeojsonMock: vi.fn() }));

vi.mock("../app/features/layers/api/getLayerGeojson", () => ({
  getLayerGeojson: getLayerGeojsonMock,
}));

const readyCollection: FeatureCollection = {
  type: "FeatureCollection",
  features: [
    {
      type: "Feature",
      id: "feature-1",
      properties: { tipo: "Lote" },
      geometry: { type: "Point", coordinates: [-48.5, -27.6] },
    },
  ],
};

const emptyCollection: FeatureCollection = { type: "FeatureCollection", features: [] };

function wrapper() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return function Wrapper({ children }: PropsWithChildren) {
    return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
  };
}

beforeEach(() => {
  getLayerGeojsonMock.mockReset();
});

describe("useLayerGeojsonQueries", () => {
  it("mantém estados independentes para camada pronta, vazia e com erro", async () => {
    getLayerGeojsonMock.mockImplementation((_projectId: string, layerId: string) => {
      if (layerId === "ready") return Promise.resolve(readyCollection);
      if (layerId === "empty") return Promise.resolve(emptyCollection);
      return Promise.reject(new AppError({
        kind: "network",
        code: "network",
        message: "Camada indisponível",
        canRetry: true,
      }));
    });

    const { result } = renderHook(
      () => useLayerGeojsonQueries("project-1", ["ready", "empty", "error"]),
      { wrapper: wrapper() },
    );

    await waitFor(() => expect(result.current.stateByLayerId.error?.status).toBe("error"));
    expect(result.current.stateByLayerId.ready).toMatchObject({ status: "ready", featureCount: 1 });
    expect(result.current.stateByLayerId.empty).toMatchObject({ status: "empty", featureCount: 0 });
    expect(result.current.readyCount).toBe(1);
    expect(result.current.emptyCount).toBe(1);
    expect(result.current.errors).toHaveLength(1);
  });

  it("permite repetir somente a camada que falhou", async () => {
    getLayerGeojsonMock
      .mockRejectedValueOnce(new AppError({
        kind: "network",
        code: "network",
        message: "Falha temporária",
        canRetry: true,
      }))
      .mockResolvedValueOnce(readyCollection);

    const { result } = renderHook(
      () => useLayerGeojsonQueries("project-1", ["layer-1"]),
      { wrapper: wrapper() },
    );
    await waitFor(() => expect(result.current.stateByLayerId["layer-1"]?.status).toBe("error"));

    await act(async () => result.current.retryLayer("layer-1"));
    await waitFor(() => expect(result.current.stateByLayerId["layer-1"]?.status).toBe("ready"));
    expect(getLayerGeojsonMock).toHaveBeenCalledTimes(2);
  });

  it("mantém a geometria anterior quando uma atualização falha", async () => {
    getLayerGeojsonMock
      .mockResolvedValueOnce(readyCollection)
      .mockRejectedValueOnce(new AppError({
        kind: "network",
        code: "network",
        message: "Falha na atualização",
        canRetry: true,
      }));

    const { result } = renderHook(
      () => useLayerGeojsonQueries("project-1", ["layer-1"]),
      { wrapper: wrapper() },
    );
    await waitFor(() => expect(result.current.stateByLayerId["layer-1"]?.status).toBe("ready"));

    await act(async () => result.current.retryLayer("layer-1"));
    await waitFor(() => expect(result.current.stateByLayerId["layer-1"]?.status).toBe("stale"));
    expect(result.current.dataByLayerId["layer-1"]).toBe(readyCollection);
  });
});
