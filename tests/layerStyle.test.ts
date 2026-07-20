import { describe, expect, it } from "vitest";

import type { LayerAttributes } from "../app/features/layers/api/getLayerAttributes";
import type { ProjectLayer } from "../app/features/layers/api/listProjectLayers";
import { applyLayerAttributes, createLayerStyle } from "../app/features/layers/model/layerStyle";

const layer: ProjectLayer = {
  id: "44444444-4444-4444-8444-444444444444",
  project_version_id: "33333333-3333-4333-8333-333333333333",
  layer_type: "territorio",
  source_filename: "territorio.geojson",
  geometry_type: "MultiPolygon",
  feature_count: 14,
  status: "mapped",
  uploaded_at: "2026-07-20T12:00:00Z",
};

const attributes: LayerAttributes = {
  layer_id: layer.id,
  source_fields: ["Comments", "Area"],
  sample_values: { Comments: ["LOTE", "APP"] },
  suggested_mapping: {},
  feature_count: 14,
  compatible_indicators: ["territorial.area_by_class"],
  fields: [
    {
      field: "Comments",
      origin: "source",
      detected_type: "text",
      present_count: 14,
      empty_count: 0,
      cardinality: 2,
      distinct_values: ["LOTE", "APP"],
      min_value: null,
      max_value: null,
      recommended_mode: "categorical",
      unsuitable_reason: null,
    },
    {
      field: "Area",
      origin: "source",
      detected_type: "numeric",
      present_count: 14,
      empty_count: 0,
      cardinality: 14,
      distinct_values: null,
      min_value: 120,
      max_value: 3400,
      recommended_mode: "sequential",
      unsuitable_reason: null,
    },
  ],
};

describe("layerStyle", () => {
  it("deriva a camada visual sem copiar o payload de transporte", () => {
    const style = createLayerStyle(layer);
    expect(style.id).toBe(layer.id);
    expect(style.geometry).toBe("polygon");
    expect(style.shortName).toBe("Território");
    expect(style.representation).toBe("single");
    expect(style.projectVersionId).toBe(layer.project_version_id);
  });

  it("transforma estatísticas de atributos em opções de representação", () => {
    const style = applyLayerAttributes(createLayerStyle(layer), attributes);
    expect(style.representationOptions).toHaveLength(3);
    expect(style.representationOptions[1]).toMatchObject({
      value: "Comments",
      recommendedMode: "categorical",
      distinctValues: ["LOTE", "APP"],
    });
    expect(style.representationOptions[2]).toMatchObject({
      value: "Area",
      recommendedMode: "sequential",
      range: [120, 3400],
    });
  });
});
