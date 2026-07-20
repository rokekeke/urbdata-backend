import type { FeatureCollection, Geometry } from "geojson";

import type { components } from "../../../lib/api/schema";
import { getApiClient } from "../../../lib/api/client";
import { executeApiRequest } from "../../../lib/api/request";
import { createRequestSignal } from "../../../lib/api/requestSignal";
import { AppError, normalizeAppError } from "../../../lib/errors";

type ApiFeatureCollection = components["schemas"]["GeoJSONFeatureCollectionOut"];

const geometryTypes = new Set([
  "Point",
  "MultiPoint",
  "LineString",
  "MultiLineString",
  "Polygon",
  "MultiPolygon",
  "GeometryCollection",
]);

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function isGeometry(value: unknown): value is Geometry {
  if (!isRecord(value) || typeof value.type !== "string" || !geometryTypes.has(value.type)) {
    return false;
  }
  return value.type === "GeometryCollection"
    ? Array.isArray(value.geometries)
    : Array.isArray(value.coordinates);
}

function toFeatureCollection(payload: ApiFeatureCollection): FeatureCollection {
  const features = payload.features.map((feature) => {
    if (!isGeometry(feature.geometry)) {
      throw new AppError({
        kind: "invalid_response",
        code: "invalid_geojson_geometry",
        message: "Uma geometria recebida da API não possui um formato GeoJSON válido.",
        context: { feature_id: feature.id },
        canRetry: true,
        presentation: "global",
      });
    }
    return {
      type: "Feature" as const,
      id: feature.id,
      geometry: feature.geometry,
      properties: feature.properties,
    };
  });
  return { type: "FeatureCollection", features };
}

export async function getLayerGeojson(
  projectId: string,
  layerId: string,
  signal?: AbortSignal,
): Promise<FeatureCollection> {
  try {
    const payload = await executeApiRequest<ApiFeatureCollection, unknown>(() =>
      getApiClient().GET("/v1/projects/{project_id}/layers/{layer_id}/geojson", {
        params: { path: { project_id: projectId, layer_id: layerId } },
        signal: createRequestSignal(signal),
      }),
    );
    return toFeatureCollection(payload);
  } catch (error) {
    throw normalizeAppError(error);
  }
}
