"use client";

import { useMemo, useState, type ReactNode } from "react";
import DataWorkspace from "./DataWorkspace";
import DiagnosticWorkspace from "./DiagnosticWorkspace";
import ExportDialog from "./ExportDialog";
import FeaturePanel from "./FeaturePanel";
import MapCanvas from "./MapCanvas";
import MapDocumentControls from "./MapDocumentControls";
import OverviewWorkspace from "./OverviewWorkspace";
import ResultsWorkspace from "./ResultsWorkspace";
import type { Basemap } from "../features/catalog/api/listBasemaps";
import type { CatalogIndicator } from "../features/catalog/api/listCatalogIndicators";
import type { MapDocument, MapDocumentWithWarnings } from "../features/map-documents/api/mapDocuments";
import {
  useCreateMapDocument,
  useDeleteMapDocument,
  useMapDocuments,
  useOpenMapDocument,
  useUpdateMapDocument,
} from "../features/map-documents/hooks/useMapDocuments";
import {
  hydrateMapDocumentLayers,
  serializeMapDocumentConfig,
} from "../features/map-documents/model/mapDocumentComposition";
import { useWorkspaceBootstrap } from "../features/workspace/hooks/useWorkspaceBootstrap";
import { categoriesFor, representationModeFor } from "../features/layers/model/layerStyle";
import type { LayerGeojsonViewState } from "../features/layers/hooks/useLayerGeojsonQueries";
import type { IndicatorResult } from "../features/results/api/listProjectResults";
import { palettes } from "../lib/mockData";
import type { LayerStyleConfig, RepresentationMode, RepresentationOption, WorkspaceSection } from "../lib/types";
import { useWorkspaceStore, type SelectedFeature } from "../store/useWorkspaceStore";

const navItems: Array<{ id: WorkspaceSection; label: string; index: string }> = [
  { id: "visao-geral", label: "Visão geral", index: "01" },
  { id: "dados", label: "Dados", index: "02" },
  { id: "diagnostico", label: "Diagnóstico", index: "03" },
  { id: "resultados", label: "Resultados", index: "04" },
  { id: "documentacao", label: "Documentação", index: "05" },
];

const modeLabels: Record<RepresentationMode, string> = {
  single: "Único",
  categorical: "Categorias",
  sequential: "Gradiente",
  diverging: "Divergente",
};

function isMapDocument(value: unknown): value is MapDocument {
  if (!value || typeof value !== "object") return false;
  const document = value as Partial<MapDocument>;
  return typeof document.id === "string"
    && typeof document.name === "string"
    && typeof document.revision === "number"
    && Boolean(document.config && typeof document.config === "object");
}

function isRepresentationModeAvailable(
  option: RepresentationOption | undefined,
  mode: RepresentationMode,
): boolean {
  if (!option || option.value === "single") return mode === "single";
  if (mode === "single") return true;
  return option.type === "text" ? mode === "categorical" : mode !== "categorical";
}

export default function UrbdataPrototype() {
  const workspace = useWorkspaceBootstrap();
  const activeSection = useWorkspaceStore((state) => state.activeSection);
  const setSection = useWorkspaceStore((state) => state.setSection);
  const layers = useWorkspaceStore((state) => state.layers);
  const layerDefaults = useWorkspaceStore((state) => state.layerDefaults);
  const geojsonByLayerId = useWorkspaceStore((state) => state.geojsonByLayerId);
  const selectedLayerId = useWorkspaceStore((state) => state.selectedLayerId);
  const selectLayer = useWorkspaceStore((state) => state.selectLayer);
  const toggleLayer = useWorkspaceStore((state) => state.toggleLayer);
  const updateLayer = useWorkspaceStore((state) => state.updateLayer);
  const moveLayer = useWorkspaceStore((state) => state.moveLayer);
  const resetLayer = useWorkspaceStore((state) => state.resetLayer);
  const basemap = useWorkspaceStore((state) => state.basemap);
  const setBasemap = useWorkspaceStore((state) => state.setBasemap);
  const viewport = useWorkspaceStore((state) => state.viewport);
  const hydrateComposition = useWorkspaceStore((state) => state.hydrateComposition);
  const hasUnsavedChanges = useWorkspaceStore((state) => state.hasUnsavedChanges);
  const lastSavedAt = useWorkspaceStore((state) => state.lastSavedAt);
  const markSaved = useWorkspaceStore((state) => state.markSaved);
  const markChanged = useWorkspaceStore((state) => state.markChanged);
  const selectedFeature = useWorkspaceStore((state) => state.selectedFeature);
  const clearFeatureSelection = useWorkspaceStore((state) => state.clearFeatureSelection);
  const [toast, setToast] = useState<string | null>(null);
  const [documentName, setDocumentName] = useState("Diagnóstico territorial");
  const [activeDocument, setActiveDocument] = useState<MapDocument | null>(null);
  const [integrityWarnings, setIntegrityWarnings] = useState<MapDocumentWithWarnings["integrity_warnings"]>([]);
  const [conflictDocument, setConflictDocument] = useState<MapDocument | null>(null);
  const [deleteArmed, setDeleteArmed] = useState(false);
  const [exportOpen, setExportOpen] = useState(false);
  const documents = useMapDocuments(workspace.activeProjectId, workspace.activeVersionId);
  const openDocument = useOpenMapDocument(workspace.activeProjectId);
  const createDocument = useCreateMapDocument(workspace.activeProjectId, workspace.activeVersionId);
  const updateDocument = useUpdateMapDocument(workspace.activeProjectId, workspace.activeVersionId);
  const deleteDocument = useDeleteMapDocument(workspace.activeProjectId, workspace.activeVersionId);

  const selectedLayer = useMemo(
    () => layers.find((layer) => layer.id === selectedLayerId) ?? layers[0],
    [layers, selectedLayerId],
  );
  const compositionBaseLayers = useMemo(
    () => layers.map((layer) => ({
      ...(layerDefaults[layer.id] ?? layer),
      representationOptions: layer.representationOptions,
    })),
    [layerDefaults, layers],
  );

  function resetDocumentSession() {
    setDocumentName("Diagnóstico territorial");
    setActiveDocument(null);
    setIntegrityWarnings([]);
    setConflictDocument(null);
    setDeleteArmed(false);
    setExportOpen(false);
  }

  function notify(message: string) {
    setToast(message);
    window.setTimeout(() => setToast(null), 2800);
  }

  function compositionPayload(name = documentName) {
    return {
      name: name.trim(),
      config: serializeMapDocumentConfig({ name, layers, basemap, viewport }),
    };
  }

  function applyDocument(document: MapDocumentWithWarnings | MapDocument) {
    hydrateComposition({
      layers: hydrateMapDocumentLayers(compositionBaseLayers, document.config),
      basemap: document.config.basemap_id,
      viewport: document.config.viewport,
    });
    setDocumentName(document.name);
    setActiveDocument(document);
    setIntegrityWarnings("integrity_warnings" in document ? document.integrity_warnings : []);
    setConflictDocument(null);
    setDeleteArmed(false);
  }

  async function handleOpenDocument(documentId: string) {
    if (hasUnsavedChanges && !window.confirm("Abrir outra composição descartará as alterações locais não salvas. Deseja continuar?")) return;
    try {
      applyDocument(await openDocument.mutateAsync(documentId));
      notify("Composição aberta com a revisão mais recente.");
    } catch (error) {
      notify(error instanceof Error ? error.message : "Não foi possível abrir a composição.");
    }
  }

  function handleNewDocument() {
    if (hasUnsavedChanges && !window.confirm("Transformar o estado atual em uma nova composição? O rascunho continuará no editor.")) return;
    setActiveDocument(null);
    setIntegrityWarnings([]);
    setConflictDocument(null);
    setDeleteArmed(false);
    setDocumentName((current) => current.includes("cópia") ? current : `${current} · cópia`);
    markChanged();
  }

  async function handleSave() {
    if (!workspace.activeProjectId || !workspace.activeVersionId) {
      notify("Selecione um projeto com versão ativa antes de salvar.");
      return;
    }
    try {
      const payload = compositionPayload();
      const saved = activeDocument
        ? await updateDocument.mutateAsync({
            documentId: activeDocument.id,
            payload: { ...payload, expected_revision: activeDocument.revision },
          })
        : await createDocument.mutateAsync(payload);
      setActiveDocument(saved);
      setDocumentName(saved.name);
      setIntegrityWarnings([]);
      setConflictDocument(null);
      markSaved();
      notify(activeDocument ? `Composição atualizada para a revisão ${saved.revision}.` : "Composição criada no projeto ativo.");
    } catch (error) {
      if (error && typeof error === "object" && "context" in error) {
        const current = (error as { context?: Record<string, unknown> }).context?.current_document;
        if (isMapDocument(current)) {
          setConflictDocument(current);
          notify("Conflito de revisão detectado; seu rascunho foi preservado.");
          return;
        }
      }
      notify(error instanceof Error ? error.message : "Não foi possível salvar a composição.");
    }
  }

  async function handleDeleteDocument() {
    if (!activeDocument) return;
    if (!deleteArmed) {
      setDeleteArmed(true);
      return;
    }
    try {
      await deleteDocument.mutateAsync(activeDocument.id);
      setActiveDocument(null);
      setIntegrityWarnings([]);
      setConflictDocument(null);
      setDeleteArmed(false);
      markChanged();
      notify("Composição excluída. O conteúdo atual permanece como rascunho local.");
    } catch (error) {
      notify(error instanceof Error ? error.message : "Não foi possível excluir a composição.");
    }
  }

  function handleExport() {
    if (!activeDocument) {
      notify("Salve a composição antes de exportar o mapa.");
      return;
    }
    if (hasUnsavedChanges) {
      notify("Salve as alterações para que o PNG corresponda à revisão arquivada.");
      return;
    }
    setExportOpen(true);
  }

  const integrationError = workspace.projects.error
    ?? workspace.versions.error
    ?? workspace.layers.error
    ?? (workspace.versionContractMissing ? new Error("A API não identificou uma versão ativa para este projeto.") : null);

  return (
    <main className="app-shell">
      <header className="topbar">
        <div className="brand-lockup" aria-label="URBDATA">
          <span className="brand-mark" aria-hidden="true"><i /><i /><i /></span>
          <span className="brand-name">URBDATA</span>
          <span className="brand-divider" />
          <span className="brand-endorsement">Grupo Methafora</span>
        </div>

        <div className="project-context">
          <label className="project-selector">
            <span className="eyebrow">Projeto ativo</span>
            <select
              value={workspace.activeProjectId ?? ""}
              onChange={(event) => {
                resetDocumentSession();
                workspace.selectProject(event.target.value || null);
              }}
              disabled={workspace.projects.isLoading || workspace.projects.isEmpty}
              aria-label="Selecionar projeto ativo"
            >
              {workspace.projects.isLoading && <option value="">Carregando projetos…</option>}
              {workspace.projects.isEmpty && <option value="">Nenhum projeto disponível</option>}
              {workspace.projects.data?.map((project) => (
                <option key={project.id} value={project.id}>{project.name}</option>
              ))}
            </select>
          </label>
          <span className="context-meta">
            {[workspace.activeProject?.municipality, workspace.activeProject?.state].filter(Boolean).join(" · ") || "Contexto territorial não informado"}
          </span>
        </div>

        <div className="topbar-actions">
          <span className="version-chip"><span className="status-dot" /> {workspace.activeVersion ? `Versão ${workspace.activeVersion.number} · ativa` : "Versão não resolvida"}</span>
          <button className="icon-button" aria-label="Abrir ajuda">?</button>
          <button className="avatar-button" aria-label="Abrir menu do usuário">UR</button>
        </div>
      </header>

      <nav className="flow-nav" aria-label="Etapas do projeto">
        <div className="flow-nav-context">
          <span className="eyebrow">Fluxo do projeto</span>
          <span className="progress-copy">4 de 5 etapas processadas</span>
        </div>
        <div className="flow-nav-items">
          {navItems.map((item) => (
            <button
              key={item.id}
              className={activeSection === item.id ? "nav-item active" : "nav-item"}
              onClick={() => setSection(item.id)}
              aria-current={activeSection === item.id ? "page" : undefined}
            >
              <span className="nav-index">{item.index}</span>
              <span>{item.label}</span>
              {item.id !== "documentacao" && <span className="nav-check" aria-label="concluído">✓</span>}
            </button>
          ))}
        </div>
        <span className="flow-nav-note">{workspace.isBootstrapping ? "Sincronizando dados reais…" : "Leitura real · ambiente local"}</span>
      </nav>

      <section className="workspace">
        {activeSection === "documentacao" && selectedLayer ? (
          <DocumentationWorkspace
            projectName={workspace.activeProject?.name ?? "Projeto"}
            selectedLayer={selectedLayer}
            layers={layers}
            onSelectLayer={selectLayer}
            onToggleLayer={toggleLayer}
            onUpdateLayer={updateLayer}
            onMoveLayer={moveLayer}
            onResetLayer={resetLayer}
            basemap={basemap}
            onBasemapChange={setBasemap}
            basemaps={workspace.basemaps.data ?? []}
            basemapsLoading={workspace.basemaps.isLoading}
            documentControls={(
              <MapDocumentControls
                documents={documents.data ?? []}
                activeDocumentId={activeDocument?.id ?? null}
                activeRevision={activeDocument?.revision ?? null}
                name={documentName}
                hasUnsavedChanges={hasUnsavedChanges}
                lastSavedAt={lastSavedAt}
                integrityWarnings={integrityWarnings}
                conflictDocument={conflictDocument}
                isLoading={documents.isLoading}
                isSaving={createDocument.isPending || updateDocument.isPending}
                isOpening={openDocument.isPending}
                isDeleting={deleteDocument.isPending}
                deleteArmed={deleteArmed}
                error={documents.error ?? openDocument.error ?? createDocument.error ?? (updateDocument.error?.kind === "conflict" ? null : updateDocument.error) ?? deleteDocument.error ?? null}
                onNameChange={(name) => { setDocumentName(name); markChanged(); }}
                onOpen={(id) => void handleOpenDocument(id)}
                onNew={handleNewDocument}
                onSave={() => void handleSave()}
                onDelete={() => void handleDeleteDocument()}
                onCancelDelete={() => setDeleteArmed(false)}
                onLoadConflict={() => conflictDocument && applyDocument(conflictDocument)}
                onKeepConflictAsCopy={() => {
                  setActiveDocument(null);
                  setConflictDocument(null);
                  setDocumentName((current) => `${current} · cópia`);
                  markChanged();
                }}
              />
            )}
            onExport={handleExport}
            geojsonLoadedCount={workspace.geojson.loadedCount}
            geojsonLoading={workspace.geojson.isFetching}
            geojsonErrorCount={workspace.geojson.errors.length}
            geojsonEmptyCount={workspace.geojson.emptyCount}
            geojsonStateByLayerId={workspace.geojson.stateByLayerId}
            onRetryLayer={workspace.geojson.retryLayer}
            onRetryFailedLayers={workspace.geojson.retryFailedLayers}
            selectedFeature={selectedFeature}
            onClearFeatureSelection={clearFeatureSelection}
            catalog={workspace.catalog.data ?? []}
            results={workspace.results.data ?? []}
            compatibleIndicatorCodes={workspace.attributes.data?.compatible_indicators ?? []}
            featurePanelLoading={workspace.catalog.isLoading || workspace.results.isLoading || workspace.attributes.isLoading}
            featurePanelError={workspace.catalog.error ?? workspace.results.error ?? workspace.attributes.error ?? null}
            onRetryFeaturePanel={() => {
              void Promise.all([
                workspace.catalog.refetch(),
                workspace.results.refetch(),
                workspace.attributes.refetch(),
              ]);
            }}
          />
        ) : activeSection === "documentacao" ? (
          <IntegrationState
            isLoading={workspace.isBootstrapping}
            error={integrationError}
            emptyMessage={workspace.projects.isEmpty ? "Nenhum projeto disponível." : "A versão ativa não possui camadas para composição."}
          />
        ) : activeSection === "visao-geral" ? (
          <OverviewWorkspace
            projects={workspace.projects.data ?? []}
            projectsLoading={workspace.projects.isLoading}
            projectsError={workspace.projects.error}
            activeProjectId={workspace.activeProjectId}
            activeVersionId={workspace.activeVersionId}
            projectLayers={workspace.layers.data ?? []}
            onSelectProject={(id) => { resetDocumentSession(); workspace.selectProject(id); }}
            onOpenData={() => setSection("dados")}
          />
        ) : activeSection === "dados" ? (
          <DataWorkspace
            projectId={workspace.activeProjectId}
            activeVersion={workspace.activeVersion}
            layers={layers}
            selectedLayer={selectedLayer ?? null}
            attributes={workspace.attributes.data}
            isLoading={workspace.isBootstrapping}
            attributesLoading={workspace.attributes.isLoading}
            error={integrationError}
            attributesError={workspace.attributes.error ?? null}
            geojsonStateByLayerId={workspace.geojson.stateByLayerId}
            onSelectLayer={selectLayer}
            onRetryLayer={workspace.geojson.retryLayer}
            onOpenDocumentation={() => setSection("documentacao")}
          />
        ) : activeSection === "diagnostico" ? (
          <DiagnosticWorkspace
            key={workspace.activeProjectId ?? "no-project"}
            projectId={workspace.activeProjectId}
            versionLabel={workspace.activeVersion ? `a versão ${workspace.activeVersion.number}` : "a versão ativa"}
            layers={layers}
            catalog={workspace.catalog.data ?? []}
            runs={workspace.runs.data ?? []}
            isLoading={workspace.isBootstrapping || workspace.catalog.isLoading}
            catalogError={workspace.catalog.error ?? null}
            onOpenData={() => setSection("dados")}
            onOpenResults={() => setSection("resultados")}
          />
        ) : activeSection === "resultados" ? (
          <ResultsWorkspace
            projectId={workspace.activeProjectId}
            versionLabel={workspace.activeVersion ? `a versão ${workspace.activeVersion.number}` : "a versão ativa"}
            layers={layers}
            catalog={workspace.catalog.data ?? []}
            results={workspace.results.data ?? []}
            runs={workspace.runs.data ?? []}
            selectedFeature={selectedFeature}
            catalogLoading={workspace.catalog.isLoading}
            resultsLoading={workspace.results.isLoading}
            runsLoading={workspace.runs.isLoading}
            catalogError={workspace.catalog.error ?? null}
            resultsError={workspace.results.error ?? null}
            runsError={workspace.runs.error ?? null}
            onClearFeatureSelection={clearFeatureSelection}
            onRefresh={() => {
              void Promise.all([
                workspace.catalog.refetch(),
                workspace.results.refetch(),
                workspace.runs.refetch(),
              ]);
            }}
            onOpenDiagnosis={() => setSection("diagnostico")}
          />
        ) : (
          <SectionPreview section={activeSection} onOpenDocumentation={() => setSection("documentacao")} />
        )}
      </section>

      <footer className="statusbar">
        <span>GeoJSON · WGS 84</span>
        <span>{layers.reduce((total, layer) => total + (layer.featureCount ?? 0), 0).toLocaleString("pt-BR")} elementos</span>
        <span>{layers.filter((layer) => layer.visible).length} camadas visíveis</span>
        {selectedFeature && <span>Elemento {selectedFeature.featureId.slice(0, 8)} selecionado</span>}
        <span className="statusbar-spacer" />
        <span><span className="status-dot" /> API local · leitura tipada</span>
      </footer>

      <div className={toast ? "toast visible" : "toast"} role="status" aria-live="polite">
        {toast}
      </div>
      {exportOpen && activeDocument && workspace.activeProjectId && (
        <ExportDialog
          open
          projectId={workspace.activeProjectId}
          projectName={workspace.activeProject?.name ?? "Projeto"}
          document={activeDocument}
          layers={layers}
          geojsonByLayerId={geojsonByLayerId}
          basemap={workspace.basemaps.data?.find((item) => item.id === activeDocument.config.basemap_id) ?? null}
          runs={workspace.runs.data ?? []}
          integrityWarnings={integrityWarnings}
          onClose={() => setExportOpen(false)}
        />
      )}
    </main>
  );
}

interface DocumentationWorkspaceProps {
  projectName: string;
  selectedLayer: LayerStyleConfig;
  layers: LayerStyleConfig[];
  onSelectLayer: (id: string) => void;
  onToggleLayer: (id: string) => void;
  onUpdateLayer: (id: string, update: Partial<LayerStyleConfig>) => void;
  onMoveLayer: (id: string, direction: -1 | 1) => void;
  onResetLayer: (id: string) => void;
  basemap: string;
  onBasemapChange: (id: string) => void;
  basemaps: Basemap[];
  basemapsLoading: boolean;
  documentControls: ReactNode;
  onExport: () => void;
  geojsonLoadedCount: number;
  geojsonLoading: boolean;
  geojsonErrorCount: number;
  geojsonEmptyCount: number;
  geojsonStateByLayerId: Record<string, LayerGeojsonViewState>;
  onRetryLayer: (id: string) => Promise<void>;
  onRetryFailedLayers: () => Promise<void>;
  selectedFeature: SelectedFeature | null;
  onClearFeatureSelection: () => void;
  catalog: CatalogIndicator[];
  results: IndicatorResult[];
  compatibleIndicatorCodes: string[];
  featurePanelLoading: boolean;
  featurePanelError: ReturnType<typeof useWorkspaceBootstrap>["catalog"]["error"];
  onRetryFeaturePanel: () => void;
}

function DocumentationWorkspace({
  projectName,
  selectedLayer,
  layers,
  onSelectLayer,
  onToggleLayer,
  onUpdateLayer,
  onMoveLayer,
  onResetLayer,
  basemap,
  onBasemapChange,
  basemaps,
  basemapsLoading,
  documentControls,
  onExport,
  geojsonLoadedCount,
  geojsonLoading,
  geojsonErrorCount,
  geojsonEmptyCount,
  geojsonStateByLayerId,
  onRetryLayer,
  onRetryFailedLayers,
  selectedFeature,
  onClearFeatureSelection,
  catalog,
  results,
  compatibleIndicatorCodes,
  featurePanelLoading,
  featurePanelError,
  onRetryFeaturePanel,
}: DocumentationWorkspaceProps) {
  const selectedOption = selectedLayer.representationOptions.find((option) => option.value === selectedLayer.representation);

  return (
    <div className="documentation-view">
      <div className="workspace-header">
        <div>
          <span className="eyebrow">Composição cartográfica</span>
          <h1>Documentação</h1>
          <p>Prepare a apresentação e a exportação do mapa.</p>
        </div>
        {documentControls}
        <button className="primary-button document-export-action" onClick={onExport}>Exportar PNG</button>
      </div>

      <div className="editor-grid">
        <aside className="layers-panel panel-surface" aria-label="Camadas do mapa">
          <div className="panel-heading">
            <div>
              <span className="eyebrow">Mapa</span>
              <h2>Camadas</h2>
            </div>
            <span className="panel-count">{layers.filter((layer) => layer.visible).length}/{layers.length}</span>
          </div>
          <p className="panel-help">A ordem define o empilhamento na visualização e na exportação.</p>

          <div className="layer-list">
            {[...layers].reverse().map((layer) => {
              const originalIndex = layers.findIndex((item) => item.id === layer.id);
              const runtimeState = geojsonStateByLayerId[layer.id];
              return (
                <div
                  key={layer.id}
                  className={selectedLayer.id === layer.id ? "layer-row selected" : "layer-row"}
                  onClick={() => onSelectLayer(layer.id)}
                >
                  <button
                    className={layer.visible ? "visibility-toggle on" : "visibility-toggle"}
                    onClick={(event) => { event.stopPropagation(); onToggleLayer(layer.id); }}
                    aria-label={`${layer.visible ? "Ocultar" : "Exibir"} ${layer.name}`}
                    aria-pressed={layer.visible}
                  >
                    <span />
                  </button>
                  <span
                    className={layer.geometry === "line" ? "layer-symbol line" : "layer-symbol"}
                    style={{ background: layer.geometry === "line" ? layer.strokeColor : layer.color, borderColor: layer.strokeColor }}
                    aria-hidden="true"
                  />
                  <span className="layer-copy">
                    <strong>{layer.shortName}</strong>
                    <small>{geometryLabel(layer)} · {geojsonStateLabel(runtimeState)}</small>
                  </span>
                  <span className="layer-order-controls">
                    {(runtimeState?.status === "error" || runtimeState?.status === "stale") && (
                      <button onClick={(event) => { event.stopPropagation(); void onRetryLayer(layer.id); }} aria-label={`Tentar carregar ${layer.name} novamente`}>↻</button>
                    )}
                    <button disabled={originalIndex === layers.length - 1} onClick={(event) => { event.stopPropagation(); onMoveLayer(layer.id, 1); }} aria-label={`Mover ${layer.name} para cima`}>↑</button>
                    <button disabled={originalIndex === 0} onClick={(event) => { event.stopPropagation(); onMoveLayer(layer.id, -1); }} aria-label={`Mover ${layer.name} para baixo`}>↓</button>
                  </span>
                </div>
              );
            })}
          </div>

          <div className="basemap-section">
            <div className="section-label-row">
              <span className="eyebrow">Plano de fundo</span>
              {basemaps.find((item) => item.id === basemap)?.attribution && <span className="attribution-badge">atribuição obrigatória</span>}
            </div>
            <div className="basemap-grid">
              {basemapsLoading && <span className="panel-help">Carregando catálogo…</span>}
              {basemaps.map((item) => (
                <button key={item.id} className={basemap === item.id ? "basemap-card active" : "basemap-card"} onClick={() => onBasemapChange(item.id)}>
                  <span className={`basemap-preview ${item.color_mode}`}><i /><i /><i /></span>
                  <span>{item.label}</span>
                </button>
              ))}
            </div>
          </div>
        </aside>

        <section className="map-stage" aria-label="Pré-visualização do documento">
          <div className="map-toolbar">
            <div className="map-title">
              <span className="map-kicker">{projectName.toUpperCase()}</span>
              <strong>Diagnóstico territorial</strong>
            </div>
            <div className="map-toolbar-actions">
              {selectedFeature && (
                <button className="selection-chip" onClick={onClearFeatureSelection} title="Limpar seleção">
                  Elemento {selectedFeature.featureId.slice(0, 8)} ×
                </button>
              )}
              <button title="Desfazer" aria-label="Desfazer alteração">↶</button>
              <button title="Refazer" aria-label="Refazer alteração">↷</button>
              <span className="zoom-chip">100%</span>
            </div>
          </div>
          <div className="map-frame">
            <MapCanvas />
            {selectedFeature && (
              <FeaturePanel
                feature={selectedFeature}
                layer={layers.find((layer) => layer.id === selectedFeature.layerId) ?? selectedLayer}
                catalog={catalog}
                results={results}
                compatibleIndicatorCodes={compatibleIndicatorCodes}
                isLoading={featurePanelLoading}
                error={featurePanelError}
                onRetry={onRetryFeaturePanel}
                onClose={onClearFeatureSelection}
              />
            )}
            {geojsonLoading && geojsonLoadedCount === 0 && (
              <div className="map-runtime-overlay" role="status"><strong>Preparando o mapa</strong><span>Carregando as geometrias da versão ativa…</span></div>
            )}
            {!geojsonLoading && geojsonLoadedCount === 0 && geojsonErrorCount > 0 && (
              <div className="map-runtime-overlay error" role="alert"><strong>Não foi possível montar o mapa</strong><span>As camadas continuam disponíveis no painel.</span><button className="secondary-button" onClick={() => void onRetryFailedLayers()}>Tentar novamente</button></div>
            )}
            {!geojsonLoading && layers.length > 0 && geojsonEmptyCount === layers.length && (
              <div className="map-runtime-overlay empty"><strong>Sem geometrias para exibir</strong><span>As camadas existem, mas estão vazias nesta versão.</span></div>
            )}
            <div className="map-legend">
              <span className="eyebrow">Legenda</span>
              {layers.filter((layer) => layer.visible && ["ready", "stale"].includes(geojsonStateByLayerId[layer.id]?.status ?? "")).map((layer) => (
                <div className="legend-row" key={layer.id}>
                  <span className={layer.geometry === "line" ? "legend-symbol line" : "legend-symbol"} style={{ background: layer.color, borderColor: layer.strokeColor }} />
                  <span>{layer.shortName}</span>
                </div>
              ))}
            </div>
            <div className="north-arrow" aria-label="Norte"><span>N</span><i /></div>
            {basemaps.find((item) => item.id === basemap)?.attribution && (
              <div className="map-attribution">{basemaps.find((item) => item.id === basemap)?.attribution}</div>
            )}
          </div>
          <div className="map-caption">
            <span>{selectedFeature ? "1 elemento territorial selecionado" : geojsonLoading ? "Carregando geometrias…" : "Prévia com dados reais"}</span>
            <span>{geojsonLoadedCount} de {layers.length} camadas carregadas{geojsonErrorCount ? ` · ${geojsonErrorCount} com erro` : ""}</span>
          </div>
        </section>

        <aside className="properties-panel panel-surface" aria-label="Propriedades da camada">
          <div className="panel-heading">
            <div>
              <span className="eyebrow">Camada selecionada</span>
              <h2>{selectedLayer.shortName}</h2>
            </div>
            <button className="text-button" onClick={() => onResetLayer(selectedLayer.id)}>Restaurar</button>
          </div>

          <div className="property-group">
            <label htmlFor="representation">Representar por</label>
            <select
              id="representation"
              value={selectedLayer.representation}
              onChange={(event) => {
                const option = selectedLayer.representationOptions.find((item) => item.value === event.target.value);
                  onUpdateLayer(selectedLayer.id, {
                    representation: event.target.value,
                    mode: option ? representationModeFor(option) : "single",
                    palette: undefined,
                    categories: option ? categoriesFor(option) : undefined,
                  range: option?.range,
                });
              }}
            >
              {selectedLayer.representationOptions.map((option) => (
                <option key={option.value} value={option.value} disabled={Boolean(option.unavailableReason)}>{option.label}</option>
              ))}
            </select>
            {selectedOption && (
              <div className="field-meta">
                <span className={`source-tag ${selectedOption.source}`}>{selectedOption.source === "indicator" ? "Indicador" : selectedOption.source === "mapped" ? "Campo mapeado" : "Fonte"}</span>
                <span>{selectedOption.type === "number" ? `Numérico${selectedOption.unit ? ` · ${selectedOption.unit}` : ""}` : "Categórico"}</span>
              </div>
            )}
          </div>

          <fieldset className="property-group">
            <legend>Tipo de representação</legend>
            <div className="segmented-control">
              {(Object.keys(modeLabels) as RepresentationMode[]).map((mode) => (
                <button
                  key={mode}
                  className={selectedLayer.mode === mode ? "active" : ""}
                  onClick={() => onUpdateLayer(selectedLayer.id, { mode })}
                  type="button"
                  disabled={!isRepresentationModeAvailable(selectedOption, mode)}
                >
                  {modeLabels[mode]}
                </button>
              ))}
            </div>
          </fieldset>

          <div className="property-group">
            <label>Paleta</label>
            <div className="palette-list">
              {palettes.map((palette) => (
                <button
                  key={palette.name}
                  className={selectedLayer.color === palette.colors[0] ? "palette-option active" : "palette-option"}
                  onClick={() => onUpdateLayer(selectedLayer.id, {
                    color: palette.colors[0],
                    secondaryColor: palette.colors[palette.colors.length - 1],
                    palette: palette.colors,
                    categories: selectedLayer.categories
                      ? Object.fromEntries(Object.keys(selectedLayer.categories).map((key, index) => [key, palette.colors[index % palette.colors.length]]))
                      : undefined,
                  })}
                  aria-label={`Usar paleta ${palette.name}`}
                >
                  <span>{palette.name}</span>
                  <i>{palette.colors.map((color) => <b key={color} style={{ background: color }} />)}</i>
                </button>
              ))}
            </div>
          </div>

          <div className="property-group control-row">
            <div className="label-with-value">
              <label htmlFor="opacity">Transparência</label>
              <output>{Math.round((1 - selectedLayer.opacity) * 100)}%</output>
            </div>
            <input
              id="opacity"
              type="range"
              min="0.1"
              max="1"
              step="0.01"
              value={selectedLayer.opacity}
              onChange={(event) => onUpdateLayer(selectedLayer.id, { opacity: Number(event.target.value) })}
            />
          </div>

          <div className="property-group line-settings">
            <label>Contorno e linha</label>
            <div className="two-column-fields">
              <label className="compact-field">
                <span>Cor</span>
                <span className="color-control">
                  <input type="color" value={selectedLayer.strokeColor} onChange={(event) => onUpdateLayer(selectedLayer.id, { strokeColor: event.target.value, color: selectedLayer.geometry === "line" ? event.target.value : selectedLayer.color })} />
                  <code>{selectedLayer.strokeColor.toUpperCase()}</code>
                </span>
              </label>
              <label className="compact-field">
                <span>Estilo</span>
                <select value={selectedLayer.lineStyle} onChange={(event) => onUpdateLayer(selectedLayer.id, { lineStyle: event.target.value as LayerStyleConfig["lineStyle"] })}>
                  <option value="solid">Contínuo</option>
                  <option value="dashed">Tracejado</option>
                  <option value="dotted">Pontilhado</option>
                </select>
              </label>
            </div>
            <div className="label-with-value">
              <label htmlFor="stroke-width">Espessura</label>
              <output>{selectedLayer.strokeWidth.toFixed(1)} px</output>
            </div>
            <input id="stroke-width" type="range" min="0.5" max="8" step="0.1" value={selectedLayer.strokeWidth} onChange={(event) => onUpdateLayer(selectedLayer.id, { strokeWidth: Number(event.target.value) })} />
          </div>

          <div className="quality-note">
            <span className="quality-icon">i</span>
            <div>
              <strong>Representação válida</strong>
              <p>As classes e a legenda usam a mesma configuração. Valores brutos permanecem inalterados.</p>
            </div>
          </div>
        </aside>
      </div>
    </div>
  );
}

function geometryLabel(layer: LayerStyleConfig): string {
  if (layer.geometry === "polygon") return "Polígono";
  if (layer.geometry === "point") return "Ponto";
  return "Linha";
}

function geojsonStateLabel(state: LayerGeojsonViewState | undefined): string {
  if (!state || state.status === "loading") return "carregando";
  if (state.status === "error") return "erro no mapa";
  if (state.status === "stale") return "desatualizada";
  if (state.status === "empty") return "sem geometrias";
  return state.isRefreshing ? "atualizando" : "pronta";
}

function IntegrationState({
  isLoading,
  error,
  emptyMessage,
}: {
  isLoading: boolean;
  error: Error | null;
  emptyMessage: string;
}) {
  return (
    <div className="section-preview">
      <div className={`integration-state ${error ? "error" : "empty"}`} role={error ? "alert" : "status"}>
        <strong>{isLoading ? "Preparando o projeto ativo…" : error ? "Não foi possível carregar o projeto." : emptyMessage}</strong>
        {error && <span>{error.message}</span>}
      </div>
    </div>
  );
}

function SectionPreview({ section, onOpenDocumentation }: { section: Exclude<WorkspaceSection, "documentacao">; onOpenDocumentation: () => void }) {
  const content = {
    "visao-geral": { eyebrow: "Projeto", title: "Visão geral", description: "Leitura rápida da situação territorial e da qualidade das bases." },
    dados: { eyebrow: "Bases territoriais", title: "Dados", description: "Camadas, atributos mapeados e cobertura do projeto." },
    diagnostico: { eyebrow: "Análise", title: "Diagnóstico", description: "Indicadores organizados por território, uso do solo, quadras e sistema viário." },
    resultados: { eyebrow: "Síntese", title: "Resultados", description: "Valores rastreáveis, avisos e elementos territoriais contribuintes." },
  }[section];

  return (
    <div className="section-preview">
      <div className="section-preview-header">
        <span className="eyebrow">{content.eyebrow}</span>
        <h1>{content.title}</h1>
        <p>{content.description}</p>
      </div>
      <div className="integration-state empty section-pending">
        <strong>Esta etapa ainda não está conectada a dados reais.</strong>
        <span>Os valores demonstrativos foram removidos para não serem confundidos com informações do projeto ativo.</span>
        <button className="secondary-button" onClick={onOpenDocumentation}>Abrir composição cartográfica</button>
      </div>
    </div>
  );
}
