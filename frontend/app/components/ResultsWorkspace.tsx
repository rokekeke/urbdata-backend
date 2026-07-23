"use client";

import { useMemo, useState } from "react";

import type { CatalogIndicator } from "../features/catalog/api/listCatalogIndicators";
import type { AnalysisRun } from "../features/results/api/listProjectRuns";
import type { IndicatorResult } from "../features/results/api/listProjectResults";
import {
  buildCategoryShares,
  buildCompoundTable,
  buildDistributionEntries,
  buildResultIndicatorViews,
  buildResultOverlay,
  findGreenAreaPair,
  formatDuration,
  formatRunDate,
  formatScalarValue,
  numericDistributionSummary,
  runStatusLabel,
  runThemes,
  selectedFeatureResult,
  type ResultIndicatorView,
} from "../features/results/model/resultsPresentation";
import type { AppError } from "../lib/errors";
import type { LayerStyleConfig } from "../lib/types";
import type { SelectedFeature } from "../store/useWorkspaceStore";
import MapCanvas from "./MapCanvas";

interface ResultsWorkspaceProps {
  versionLabel: string;
  layers: LayerStyleConfig[];
  catalog: CatalogIndicator[];
  results: IndicatorResult[];
  runs: AnalysisRun[];
  selectedFeature: SelectedFeature | null;
  catalogLoading: boolean;
  resultsLoading: boolean;
  runsLoading: boolean;
  catalogError: AppError | null;
  resultsError: AppError | null;
  runsError: AppError | null;
  onClearFeatureSelection: () => void;
  onRefresh: () => void;
  onOpenDiagnosis: () => void;
}

export default function ResultsWorkspace({
  versionLabel,
  layers,
  catalog,
  results,
  runs,
  selectedFeature,
  catalogLoading,
  resultsLoading,
  runsLoading,
  catalogError,
  resultsError,
  runsError,
  onClearFeatureSelection,
  onRefresh,
  onOpenDiagnosis,
}: ResultsWorkspaceProps) {
  const [selectedRunId, setSelectedRunId] = useState<string | null>(null);
  const [selectedTheme, setSelectedTheme] = useState("all");
  const [selectedIndicatorCode, setSelectedIndicatorCode] = useState<string | null>(null);
  const views = useMemo(
    () => buildResultIndicatorViews(catalog, results),
    [catalog, results],
  );
  // Métricas internas (ex.: quadras.face_length_score) continuam no
  // catálogo e alimentam o resumo de avisos, mas não viram opção de
  // navegação - nota Obsidian 88/97.
  const selectableViews = useMemo(() => views.filter((view) => !view.internal), [views]);
  const latestCompletedRun = runs.find((run) => run.status === "completed") ?? null;
  const selectedRun = runs.find((run) => run.id === selectedRunId)
    ?? latestCompletedRun
    ?? runs[0]
    ?? null;
  const isLatestCompleted = Boolean(selectedRun && selectedRun.id === latestCompletedRun?.id);
  const filteredViews = selectedTheme === "all"
    ? selectableViews
    : selectableViews.filter((view) => view.theme === selectedTheme);
  const selectedView = filteredViews.find((view) => view.code === selectedIndicatorCode)
    ?? filteredViews[0]
    ?? null;
  const themes = Array.from(new Set(selectableViews.map((view) => view.theme)));
  const warningCount = results.reduce((total, result) => total + result.warnings.length, 0);
  // A partir de `views` (não `selectableViews`): o aviso de um indicador
  // interno (ex.: block_face_out_of_compliance em quadras.face_length_score)
  // precisa continuar visível mesmo que o indicador não seja mais
  // selecionável - nota Obsidian 88/97.
  const allWarnings = useMemo(
    () => views.flatMap((view) => view.warnings.map((warning) => ({ view, warning }))),
    [views],
  );
  const isLoading = catalogLoading || resultsLoading || runsLoading;

  return (
    <div className="results-view">
      <header className="results-header">
        <div>
          <span className="eyebrow">Síntese rastreável</span>
          <h1>Resultados</h1>
          <p>Explore os indicadores calculados para {versionLabel}, sem interpretação qualitativa automática.</p>
        </div>
        <div className="results-header-actions">
          <span className="results-contract-note">Resultados da execução concluída mais recente</span>
          <button className="secondary-button" onClick={onRefresh}>Atualizar resultados</button>
        </div>
      </header>

      {(runsError || catalogError) && (
        <div className="results-local-alert warning" role="alert">
          <strong>Parte do contexto não pôde ser atualizada.</strong>
          <span>{runsError?.message ?? catalogError?.message}</span>
        </div>
      )}

      <section className="results-summary" aria-label="Resumo dos resultados">
        <article><span>Indicadores calculados</span><strong>{resultsLoading ? "—" : selectableViews.length}</strong><small>{themes.length} temas com resultado</small></article>
        <article><span>Execução de referência</span><strong>{latestCompletedRun ? formatRunDate(latestCompletedRun.run_at) : "Não disponível"}</strong><small>{latestCompletedRun ? formatDuration(latestCompletedRun.duration_ms) : "Nenhuma execução concluída"}</small></article>
        <article><span>Avisos do cálculo</span><strong>{resultsLoading ? "—" : warningCount}</strong><small>{warningCount ? "Ver lista em Avisos" : "Nenhum aviso retornado"}</small></article>
      </section>

      <div className="results-layout">
        <aside className="results-sidebar panel-surface" aria-label="Navegação dos resultados">
          <div className="results-sidebar-section">
            <div className="panel-heading">
              <div><span className="eyebrow">Histórico</span><h2>Execuções</h2></div>
              <span className="panel-count">{runs.length}</span>
            </div>
            {runsLoading ? (
              <p className="results-sidebar-state">Consultando execuções…</p>
            ) : runs.length === 0 ? (
              <div className="results-sidebar-state empty">
                <span>Nenhuma execução registrada.</span>
                <button className="text-button" onClick={onOpenDiagnosis}>Abrir Diagnóstico</button>
              </div>
            ) : (
              <div className="run-list">
                {runs.map((run) => (
                  <button
                    key={run.id}
                    className={selectedRun?.id === run.id ? "run-item active" : "run-item"}
                    onClick={() => setSelectedRunId(run.id)}
                  >
                    <span className={`run-status-dot ${run.status}`} />
                    <span>
                      <strong>{formatRunDate(run.run_at)}</strong>
                      <small>{runStatusLabel(run.status)} · {formatDuration(run.duration_ms)}</small>
                    </span>
                    {run.id === latestCompletedRun?.id && <em>Atual</em>}
                  </button>
                ))}
              </div>
            )}
          </div>

          <div className="results-sidebar-section">
            <div className="panel-heading">
              <div><span className="eyebrow">Leitura</span><h2>Temas</h2></div>
            </div>
            <div className="result-theme-list">
              <button className={selectedTheme === "all" ? "active" : ""} onClick={() => setSelectedTheme("all")}>
                <span>Todos os temas</span><b>{selectableViews.length}</b>
              </button>
              {themes.map((theme) => {
                const label = selectableViews.find((view) => view.theme === theme)?.themeLabel ?? theme;
                return (
                  <button key={theme} className={selectedTheme === theme ? "active" : ""} onClick={() => setSelectedTheme(theme)}>
                    <span>{label}</span><b>{selectableViews.filter((view) => view.theme === theme).length}</b>
                  </button>
                );
              })}
            </div>
          </div>

          <div className="results-sidebar-section">
            <div className="panel-heading">
              <div><span className="eyebrow">Qualidade</span><h2>Avisos</h2></div>
              <span className="panel-count">{allWarnings.length}</span>
            </div>
            {allWarnings.length === 0 ? (
              <p className="results-sidebar-state">Nenhum aviso retornado nesta execução.</p>
            ) : (
              <div className="result-warning-summary-list">
                {allWarnings.map(({ view, warning }, index) => {
                  const isSelectable = selectableViews.some((candidate) => candidate.code === view.code);
                  return (
                    <button
                      key={`${view.code}-${warning.code}-${index}`}
                      disabled={!isSelectable}
                      title={isSelectable ? `Ver em ${view.displayName}` : view.displayName}
                      onClick={() => {
                        setSelectedTheme(view.theme);
                        setSelectedIndicatorCode(view.code);
                      }}
                    >
                      <span className={`result-warning-dot ${warning.severity}`} />
                      <span>
                        <strong>{warning.message}</strong>
                        <small>{view.displayName}</small>
                      </span>
                    </button>
                  );
                })}
              </div>
            )}
          </div>
        </aside>

        <main className="results-main">
          {isLoading && views.length === 0 ? (
            <div className="integration-state" role="status">Organizando resultados e histórico…</div>
          ) : catalogError && views.length === 0 ? (
            <div className="integration-state error" role="alert">
              <strong>Não foi possível organizar o catálogo de indicadores.</strong>
              <span>{catalogError.message}</span>
              <button className="secondary-button" onClick={onRefresh}>Tentar novamente</button>
            </div>
          ) : resultsError ? (
            <div className="integration-state error" role="alert">
              <strong>Não foi possível carregar os resultados.</strong>
              <span>{resultsError.message}</span>
              <button className="secondary-button" onClick={onRefresh}>Tentar novamente</button>
            </div>
          ) : selectedRun && !isLatestCompleted ? (
            <HistoricalRun run={selectedRun} latestCompletedRun={latestCompletedRun} />
          ) : views.length === 0 ? (
            <div className="integration-state empty results-empty-state">
              <strong>A versão ativa ainda não possui resultados concluídos.</strong>
              <span>Execute um diagnóstico para gerar indicadores rastreáveis.</span>
              <button className="secondary-button" onClick={onOpenDiagnosis}>Abrir Diagnóstico</button>
            </div>
          ) : selectedView ? (
            <ResultExplorer
              view={selectedView}
              views={filteredViews}
              layers={layers}
              selectedFeature={selectedFeature}
              onSelectIndicator={setSelectedIndicatorCode}
              onClearFeatureSelection={onClearFeatureSelection}
            />
          ) : null}
        </main>
      </div>
    </div>
  );
}

function ResultExplorer({
  view,
  views,
  layers,
  selectedFeature,
  onSelectIndicator,
  onClearFeatureSelection,
}: {
  view: ResultIndicatorView;
  views: ResultIndicatorView[];
  layers: LayerStyleConfig[];
  selectedFeature: SelectedFeature | null;
  onSelectIndicator: (code: string) => void;
  onClearFeatureSelection: () => void;
}) {
  const distribution = useMemo(() => buildDistributionEntries(view), [view]);
  const summary = useMemo(() => numericDistributionSummary(distribution), [distribution]);
  const greenAreaPair = useMemo(() => findGreenAreaPair(view, views), [view, views]);
  const categoryShares = useMemo(
    () => (view.valueShape === "category_breakdown" ? buildCategoryShares(view) : []),
    [view],
  );
  const compoundTable = useMemo(
    () => (view.valueShape === "feature_compound" ? buildCompoundTable(view) : null),
    [view],
  );
  const overlay = useMemo(() => buildResultOverlay(view, layers), [layers, view]);
  const selectedValue = useMemo(
    () => selectedFeatureResult(view, selectedFeature),
    [selectedFeature, view],
  );
  const maxMagnitude = Math.max(0, ...distribution.map((entry) => Math.abs(entry.numericValue ?? 0)));
  const targetLayer = overlay ? layers.find((layer) => layer.id === overlay.layerId) : null;
  const coverageTotal = targetLayer?.featureCount ?? null;
  const coverageCount = view.granularity === "por_feicao" ? distribution.length : view.contributingFeatureIds.length;

  return (
    <article className="result-explorer">
      <div className="result-selector-row">
        <label>
          <span>Indicador</span>
          <select value={view.code} onChange={(event) => onSelectIndicator(event.target.value)}>
            {views.map((item) => <option key={item.code} value={item.code}>{item.displayName}</option>)}
          </select>
        </label>
        <span className="result-granularity">{view.granularity === "por_feicao" ? "Por feição" : "Síntese do projeto"}</span>
      </div>

      <header className="result-detail-header">
        <div>
          <span className="eyebrow">{view.themeLabel}</span>
          <h2>{view.displayName}</h2>
          <p>{view.description}</p>
        </div>
        <div className={view.formattedValue === "Sem dado" ? "result-primary-value empty" : "result-primary-value"}>
          <span>Resultado</span>
          <strong>{view.formattedValue}</strong>
        </div>
      </header>

      {greenAreaPair && (
        <section className="result-green-area-pair" aria-label="Comparação AVL e AVL+APP">
          <div><span>AVL</span><strong>{formatScalarValue(greenAreaPair.avlOnlyValue, view.unit)}</strong></div>
          <div><span>AVL+APP</span><strong>{formatScalarValue(greenAreaPair.withAppValue, view.unit)}</strong></div>
          <div className="result-green-area-delta"><span>Ganho com a APP</span><strong>+{greenAreaPair.deltaFormatted}</strong></div>
        </section>
      )}

      <div className="result-map-and-context">
        <section className="result-map-card" aria-label="Contexto territorial do indicador">
          <div className="result-map-heading">
            <div><span className="eyebrow">Leitura territorial</span><strong>{overlay ? `Distribuição em ${targetLayer?.shortName ?? "camada"}` : "Mapa de contexto"}</strong></div>
            {selectedFeature && <button className="selection-chip" onClick={onClearFeatureSelection}>Limpar seleção ×</button>}
          </div>
          <div className="result-map-frame">
            <MapCanvas resultOverlay={overlay} />
            {overlay?.kind === "numeric" ? (
              <div className="result-map-scale">
                <span>{formatScalarValue(overlay.min, view.unit)}</span>
                <i />
                <span>{formatScalarValue(overlay.max, view.unit)}</span>
              </div>
            ) : overlay?.kind === "categorical" ? (
              <div className="result-map-categories">
                {overlay.categories.map((category) => (
                  <span key={category.key} className="result-map-category-chip">
                    <i style={{ background: category.color }} />
                    {category.label}
                  </span>
                ))}
              </div>
            ) : (
              <div className="result-map-note">
                {view.granularity === "por_feicao"
                  ? "Este resultado não possui valores numéricos simples ou uma camada compatível para representação temática."
                  : "Indicador consolidado do projeto; o mapa permanece como referência territorial."}
              </div>
            )}
          </div>
        </section>

        <aside className="result-context-card">
          <section>
            <span className="eyebrow">Cobertura</span>
            <strong>{coverageCount.toLocaleString("pt-BR")} {view.granularity === "por_feicao" ? "registros" : "feições contribuintes"}</strong>
            <small>{coverageTotal ? `de ${coverageTotal.toLocaleString("pt-BR")} elementos da camada` : "Conforme rastreabilidade da execução"}</small>
          </section>
          {selectedFeature && view.granularity === "por_feicao" && (
            <section className={`selected-result-value ${selectedValue?.status ?? "no_data"}`}>
              <span className="eyebrow">Feição selecionada</span>
              <strong>{selectedValue?.formattedValue ?? "Sem correspondência"}</strong>
              <small>ID {selectedFeature.featureId.slice(0, 12)}</small>
            </section>
          )}
          <section className="result-trace-grid">
            <div><span>Fórmula</span><strong>{view.formulaVersion}</strong></div>
            <div><span>CRS métrico</span><strong>{view.metricCrs ?? "Não aplicável"}</strong></div>
            <div><span>Fontes</span><strong>{view.sourceLayers.join(", ") || "Não informadas"}</strong></div>
            <div><span>Unidade</span><strong>{view.unitLabel || "Adimensional"}</strong></div>
          </section>
        </aside>
      </div>

      <div className="result-support-grid">
        {view.valueShape === "category_breakdown" ? (
          <section className="result-distribution panel-surface">
            <div className="result-section-heading">
              <div><span className="eyebrow">Composição</span><h3>Participação por categoria</h3></div>
              {categoryShares.length > 0 && <span>{categoryShares.length} categorias</span>}
            </div>
            {categoryShares.length ? (
              <div className="category-share-list">
                {categoryShares.map((entry) => (
                  <div className="category-share-row" key={entry.key}>
                    <span className="category-share-label" title={entry.key}>
                      <i className="category-share-chip" style={{ background: entry.color }} />
                      {entry.label}
                    </span>
                    <i><b style={{ width: `${Math.max(2, entry.share * 100)}%`, background: entry.color }} /></i>
                    <span className="category-share-numbers">
                      <strong>{entry.formattedShare}</strong>
                      {view.unit !== "ratio" && <small>{entry.formattedValue}</small>}
                    </span>
                  </div>
                ))}
              </div>
            ) : (
              <p className="result-section-empty">Nenhuma categoria com valor calculado nesta execução.</p>
            )}
          </section>
        ) : view.valueShape === "categorical_label" ? (
          <section className="result-distribution panel-surface">
            <div className="result-section-heading">
              <div><span className="eyebrow">Classificação</span><h3>Categoria resultante</h3></div>
            </div>
            <div className={view.rawValue ? "categorical-label-display" : "categorical-label-display empty"}>
              <strong>{view.formattedValue}</strong>
              <small>{view.rawValue
                ? "Categoria com maior área classificada no projeto."
                : "Empate entre categorias ou universo sem classificação - consulte os avisos do cálculo."}</small>
            </div>
          </section>
        ) : view.valueShape === "feature_compound" && compoundTable ? (
          <section className="result-distribution panel-surface">
            <div className="result-section-heading">
              <div><span className="eyebrow">Detalhamento</span><h3>Valores por {view.featureKey === "quadra_id" ? "quadra" : "feição"}</h3></div>
              <span>{compoundTable.rows.length} registros</span>
            </div>
            <div className="compound-table-scroll">
              <table className="compound-table">
                <thead>
                  <tr>
                    <th>{view.featureKey === "quadra_id" ? "Quadra" : "Feição"}</th>
                    {compoundTable.columns.map((column) => <th key={column.key}>{column.label}</th>)}
                  </tr>
                </thead>
                <tbody>
                  {compoundTable.rows.map((row) => (
                    <tr key={row.key}>
                      <th title={row.key}>{view.featureKey === "quadra_id" ? row.key : row.key.slice(0, 8)}</th>
                      {row.cells.map((cell, index) => <td key={compoundTable.columns[index].key}>{cell}</td>)}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>
        ) : (
          <section className="result-distribution panel-surface">
            <div className="result-section-heading">
              <div><span className="eyebrow">Distribuição</span><h3>{distribution.length ? "Valores detalhados" : "Valor consolidado"}</h3></div>
              {summary && <span>{summary.count} valores numéricos</span>}
            </div>
            {summary && (
              <div className="distribution-summary">
                <span><small>Mínimo</small><strong>{formatScalarValue(summary.min, view.unit)}</strong></span>
                <span><small>Média</small><strong>{formatScalarValue(summary.mean, view.unit)}</strong></span>
                <span><small>Máximo</small><strong>{formatScalarValue(summary.max, view.unit)}</strong></span>
              </div>
            )}
            {distribution.length ? (
              <div className="distribution-list">
                {distribution.slice(0, 12).map((entry) => (
                  <div className="distribution-row" key={entry.key}>
                    <span title={entry.key}>{friendlyKey(entry.key)}</span>
                    <i><b style={{ width: `${maxMagnitude ? Math.max(2, Math.abs(entry.numericValue ?? 0) / maxMagnitude * 100) : 0}%` }} /></i>
                    <strong>{entry.formattedValue}</strong>
                  </div>
                ))}
                {distribution.length > 12 && <p className="distribution-more">Mais {distribution.length - 12} registros disponíveis no resultado.</p>}
              </div>
            ) : (
              <p className="result-section-empty">Este indicador retorna um único valor para o projeto.</p>
            )}
          </section>
        )}

        <section className="result-warnings panel-surface">
          <div className="result-section-heading">
            <div><span className="eyebrow">Qualidade e método</span><h3>Avisos do cálculo</h3></div>
            <span>{view.warnings.length}</span>
          </div>
          {view.warnings.length ? (
            <div className="warning-list">
              {view.warnings.map((warning, index) => (
                <details key={`${warning.code}-${index}`} className={`result-warning ${warning.severity}`}>
                  <summary><strong>{warning.message}</strong><span>{warning.feature_ids.length} feições</span></summary>
                  <code>{warning.code}</code>
                </details>
              ))}
            </div>
          ) : (
            <p className="result-section-empty success">Nenhum aviso foi retornado para este indicador.</p>
          )}
          <details className="method-details">
            <summary>Parâmetros utilizados</summary>
            <dl>
              {Object.entries(view.parameters).map(([key, value]) => (
                <div key={key}><dt>{friendlyKey(key)}</dt><dd>{formatParameter(value)}</dd></div>
              ))}
            </dl>
          </details>
        </section>
      </div>
    </article>
  );
}

function HistoricalRun({
  run,
  latestCompletedRun,
}: {
  run: AnalysisRun;
  latestCompletedRun: AnalysisRun | null;
}) {
  const themes = runThemes(run);
  return (
    <article className="historical-run panel-surface">
      <header>
        <div>
          <span className="eyebrow">Execução histórica</span>
          <h2>{formatRunDate(run.run_at)}</h2>
          <p>Consulta de metadados, sem comparação entre execuções.</p>
        </div>
        <span className={`run-status-badge ${run.status}`}>{runStatusLabel(run.status)}</span>
      </header>
      <div className="historical-run-grid">
        <section><span>Duração</span><strong>{formatDuration(run.duration_ms)}</strong></section>
        <section><span>Início</span><strong>{run.started_at ? formatRunDate(run.started_at) : "Não iniciado"}</strong></section>
        <section><span>Conclusão</span><strong>{run.completed_at ? formatRunDate(run.completed_at) : "Não concluído"}</strong></section>
        <section><span>Versão do projeto</span><strong>{run.project_version_id.slice(0, 12)}</strong></section>
      </div>
      <section className="historical-themes">
        <span className="eyebrow">Temas solicitados</span>
        <div>{themes.length ? themes.map((theme) => <span key={theme}>{theme}</span>) : <em>Não informados</em>}</div>
      </section>
      {run.error && (
        <section className="historical-error" role="alert">
          <span className="eyebrow">Falha registrada</span>
          <strong>{structuredErrorMessage(run.error)}</strong>
        </section>
      )}
      {run.status === "completed" && run.id !== latestCompletedRun?.id && (
        <section className="historical-contract-note">
          <strong>Valores históricos ainda não estão disponíveis neste contrato.</strong>
          <p>A API atual retorna valores somente para a execução concluída mais recente. Esta execução permanece consultável por seus metadados e rastreabilidade.</p>
        </section>
      )}
    </article>
  );
}

function friendlyKey(value: string): string {
  const text = value.replaceAll("_", " ");
  return text.charAt(0).toLocaleUpperCase("pt-BR") + text.slice(1);
}

function formatParameter(value: unknown): string {
  if (value === null || value === undefined) return "Não informado";
  if (Array.isArray(value)) return value.map(formatParameter).join(", ");
  if (typeof value === "object") return "Configuração composta";
  if (typeof value === "boolean") return value ? "Sim" : "Não";
  return String(value);
}

function structuredErrorMessage(error: Record<string, unknown>): string {
  const message = error.message ?? error.error ?? error.detail;
  return typeof message === "string" ? message : "A execução falhou; consulte o código registrado no backend.";
}
