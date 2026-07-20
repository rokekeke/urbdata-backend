export const queryKeys = {
  projects: {
    all: ["projects"] as const,
    list: () => ["projects", "list"] as const,
    detail: (projectId: string) => ["projects", "detail", projectId] as const,
    versions: (projectId: string) => ["projects", projectId, "versions"] as const,
    layers: (projectId: string, versionId: string) =>
      ["projects", projectId, "versions", versionId, "layers"] as const,
    results: (projectId: string) => ["projects", projectId, "results"] as const,
    runs: (projectId: string) => ["projects", projectId, "runs"] as const,
    documents: (projectId: string, versionId: string) =>
      ["projects", projectId, "versions", versionId, "documents"] as const,
  },
  layers: {
    geojson: (projectId: string, layerId: string) =>
      ["layers", layerId, "geojson", projectId] as const,
    attributes: (projectId: string, layerId: string) =>
      ["layers", layerId, "attributes", projectId] as const,
  },
  catalog: {
    indicators: ["catalog", "indicators"] as const,
    basemaps: ["catalog", "basemaps"] as const,
  },
};
