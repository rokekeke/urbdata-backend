import type { components } from "./api/schema";

export type WorkspaceSection =
  | "visao-geral"
  | "dados"
  | "diagnostico"
  | "resultados"
  | "documentacao";

export type GeometryKind = "polygon" | "line" | "point";
export type RepresentationMode = components["schemas"]["RepresentationMode"];
export type LineStyle = "solid" | "dashed" | "dotted";
export type BasemapId = string;
export type MapViewport = components["schemas"]["Viewport"];

export interface RepresentationOption {
  value: string;
  label: string;
  type: "text" | "number";
  unit?: string;
  source: "source" | "mapped" | "indicator";
  recommendedMode?: RepresentationMode;
  distinctValues?: string[];
  range?: [number, number];
  unavailableReason?: string;
}

export interface LayerStyleConfig {
  id: string;
  name: string;
  shortName: string;
  geometry: GeometryKind;
  visible: boolean;
  opacity: number;
  color: string;
  secondaryColor: string;
  palette?: string[];
  strokeColor: string;
  strokeWidth: number;
  lineStyle: LineStyle;
  representation: string;
  mode: RepresentationMode;
  representationOptions: RepresentationOption[];
  categories?: Record<string, string>;
  range?: [number, number];
  layerType?: components["schemas"]["LayerType"];
  projectVersionId?: string;
  featureCount?: number;
  status?: components["schemas"]["LayerStatus"];
  sourceFilename?: string | null;
}
