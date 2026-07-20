import type { LayerAttributes } from "../api/getLayerAttributes";
import type { ProjectLayer } from "../api/listProjectLayers";
import type {
  GeometryKind,
  LayerStyleConfig,
  RepresentationMode,
  RepresentationOption,
} from "../../../lib/types";

const layerLabels: Record<ProjectLayer["layer_type"], string> = {
  perimetro: "Perímetro",
  quadras: "Quadras",
  lotes: "Lotes",
  sistema_viario: "Sistema viário",
  uso_solo: "Uso do solo",
  areas_verdes: "Áreas verdes",
  equipamentos: "Equipamentos",
  edificacoes: "Edificações",
  desconexoes_viarias: "Desconexões viárias",
  territorio: "Território",
};

const layerColors: Record<ProjectLayer["layer_type"], [string, string, string]> = {
  perimetro: ["#F4F2ED", "#172A25", "#172A25"],
  quadras: ["#DCE8E8", "#3D6F78", "#29545D"],
  lotes: ["#D6B17B", "#9C7F6A", "#5F4E43"],
  sistema_viario: ["#995044", "#C78268", "#7F4138"],
  uso_solo: ["#D6B17B", "#557681", "#43564F"],
  areas_verdes: ["#6D9375", "#A6C0A0", "#355847"],
  equipamentos: ["#4D7390", "#9DB8C9", "#34566F"],
  edificacoes: ["#7B8682", "#BEC5BF", "#43564F"],
  desconexoes_viarias: ["#C89235", "#E6C487", "#8A5C28"],
  territorio: ["#D6B17B", "#3D6F78", "#384541"],
};

const categoryPalette = ["#D6B17B", "#889296", "#6D9375", "#3D746A", "#9C7F6A", "#4D7390"];

function geometryKind(geometryType: string | null): GeometryKind {
  const normalized = geometryType?.toLowerCase() ?? "";
  if (normalized.includes("line")) return "line";
  if (normalized.includes("point")) return "point";
  return "polygon";
}

export function createLayerStyle(layer: ProjectLayer): LayerStyleConfig {
  const [color, secondaryColor, strokeColor] = layerColors[layer.layer_type];
  return {
    id: layer.id,
    name: layerLabels[layer.layer_type],
    shortName: layerLabels[layer.layer_type],
    geometry: geometryKind(layer.geometry_type),
    visible: true,
    opacity: layer.layer_type === "perimetro" ? 0.08 : 0.72,
    color,
    secondaryColor,
    strokeColor,
    strokeWidth: layer.layer_type === "perimetro" ? 2.4 : layer.geometry_type?.toLowerCase().includes("line") ? 2.8 : 1.2,
    lineStyle: "solid",
    representation: "single",
    mode: "single",
    representationOptions: [
      { value: "single", label: "Estilo único", type: "text", source: "source", recommendedMode: "single" },
    ],
    layerType: layer.layer_type,
    projectVersionId: layer.project_version_id,
    featureCount: layer.feature_count,
    status: layer.status,
    sourceFilename: layer.source_filename,
  };
}

function fieldOption(field: LayerAttributes["fields"][number]): RepresentationOption {
  const numeric = field.detected_type === "numeric";
  const range = numeric && field.min_value !== null && field.max_value !== null
    ? ([field.min_value, field.max_value] as [number, number])
    : undefined;
  return {
    value: field.field,
    label: field.field,
    type: numeric ? "number" : "text",
    source: field.origin,
    recommendedMode: field.recommended_mode ?? "single",
    distinctValues: field.distinct_values ?? undefined,
    range,
    unavailableReason: field.unsuitable_reason ?? undefined,
  };
}

export function applyLayerAttributes(
  layer: LayerStyleConfig,
  attributes: LayerAttributes,
): LayerStyleConfig {
  const options = [layer.representationOptions[0], ...attributes.fields.map(fieldOption)];
  const representationExists = options.some((option) => option.value === layer.representation);
  const selectedOption = options.find((option) => option.value === layer.representation);
  const categories = layer.mode === "categorical" && selectedOption?.distinctValues && layer.palette
    ? Object.fromEntries(
        selectedOption.distinctValues.map((value, index) => [
          value,
          layer.palette![index % layer.palette!.length],
        ]),
      )
    : layer.categories;
  return {
    ...layer,
    featureCount: attributes.feature_count,
    representation: representationExists ? layer.representation : "single",
    mode: representationExists ? layer.mode : "single",
    categories: representationExists ? categories : undefined,
    representationOptions: options,
  };
}

export function categoriesFor(option: RepresentationOption): Record<string, string> | undefined {
  if (!option.distinctValues) return undefined;
  return Object.fromEntries(
    option.distinctValues.map((value, index) => [value, categoryPalette[index % categoryPalette.length]]),
  );
}

export function representationModeFor(option: RepresentationOption): RepresentationMode {
  return option.recommendedMode ?? (option.type === "number" ? "sequential" : "categorical");
}
