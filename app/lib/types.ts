export type WorkspaceSection =
  | "visao-geral"
  | "dados"
  | "diagnostico"
  | "resultados"
  | "documentacao";

export type GeometryKind = "polygon" | "line" | "point";
export type RepresentationMode = "single" | "categorical" | "sequential";
export type LineStyle = "solid" | "dashed" | "dotted";
export type BasemapId = "none" | "osm";

export interface RepresentationOption {
  value: string;
  label: string;
  type: "text" | "number";
  unit?: string;
  source: "source" | "mapped" | "indicator";
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
  strokeColor: string;
  strokeWidth: number;
  lineStyle: LineStyle;
  representation: string;
  mode: RepresentationMode;
  representationOptions: RepresentationOption[];
  categories?: Record<string, string>;
  range?: [number, number];
}

