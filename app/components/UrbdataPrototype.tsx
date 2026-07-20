"use client";

import { useMemo, useRef, useState } from "react";
import MapCanvas from "./MapCanvas";
import { palettes } from "../lib/mockData";
import type { LayerStyleConfig, RepresentationMode, WorkspaceSection } from "../lib/types";
import { useWorkspaceStore } from "../store/useWorkspaceStore";

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
};

export default function UrbdataPrototype() {
  const activeSection = useWorkspaceStore((state) => state.activeSection);
  const setSection = useWorkspaceStore((state) => state.setSection);
  const layers = useWorkspaceStore((state) => state.layers);
  const selectedLayerId = useWorkspaceStore((state) => state.selectedLayerId);
  const selectLayer = useWorkspaceStore((state) => state.selectLayer);
  const toggleLayer = useWorkspaceStore((state) => state.toggleLayer);
  const updateLayer = useWorkspaceStore((state) => state.updateLayer);
  const moveLayer = useWorkspaceStore((state) => state.moveLayer);
  const resetLayer = useWorkspaceStore((state) => state.resetLayer);
  const basemap = useWorkspaceStore((state) => state.basemap);
  const setBasemap = useWorkspaceStore((state) => state.setBasemap);
  const hasUnsavedChanges = useWorkspaceStore((state) => state.hasUnsavedChanges);
  const lastSavedAt = useWorkspaceStore((state) => state.lastSavedAt);
  const markSaved = useWorkspaceStore((state) => state.markSaved);
  const [toast, setToast] = useState<string | null>(null);
  const canvasGetter = useRef<(() => HTMLCanvasElement | null) | null>(null);

  const selectedLayer = useMemo(
    () => layers.find((layer) => layer.id === selectedLayerId) ?? layers[0],
    [layers, selectedLayerId],
  );

  function notify(message: string) {
    setToast(message);
    window.setTimeout(() => setToast(null), 2800);
  }

  function handleSave() {
    markSaved();
    notify("Composição salva localmente para avaliação de UX.");
  }

  async function handleExport() {
    const source = canvasGetter.current?.();
    if (!source) {
      notify("A pré-visualização ainda está sendo preparada.");
      return;
    }

    try {
      const output = document.createElement("canvas");
      output.width = 1800;
      output.height = 1200;
      const context = output.getContext("2d");
      if (!context) return;
      context.fillStyle = "#f6f4ef";
      context.fillRect(0, 0, output.width, output.height);
      context.fillStyle = "#172724";
      context.fillRect(0, 0, output.width, 116);
      context.fillStyle = "#f6f4ef";
      context.font = "600 30px Arial";
      context.fillText("RESIDENCIAL VANDRESSEN", 54, 54);
      context.font = "16px Arial";
      context.fillStyle = "#b9c4c0";
      context.fillText("Composição territorial · prévia 2×", 54, 84);
      context.drawImage(source, 340, 150, 1406, 982);

      context.fillStyle = "#ffffff";
      context.fillRect(54, 150, 252, 982);
      context.fillStyle = "#172724";
      context.font = "600 18px Arial";
      context.fillText("LEGENDA", 82, 196);

      let y = 238;
      layers.filter((layer) => layer.visible).forEach((layer) => {
        context.fillStyle = layer.color;
        context.fillRect(82, y - 15, 22, 22);
        context.strokeStyle = layer.strokeColor;
        context.strokeRect(82, y - 15, 22, 22);
        context.fillStyle = "#35423f";
        context.font = "15px Arial";
        context.fillText(layer.shortName, 118, y + 2);
        y += 46;
      });

      context.fillStyle = "#68716e";
      context.font = "13px Arial";
      context.fillText("Fonte: dados demonstrativos", 82, 1060);
      context.fillText(basemap === "osm" ? "© OpenStreetMap contributors" : "Sem mapa-base", 82, 1084);
      context.fillText("URBDATA · Grupo Methafora", 82, 1108);

      const link = document.createElement("a");
      link.download = "urbdata-composicao-vandressen.png";
      link.href = output.toDataURL("image/png");
      link.click();
      notify("Prévia PNG exportada pelo mesmo mapa exibido na tela.");
    } catch {
      notify("A base externa impediu esta prévia. Selecione “Sem mapa-base” e tente novamente.");
    }
  }

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
          <span className="eyebrow">Projeto ativo</span>
          <strong>Residencial Vandressen</strong>
          <span className="context-meta">Florianópolis · SC</span>
        </div>

        <div className="topbar-actions">
          <span className="version-chip"><span className="status-dot" /> Versão 1 · ativa</span>
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
        <span className="flow-nav-note">Dados demonstrativos · ambiente local</span>
      </nav>

      <section className="workspace">
        {activeSection === "documentacao" ? (
          <DocumentationWorkspace
            selectedLayer={selectedLayer}
            layers={layers}
            onSelectLayer={selectLayer}
            onToggleLayer={toggleLayer}
            onUpdateLayer={updateLayer}
            onMoveLayer={moveLayer}
            onResetLayer={resetLayer}
            basemap={basemap}
            onBasemapChange={setBasemap}
            hasUnsavedChanges={hasUnsavedChanges}
            lastSavedAt={lastSavedAt}
            onSave={handleSave}
            onExport={handleExport}
            onCanvasReady={(getter) => { canvasGetter.current = getter; }}
          />
        ) : (
          <SectionPreview section={activeSection} onOpenDocumentation={() => setSection("documentacao")} />
        )}
      </section>

      <footer className="statusbar">
        <span>WGS 84 · EPSG:4326</span>
        <span>387 feições</span>
        <span>{layers.filter((layer) => layer.visible).length} camadas visíveis</span>
        <span className="statusbar-spacer" />
        <span><span className="status-dot" /> Protótipo local</span>
      </footer>

      <div className={toast ? "toast visible" : "toast"} role="status" aria-live="polite">
        {toast}
      </div>
    </main>
  );
}

interface DocumentationWorkspaceProps {
  selectedLayer: LayerStyleConfig;
  layers: LayerStyleConfig[];
  onSelectLayer: (id: string) => void;
  onToggleLayer: (id: string) => void;
  onUpdateLayer: (id: string, update: Partial<LayerStyleConfig>) => void;
  onMoveLayer: (id: string, direction: -1 | 1) => void;
  onResetLayer: (id: string) => void;
  basemap: "none" | "osm";
  onBasemapChange: (id: "none" | "osm") => void;
  hasUnsavedChanges: boolean;
  lastSavedAt: string | null;
  onSave: () => void;
  onExport: () => void;
  onCanvasReady: (getter: (() => HTMLCanvasElement | null) | null) => void;
}

function DocumentationWorkspace({
  selectedLayer,
  layers,
  onSelectLayer,
  onToggleLayer,
  onUpdateLayer,
  onMoveLayer,
  onResetLayer,
  basemap,
  onBasemapChange,
  hasUnsavedChanges,
  lastSavedAt,
  onSave,
  onExport,
  onCanvasReady,
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
        <div className="document-title-field">
          <label htmlFor="document-name">Nome da composição</label>
          <input id="document-name" defaultValue="Diagnóstico territorial · Versão 1" />
        </div>
        <div className="document-actions">
          <span className={hasUnsavedChanges ? "save-state pending" : "save-state"}>
            {hasUnsavedChanges ? "Alterações não salvas" : lastSavedAt ? `Salvo às ${lastSavedAt}` : "Rascunho local"}
          </span>
          <button className="secondary-button" onClick={onSave}>Salvar composição</button>
          <button className="primary-button" onClick={onExport}>Exportar prévia</button>
        </div>
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
                    <small>{layer.geometry === "polygon" ? "Polígono" : "Linha"}</small>
                  </span>
                  <span className="layer-order-controls">
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
              {basemap === "osm" && <span className="attribution-badge">atribuição obrigatória</span>}
            </div>
            <div className="basemap-grid">
              <button className={basemap === "none" ? "basemap-card active" : "basemap-card"} onClick={() => onBasemapChange("none")}>
                <span className="basemap-preview none"><i /></span>
                <span>Sem mapa-base</span>
              </button>
              <button className={basemap === "osm" ? "basemap-card active" : "basemap-card"} onClick={() => onBasemapChange("osm")}>
                <span className="basemap-preview osm"><i /><i /><i /></span>
                <span>OSM claro</span>
              </button>
            </div>
          </div>
        </aside>

        <section className="map-stage" aria-label="Pré-visualização do documento">
          <div className="map-toolbar">
            <div className="map-title">
              <span className="map-kicker">RESIDENCIAL VANDRESSEN</span>
              <strong>Diagnóstico territorial</strong>
            </div>
            <div className="map-toolbar-actions">
              <button title="Desfazer" aria-label="Desfazer alteração">↶</button>
              <button title="Refazer" aria-label="Refazer alteração">↷</button>
              <span className="zoom-chip">100%</span>
            </div>
          </div>
          <div className="map-frame">
            <MapCanvas onCanvasReady={onCanvasReady} />
            <div className="map-legend">
              <span className="eyebrow">Legenda</span>
              {layers.filter((layer) => layer.visible).map((layer) => (
                <div className="legend-row" key={layer.id}>
                  <span className={layer.geometry === "line" ? "legend-symbol line" : "legend-symbol"} style={{ background: layer.color, borderColor: layer.strokeColor }} />
                  <span>{layer.shortName}</span>
                </div>
              ))}
            </div>
            <div className="north-arrow" aria-label="Norte"><span>N</span><i /></div>
            {basemap === "osm" && <div className="map-attribution">© OpenStreetMap contributors</div>}
          </div>
          <div className="map-caption">
            <span>Prévia em tempo real</span>
            <span>Escala aproximada · uso demonstrativo</span>
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
                  mode: event.target.value === "single" ? "single" : option?.type === "number" ? "sequential" : "categorical",
                });
              }}
            >
              {selectedLayer.representationOptions.map((option) => (
                <option key={option.value} value={option.value}>{option.label}</option>
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
      <div className="summary-grid">
        <article className="summary-card primary"><span>Área analisada</span><strong>34,82 ha</strong><small>100% da matrícula coberta</small></article>
        <article className="summary-card"><span>Feições territoriais</span><strong>387</strong><small>12 avisos informativos</small></article>
        <article className="summary-card"><span>Camadas válidas</span><strong>6 de 7</strong><small>Edificações com cobertura parcial</small></article>
      </div>
      <div className="insight-panel">
        <div><span className="eyebrow">Próxima ação</span><h2>Prepare o mapa para comunicação</h2><p>Use os dados processados para definir camadas, cores, linhas e mapa-base antes de exportar.</p><button className="primary-button" onClick={onOpenDocumentation}>Abrir Documentação</button></div>
        <div className="mini-map" aria-hidden="true"><i /><i /><i /><i /></div>
      </div>
    </div>
  );
}
