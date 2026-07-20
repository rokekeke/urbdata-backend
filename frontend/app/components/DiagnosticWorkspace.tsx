"use client";

import { useEffect, useMemo, useRef, useState } from "react";

import type { CatalogIndicator } from "../features/catalog/api/listCatalogIndicators";
import { useAnalyzeProject } from "../features/diagnostics/hooks/useAnalyzeProject";
import {
  buildDiagnosticThemes,
  selectedBackendThemes,
  type DiagnosticTheme,
} from "../features/diagnostics/model/diagnosticAvailability";
import type { AnalysisRun } from "../features/results/api/listProjectRuns";
import { formatDuration, formatRunDate, runStatusLabel } from "../features/results/model/resultsPresentation";
import type { AppError } from "../lib/errors";
import type { LayerStyleConfig } from "../lib/types";

interface DiagnosticWorkspaceProps {
  projectId: string | null;
  versionLabel: string;
  layers: LayerStyleConfig[];
  catalog: CatalogIndicator[];
  runs: AnalysisRun[];
  isLoading: boolean;
  catalogError: AppError | null;
  onOpenData: () => void;
  onOpenResults: () => void;
}

export default function DiagnosticWorkspace({
  projectId,
  versionLabel,
  layers,
  catalog,
  runs,
  isLoading,
  catalogError,
  onOpenData,
  onOpenResults,
}: DiagnosticWorkspaceProps) {
  const themes = useMemo(() => buildDiagnosticThemes(catalog, layers), [catalog, layers]);
  const [activeThemeId, setActiveThemeId] = useState("territorio");
  const [selectedThemeIds, setSelectedThemeIds] = useState<string[]>([]);
  const initializedSelection = useRef(false);
  const analysis = useAnalyzeProject(projectId);
  const activeTheme = themes.find((theme) => theme.id === activeThemeId) ?? themes[0] ?? null;
  const backendThemes = selectedBackendThemes(themes, selectedThemeIds);
  const availableCount = themes.filter((theme) => theme.status === "available").length;
  const attentionCount = themes.filter((theme) => theme.status === "attention").length;
  const blockedCount = themes.filter((theme) => theme.status === "blocked").length;
  const selectedIndicatorCount = themes
    .filter((theme) => selectedThemeIds.includes(theme.id))
    .reduce((total, theme) => total + theme.indicators.length, 0);
  const latestRun = runs[0] ?? null;

  useEffect(() => {
    if (isLoading || catalog.length === 0) return;
    const runnableIds = themes.filter((theme) => theme.status !== "blocked").map((theme) => theme.id);
    if (!initializedSelection.current) {
      setSelectedThemeIds(runnableIds);
      initializedSelection.current = true;
      return;
    }
    const runnable = new Set(runnableIds);
    setSelectedThemeIds((current) => current.filter((id) => runnable.has(id)));
  }, [catalog.length, isLoading, themes]);

  function toggleTheme(theme: DiagnosticTheme) {
    if (theme.status === "blocked" || analysis.isPending) return;
    setSelectedThemeIds((current) =>
      current.includes(theme.id)
        ? current.filter((id) => id !== theme.id)
        : [...current, theme.id],
    );
    analysis.reset();
  }

  function processDiagnosis() {
    if (!projectId || backendThemes.length === 0 || analysis.isPending) return;
    analysis.mutate(backendThemes);
  }

  return (
    <div className="diagnostic-view">
      <header className="diagnostic-header">
        <div>
          <span className="eyebrow">Preparação e processamento</span>
          <h1>Diagnóstico</h1>
          <p>Escolha os temas que serão processados para {versionLabel} e confira o que ainda falta.</p>
        </div>
        <div className="diagnostic-header-context">
          <span>Motor síncrono do MVP</span>
          <strong>{catalog.length} indicadores publicados</strong>
        </div>
      </header>

      {catalogError && (
        <div className="diagnostic-global-alert" role="alert">
          <strong>Não foi possível consultar o catálogo de diagnósticos.</strong>
          <span>{catalogError.message}</span>
        </div>
      )}

      <section className="diagnostic-summary" aria-label="Disponibilidade dos diagnósticos">
        <article><span>Disponíveis</span><strong>{isLoading ? "—" : availableCount}</strong><small>Prontos para processar</small></article>
        <article><span>Pedem revisão</span><strong>{isLoading ? "—" : attentionCount}</strong><small>Podem ser executados conscientemente</small></article>
        <article><span>Bloqueados</span><strong>{isLoading ? "—" : blockedCount}</strong><small>Clique para ver o requisito ausente</small></article>
        <article><span>Última execução</span><strong>{latestRun ? runStatusLabel(latestRun.status) : "Nenhuma"}</strong><small>{latestRun ? formatRunDate(latestRun.run_at) : "Ainda não processado"}</small></article>
      </section>

      {isLoading && catalog.length === 0 ? (
        <div className="integration-state diagnostic-loading" role="status">Verificando temas, camadas e histórico…</div>
      ) : (
        <div className="diagnostic-layout">
          <aside className="diagnostic-theme-panel panel-surface" aria-label="Temas do diagnóstico">
            <div className="panel-heading">
              <div><span className="eyebrow">Painel de controle</span><h2>Temas</h2></div>
              <span className="panel-count">{selectedThemeIds.length}/{themes.length}</span>
            </div>
            <p className="panel-help">Temas bloqueados continuam acessíveis para explicar o impedimento.</p>

            <div className="diagnostic-theme-list">
              {themes.map((theme) => (
                <article key={theme.id} className={`diagnostic-theme-card ${theme.status} ${activeTheme?.id === theme.id ? "active" : ""}`}>
                  <button className="diagnostic-theme-open" onClick={() => setActiveThemeId(theme.id)}>
                    <span className={`diagnostic-state-mark ${theme.status}`} aria-hidden="true" />
                    <span>
                      <strong>{theme.label}</strong>
                      <small>{theme.indicators.length} indicadores · {theme.statusLabel}</small>
                    </span>
                    <span aria-hidden="true">›</span>
                  </button>
                  {theme.status === "blocked" ? (
                    <span className="diagnostic-blocked-label">Requisito ausente</span>
                  ) : (
                    <label className="diagnostic-theme-check">
                      <input
                        type="checkbox"
                        checked={selectedThemeIds.includes(theme.id)}
                        disabled={analysis.isPending}
                        onChange={() => toggleTheme(theme)}
                      />
                      <span>Incluir</span>
                    </label>
                  )}
                </article>
              ))}
            </div>
          </aside>

          <main className="diagnostic-main">
            {activeTheme && (
              <DiagnosticThemeDetail
                theme={activeTheme}
                selected={selectedThemeIds.includes(activeTheme.id)}
                processing={analysis.isPending}
                onToggle={() => toggleTheme(activeTheme)}
                onOpenData={onOpenData}
              />
            )}

            <section className="diagnostic-run-panel panel-surface" aria-label="Processar diagnóstico">
              <div className="diagnostic-run-copy">
                <span className="eyebrow">Execução</span>
                <h2>{analysis.isPending ? "Processando diagnóstico…" : `${selectedThemeIds.length} temas selecionados`}</h2>
                <p>{analysis.isPending
                  ? "O backend está calculando e registrando uma nova execução. Não feche esta tela."
                  : `${selectedIndicatorCount} indicadores serão calculados na mesma execução rastreável.`}</p>
              </div>
              <button
                className="primary-button diagnostic-run-button"
                disabled={!projectId || backendThemes.length === 0 || analysis.isPending || Boolean(catalogError)}
                onClick={processDiagnosis}
              >
                {analysis.isPending ? "Processando…" : "Processar diagnóstico"}
              </button>

              {analysis.isPending && <div className="diagnostic-progress" role="progressbar" aria-label="Diagnóstico em processamento"><i /></div>}

              {analysis.isError && (
                <div className="diagnostic-run-feedback error" role="alert">
                  <div>
                    <strong>O diagnóstico não foi concluído.</strong>
                    <span>{analysis.error.message}</span>
                    {Boolean(analysis.error.context.layer_type) && <small>Camada indicada pelo backend: {String(analysis.error.context.layer_type)}</small>}
                  </div>
                  {analysis.error.canRetry && <button className="text-button" onClick={processDiagnosis}>Tentar novamente</button>}
                </div>
              )}

              {analysis.isSuccess && (
                <div className="diagnostic-run-feedback success" role="status">
                  <div>
                    <strong>Diagnóstico concluído.</strong>
                    <span>{analysis.data.results.length} indicadores foram registrados na execução {analysis.data.analysis_run_id.slice(0, 8)}.</span>
                  </div>
                  <button className="secondary-button" onClick={onOpenResults}>Explorar resultados</button>
                </div>
              )}

              {!analysis.isPending && !analysis.isSuccess && !analysis.isError && latestRun && (
                <div className={`diagnostic-last-run ${latestRun.status}`}>
                  <span>Última execução: {runStatusLabel(latestRun.status)}</span>
                  <small>{formatRunDate(latestRun.run_at)} · {formatDuration(latestRun.duration_ms)}</small>
                </div>
              )}
            </section>
          </main>
        </div>
      )}
    </div>
  );
}

function DiagnosticThemeDetail({
  theme,
  selected,
  processing,
  onToggle,
  onOpenData,
}: {
  theme: DiagnosticTheme;
  selected: boolean;
  processing: boolean;
  onToggle: () => void;
  onOpenData: () => void;
}) {
  return (
    <article className="diagnostic-detail panel-surface">
      <header className="diagnostic-detail-header">
        <div>
          <span className="eyebrow">Tema selecionado</span>
          <h2>{theme.label}</h2>
          <p>{theme.description}</p>
        </div>
        <span className={`diagnostic-status-badge ${theme.status}`}>{theme.statusLabel}</span>
      </header>

      <div className={`diagnostic-status-message ${theme.status}`}>
        <strong>{theme.status === "blocked"
          ? "Este tema não pode ser processado ainda."
          : theme.status === "attention"
            ? "O tema pode ser processado, mas a base pede revisão."
            : "Todos os requisitos estruturais estão presentes."}</strong>
        <span>{theme.blockerSummary ?? theme.nextAction ?? theme.outcome}</span>
      </div>

      <div className="diagnostic-detail-grid">
        <section>
          <div className="diagnostic-section-heading">
            <div><span className="eyebrow">Entradas</span><h3>Bases necessárias</h3></div>
            <span>{theme.requirements.length}</span>
          </div>
          <div className="diagnostic-requirement-list">
            {theme.requirements.map((requirement) => (
              <div key={requirement.layerType} className={requirement.state}>
                <span className={`diagnostic-state-mark ${requirement.state}`} aria-hidden="true" />
                <span><strong>{requirement.label}</strong><small>{requirement.detail}</small></span>
              </div>
            ))}
          </div>
          {theme.status === "blocked" && (
            <button className="secondary-button diagnostic-data-action" onClick={onOpenData}>Abrir Dados e corrigir</button>
          )}
        </section>

        <section>
          <div className="diagnostic-section-heading">
            <div><span className="eyebrow">Saída</span><h3>Indicadores previstos</h3></div>
            <span>{theme.indicators.length}</span>
          </div>
          <p className="diagnostic-outcome">{theme.outcome}</p>
          <div className="diagnostic-indicator-list">
            {theme.indicators.map((indicator) => (
              <details key={indicator.code}>
                <summary>
                  <span><strong>{indicator.display_name}</strong><small>{indicator.granularity === "por_feicao" ? "Por elemento territorial" : "Síntese do projeto"}</small></span>
                  <span>+</span>
                </summary>
                <p>{indicator.description}</p>
              </details>
            ))}
          </div>
        </section>
      </div>

      {theme.status !== "blocked" && (
        <footer className="diagnostic-detail-footer">
          <span>{selected ? "Tema incluído na próxima execução" : "Tema fora da próxima execução"}</span>
          <button className={selected ? "secondary-button" : "primary-button"} disabled={processing} onClick={onToggle}>
            {selected ? "Remover da execução" : "Incluir na execução"}
          </button>
        </footer>
      )}
    </article>
  );
}
