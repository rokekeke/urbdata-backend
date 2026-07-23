import type { components } from "../../../lib/api/schema";

export type ExportRatio = components["schemas"]["ImageRatio"];
export type ExportResolution = components["schemas"]["ImageResolution"];
export type ExportImageSpec = components["schemas"]["ExportImageSpecIn"];

export interface ExportRatioPreset {
  id: ExportRatio;
  label: string;
  description: string;
  baseWidth: number;
  baseHeight: number;
}

export const exportRatioPresets: ExportRatioPreset[] = [
  { id: "screen", label: "Tela", description: "Apresentações e relatórios digitais", baseWidth: 1440, baseHeight: 900 },
  { id: "four_by_three", label: "4:3", description: "Pranchas compactas e apresentações", baseWidth: 1200, baseHeight: 900 },
  { id: "sixteen_by_nine", label: "16:9", description: "Slides e visualização panorâmica", baseWidth: 1600, baseHeight: 900 },
];

export function exportImageSpec(
  ratioId: ExportRatio,
  resolutionId: ExportResolution,
): ExportImageSpec {
  const preset = exportRatioPresets.find((item) => item.id === ratioId) ?? exportRatioPresets[0];
  const scale = resolutionId === "2x" ? 2 : 1;
  return {
    ratio_id: ratioId,
    resolution_id: resolutionId,
    width_px: preset.baseWidth * scale,
    height_px: preset.baseHeight * scale,
  };
}

export function exportFileName(documentName: string): string {
  const normalized = documentName
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-|-$/g, "")
    .slice(0, 64);
  return `${normalized || "mapa-urbdata"}.png`;
}
