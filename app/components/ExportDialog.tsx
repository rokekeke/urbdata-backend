"use client";

import { useMemo, useState } from "react";
import type { FeatureCollection } from "geojson";

import type { Basemap } from "../features/catalog/api/listBasemaps";
import { useExportWorkflow, type ExportStage } from "../features/exports/hooks/useExportWorkflow";
import {
  exportFileName,
  exportImageSpec,
  exportRatioPresets,
  type ExportRatio,
  type ExportResolution,
} from "../features/exports/model/exportPresets";
import { renderMapExport } from "../features/exports/model/renderMapExport";
import type { MapDocumentWithWarnings, MapDocument } from "../features/map-documents/api/mapDocuments";
import type { AnalysisRun } from "../features/results/api/listProjectRuns";
import type { LayerStyleConfig } from "../lib/types";

interface ExportDialogProps {
  open: boolean;
  projectId: string;
  projectName: string;
  document: MapDocument;
  layers: LayerStyleConfig[];
  geojsonByLayerId: Record<string, FeatureCollection>;
  basemap: Basemap | null;
  runs: AnalysisRun[];
  integrityWarnings: MapDocumentWithWarnings["integrity_warnings"];
  onClose: () => void;
}

const stageLabels: Record<Exclude<ExportStage, "idle" | "failed">, string> = {
  snapshot: "Congelando a revisão do documento",
  rendering: "Renderizando o mapa em alta resolução",
  uploading: "Arquivando o PNG no projeto",
  verifying: "Confirmando a exportação",
  completed: "Exportação concluída",
};

function downloadBlob(blob: Blob, name: string) {
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = name;
  link.click();
  window.setTimeout(() => URL.revokeObjectURL(url), 1_000);
}

function runLabel(run: AnalysisRun): string {
  const date = new Intl.DateTimeFormat("pt-BR", { dateStyle: "short", timeStyle: "short" }).format(new Date(run.run_at));
  const themes = Array.isArray(run.config.themes) ? run.config.themes.join(", ") : "diagnóstico completo";
  return `${date} · ${themes}`;
}

export default function ExportDialog({
  open,
  projectId,
  projectName,
  document: mapDocument,
  layers,
  geojsonByLayerId,
  basemap,
  runs,
  integrityWarnings,
  onClose,
}: ExportDialogProps) {
  const [ratio, setRatio] = useState<ExportRatio>("screen");
  const [resolution, setResolution] = useState<ExportResolution>("1x");
  const [legend, setLegend] = useState(true);
  const [analysisRunId, setAnalysisRunId] = useState("");
  const workflow = useExportWorkflow(projectId);
  const image = exportImageSpec(ratio, resolution);
  const eligibleRuns = useMemo(
    () => runs.filter((run) => run.status === "completed" && run.project_version_id === mapDocument.project_version_id),
    [mapDocument.project_version_id, runs],
  );
  const missingVisibleLayers = layers.filter(
    (layer) => layer.visible && !geojsonByLayerId[layer.id],
  );
  const basemapUnavailable = mapDocument.config.basemap_id !== "none" && !basemap;
  const basemapNotExportable = basemap?.export_allowed === false;
  const blocked = missingVisibleLayers.length > 0 || basemapUnavailable || basemapNotExportable;

  if (!open) return null;

  async function startExport() {
    try {
      const result = await workflow.start({
        documentId: mapDocument.id,
        expectedRevision: mapDocument.revision,
        legend,
        image,
        analysisRunId: analysisRunId || null,
        render: () => renderMapExport({
          image,
          viewport: mapDocument.config.viewport,
          layers,
          geojsonByLayerId,
          basemap,
          legend,
          projectName,
          documentName: mapDocument.name,
        }),
      });
      downloadBlob(result.png, exportFileName(mapDocument.name));
    } catch {
      // The normalized error and recovery action are rendered by the workflow state.
    }
  }

  async function retryUpload() {
    try {
      const result = await workflow.retry();
      downloadBlob(result.png, exportFileName(mapDocument.name));
    } catch {
      // The workflow keeps the rendered PNG available for another retry.
    }
  }

  function closeDialog() {
    if (workflow.isPending) return;
    workflow.reset();
    onClose();
  }

  return (
    <div className="export-dialog-backdrop" role="presentation" onMouseDown={(event) => event.target === event.currentTarget && closeDialog()}>
      <section className="export-dialog" role="dialog" aria-modal="true" aria-labelledby="export-dialog-title">
        <header className="export-dialog-header">
          <div>
            <span className="eyebrow">Documento salvo · revisão {mapDocument.revision}</span>
            <h2 id="export-dialog-title">Exportar mapa em PNG</h2>
            <p>{mapDocument.name}</p>
          </div>
          <button className="feature-panel-close" type="button" onClick={closeDialog} disabled={workflow.isPending} aria-label="Fechar exportação">×</button>
        </header>

        <div className="export-dialog-body">
          <section className="export-config-section">
            <div className="export-section-heading"><span className="eyebrow">Proporção</span><span>{image.width_px.toLocaleString("pt-BR")} × {image.height_px.toLocaleString("pt-BR")} px</span></div>
            <div className="export-ratio-grid">
              {exportRatioPresets.map((preset) => (
                <button key={preset.id} type="button" className={ratio === preset.id ? "export-ratio-card active" : "export-ratio-card"} onClick={() => setRatio(preset.id)} disabled={workflow.isPending}>
                  <i className={`ratio-shape ${preset.id}`} />
                  <strong>{preset.label}</strong>
                  <span>{preset.description}</span>
                </button>
              ))}
            </div>
          </section>

          <section className="export-config-section export-config-grid">
            <fieldset>
              <legend>Resolução</legend>
              <div className="segmented-control export-resolution-control">
                {(["1x", "2x"] as ExportResolution[]).map((item) => (
                  <button key={item} type="button" className={resolution === item ? "active" : ""} onClick={() => setResolution(item)} disabled={workflow.isPending}>
                    {item === "1x" ? "Padrão" : "Alta · 2×"}
                  </button>
                ))}
              </div>
            </fieldset>
            <label className="export-checkbox">
              <input type="checkbox" checked={legend} onChange={(event) => setLegend(event.target.checked)} disabled={workflow.isPending} />
              <span><strong>Incluir legenda</strong><small>Camadas visíveis e simbologia atual</small></span>
            </label>
          </section>

          <section className="export-config-section">
            <label className="export-run-field" htmlFor="export-analysis-run">
              <span>Diagnóstico de referência <em>opcional</em></span>
              <select id="export-analysis-run" value={analysisRunId} onChange={(event) => setAnalysisRunId(event.target.value)} disabled={workflow.isPending || eligibleRuns.length === 0}>
                <option value="">Sem vínculo com execução</option>
                {eligibleRuns.map((run) => <option key={run.id} value={run.id}>{runLabel(run)}</option>)}
              </select>
              <small>O vínculo registra qual execução de indicadores contextualizou este mapa.</small>
            </label>
          </section>

          {(integrityWarnings.length > 0 || blocked) && (
            <div className={blocked ? "export-readiness error" : "export-readiness warning"} role={blocked ? "alert" : "status"}>
              <strong>{blocked ? "A exportação ainda não pode começar" : "A composição possui referências que exigem atenção"}</strong>
              {missingVisibleLayers.length > 0 && <span>{missingVisibleLayers.length} camada(s) visível(is) ainda não têm geometria carregada.</span>}
              {basemapUnavailable && <span>O estilo do mapa-base salvo não está disponível no catálogo carregado.</span>}
              {basemapNotExportable && <span>O mapa-base selecionado não permite exportação.</span>}
              {!blocked && <span>O PNG refletirá somente o conteúdo que a interface conseguiu representar, sem correções automáticas.</span>}
            </div>
          )}

          {workflow.stage !== "idle" && (
            <div className={`export-progress ${workflow.stage}`} aria-live="polite">
              <div className="export-progress-track">
                {["snapshot", "rendering", "uploading", "verifying"].map((step, index) => {
                  const currentIndex = ["snapshot", "rendering", "uploading", "verifying", "completed"].indexOf(workflow.stage);
                  return <i key={step} className={currentIndex > index || workflow.stage === "completed" ? "done" : currentIndex === index ? "active" : ""} />;
                })}
              </div>
              <strong>{workflow.stage === "failed" ? "A exportação foi interrompida" : stageLabels[workflow.stage as Exclude<ExportStage, "idle" | "failed">]}</strong>
              {workflow.error && <span>{workflow.error.message}</span>}
              {workflow.data?.record.status === "completed" && <span>Registro {workflow.data.record.id.slice(0, 8)} · PNG arquivado e baixado.</span>}
            </div>
          )}
        </div>

        <footer className="export-dialog-footer">
          <div><strong>PNG · renderização MapLibre dedicada</strong><span>O snapshot conserva revisão, viewport, camadas e atribuição.</span></div>
          <div className="export-dialog-actions">
            <button className="text-button" type="button" onClick={closeDialog} disabled={workflow.isPending}>Fechar</button>
            {workflow.stage === "failed" && workflow.canRetryUpload && (
              <button className="secondary-button" type="button" onClick={() => void retryUpload()} disabled={workflow.isPending}>Reenviar PNG</button>
            )}
            {workflow.stage !== "completed" && (
              <button className="primary-button" type="button" onClick={() => void startExport()} disabled={blocked || workflow.isPending}>
                {workflow.isPending ? "Exportando…" : workflow.stage === "failed" ? "Gerar novo export" : "Gerar e arquivar PNG"}
              </button>
            )}
            {workflow.stage === "completed" && workflow.data && (
              <button className="primary-button" type="button" onClick={() => downloadBlob(workflow.data!.png, exportFileName(mapDocument.name))}>Baixar novamente</button>
            )}
          </div>
        </footer>
      </section>
    </div>
  );
}
