import type { FeatureCollection } from "geojson";
import type { LayerStyleConfig } from "./types";

export const initialLayers: LayerStyleConfig[] = [
  {
    id: "territorio",
    name: "Classificação territorial",
    shortName: "Território",
    geometry: "polygon",
    visible: true,
    opacity: 0.76,
    color: "#d2a86e",
    secondaryColor: "#426f78",
    strokeColor: "#384541",
    strokeWidth: 1.2,
    lineStyle: "solid",
    representation: "macroarea",
    mode: "categorical",
    representationOptions: [
      { value: "macroarea", label: "Macroárea", type: "text", source: "mapped" },
      { value: "parcelavel", label: "Condição de parcelamento", type: "text", source: "mapped" },
      { value: "area_m2", label: "Área da feição", type: "number", unit: "m²", source: "indicator" },
    ],
    categories: {
      Lote: "#d6b17b",
      "Sistema viário": "#889296",
      AVL: "#6d9375",
      APP: "#3d746a",
      ACI: "#9c7f6a",
    },
    range: [1800, 12600],
  },
  {
    id: "quadras",
    name: "Quadras derivadas",
    shortName: "Quadras",
    geometry: "polygon",
    visible: true,
    opacity: 0.06,
    color: "#ffffff",
    secondaryColor: "#315d68",
    strokeColor: "#315d68",
    strokeWidth: 2,
    lineStyle: "solid",
    representation: "single",
    mode: "single",
    representationOptions: [
      { value: "single", label: "Estilo único", type: "text", source: "source" },
      { value: "compactness", label: "Compacidade", type: "number", source: "indicator" },
      { value: "area_m2", label: "Área da quadra", type: "number", unit: "m²", source: "indicator" },
    ],
    range: [0.38, 0.87],
  },
  {
    id: "sistema_viario",
    name: "Sistema viário",
    shortName: "Eixos viários",
    geometry: "line",
    visible: true,
    opacity: 0.92,
    color: "#9b5d46",
    secondaryColor: "#d1906f",
    strokeColor: "#9b5d46",
    strokeWidth: 3,
    lineStyle: "solid",
    representation: "road_status",
    mode: "categorical",
    representationOptions: [
      { value: "road_status", label: "Status da via", type: "text", source: "mapped" },
      { value: "connectivity", label: "Conectividade", type: "number", source: "indicator" },
    ],
    categories: { existente: "#716e68", proposta: "#b86848" },
    range: [1, 5],
  },
  {
    id: "areas_verdes",
    name: "Áreas verdes e APP",
    shortName: "Áreas verdes",
    geometry: "polygon",
    visible: true,
    opacity: 0.72,
    color: "#557d63",
    secondaryColor: "#a6c0a0",
    strokeColor: "#355847",
    strokeWidth: 1.4,
    lineStyle: "solid",
    representation: "green_type",
    mode: "categorical",
    representationOptions: [
      { value: "green_type", label: "Tipo de área verde", type: "text", source: "mapped" },
      { value: "area_m2", label: "Área", type: "number", unit: "m²", source: "indicator" },
    ],
    categories: { AVL: "#71916c", APP: "#356b5a" },
    range: [940, 5600],
  },
];

export const sampleGeojson: Record<string, FeatureCollection> = {
  territorio: {
    type: "FeatureCollection",
    features: [
      {
        type: "Feature",
        id: "8b65a-01",
        properties: { macroarea: "Lote", parcelavel: "Parcelável", area_m2: 12600 },
        geometry: { type: "Polygon", coordinates: [[[-48.509, -27.608], [-48.503, -27.606], [-48.501, -27.611], [-48.507, -27.613], [-48.509, -27.608]]] },
      },
      {
        type: "Feature",
        id: "8b65a-02",
        properties: { macroarea: "Lote", parcelavel: "Parcelável", area_m2: 7800 },
        geometry: { type: "Polygon", coordinates: [[[-48.503, -27.606], [-48.497, -27.604], [-48.496, -27.61], [-48.501, -27.611], [-48.503, -27.606]]] },
      },
      {
        type: "Feature",
        id: "8b65a-03",
        properties: { macroarea: "ACI", parcelavel: "Parcelável", area_m2: 4200 },
        geometry: { type: "Polygon", coordinates: [[[-48.507, -27.613], [-48.501, -27.611], [-48.5, -27.617], [-48.506, -27.619], [-48.507, -27.613]]] },
      },
      {
        type: "Feature",
        id: "8b65a-04",
        properties: { macroarea: "Sistema viário", parcelavel: "Não parcelável", area_m2: 1800 },
        geometry: { type: "Polygon", coordinates: [[[-48.501, -27.611], [-48.496, -27.61], [-48.494, -27.616], [-48.5, -27.617], [-48.501, -27.611]]] },
      },
    ],
  },
  quadras: {
    type: "FeatureCollection",
    features: [
      {
        type: "Feature",
        id: "q-01",
        properties: { compactness: 0.87, area_m2: 20400 },
        geometry: { type: "Polygon", coordinates: [[[-48.5093, -27.6078], [-48.4967, -27.6037], [-48.4956, -27.6102], [-48.5072, -27.6134], [-48.5093, -27.6078]]] },
      },
      {
        type: "Feature",
        id: "q-02",
        properties: { compactness: 0.62, area_m2: 11200 },
        geometry: { type: "Polygon", coordinates: [[[-48.5073, -27.6132], [-48.4957, -27.6099], [-48.4937, -27.6161], [-48.5061, -27.6193], [-48.5073, -27.6132]]] },
      },
    ],
  },
  sistema_viario: {
    type: "FeatureCollection",
    features: [
      {
        type: "Feature",
        id: "v-01",
        properties: { road_status: "existente", connectivity: 5 },
        geometry: { type: "LineString", coordinates: [[-48.512, -27.609], [-48.506, -27.611], [-48.5, -27.613], [-48.492, -27.615]] },
      },
      {
        type: "Feature",
        id: "v-02",
        properties: { road_status: "proposta", connectivity: 3 },
        geometry: { type: "LineString", coordinates: [[-48.505, -27.602], [-48.503, -27.608], [-48.501, -27.614], [-48.499, -27.621]] },
      },
    ],
  },
  areas_verdes: {
    type: "FeatureCollection",
    features: [
      {
        type: "Feature",
        id: "avl-01",
        properties: { green_type: "AVL", area_m2: 5600 },
        geometry: { type: "Polygon", coordinates: [[[-48.499, -27.6045], [-48.495, -27.6038], [-48.494, -27.6075], [-48.498, -27.6083], [-48.499, -27.6045]]] },
      },
      {
        type: "Feature",
        id: "app-01",
        properties: { green_type: "APP", area_m2: 3140 },
        geometry: { type: "Polygon", coordinates: [[[-48.51, -27.614], [-48.506, -27.613], [-48.505, -27.618], [-48.509, -27.619], [-48.51, -27.614]]] },
      },
    ],
  },
};

export const palettes = [
  { name: "Território", colors: ["#d6b17b", "#889296", "#6d9375", "#3d746a", "#9c7f6a"] },
  { name: "Mineral", colors: ["#e3d7bd", "#9db1ad", "#557681", "#2b4c57", "#152f38"] },
  { name: "Quente", colors: ["#f1d9b7", "#d9a875", "#b96f50", "#874847", "#4c3138"] },
];

