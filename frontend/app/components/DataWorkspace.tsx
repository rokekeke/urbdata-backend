"use client";

import { useState } from "react";

import type { AppError } from "../lib/errors";
import type { LayerStyleConfig } from "../lib/types";
import type { LayerAttributes } from "../features/layers/api/getLayerAttributes";
import { useDeleteLayer } from "../features/layers/hooks/useDeleteLayer";
import type { LayerGeojsonViewState } from "../features/layers/hooks/useLayerGeojsonQueries";
import type { ProjectVersion } from "../features/projects";

interface DataWorkspaceProps {
  projectId: string | null;
  activeVersion: ProjectVersion | null;
  layers: LayerStyleConfig[];
  selectedLayer: LayerStyleConfig | null;
  attributes: LayerAttributes | undefined;
  isLoading: boolean;
  attributesLoading: boolean;
  error: Error | null;
  attributesError: AppError | null;
  geojsonStateByLayerId: Record<string, LayerGeojsonViewState>;
  onSelectLayer: (id: string) => void;
  onRetryLayer: (id: string) => Promise<void>;
  onOpenDocumentation: () => void;
}

const statusLabels: Record<NonNullable<LayerStyleConfig["status"]>, string> = {
  uploaded: "Enviada",
  mapped: "Mapeada",
  validated: "Validada",
  error: "Com erro",
};

export default function DataWorkspace({
  projectId,
  activeVersion,
  layers,
  selectedLayer,
  attributes,
  isLoading,
  attributesLoading,
  error,
  attributesError,
  geojsonStateByLayerId,
  onSelectLayer,
  onRetryLayer,
  onOpenDocumentation,
}: DataWorkspaceProps) {
  const featureCount = layers.reduce((total, layer) => total + (layer.featureCount ?? 0), 0);
  const [deleteArmedLayerId, setDeleteArmedLayerId] = useState<string | null>(null);
  const deleteLayer = useDeleteLayer(projectId, activeVersion?.id ?? null);

  function handleDeleteClick(layerId: string) {
    if (deleteArmedLayerId !== layerId) {
      setDeleteArmedLayerId(layerId);
      return;
    }
    deleteLayer.mutate(layerId, { onSettled: () => setDeleteArmedLayerId(null) });
  }

  return (
    <div className="data-view">
      <div className="data-header">
        <div>
          <span className="eyebrow">Bases territoriais</span>
          <h1>Dados</h1>
          <p>Camadas e atributos fornecidos pela versão ativa do projeto.</p>
        </div>
        <button className="secondary-button" onClick={onOpenDocumentation} disabled={layers.length === 0}>
          Visualizar no mapa
        </button>
      </div>

      {error ? (
        <div className="integration-state error" role="alert">
          <strong>Não foi possível carregar as bases territoriais.</strong>
          <span>{error.message}</span>
        </div>
      ) : isLoading ? (
        <div className="integration-state" role="status">Carregando projeto, versão ativa e camadas…</div>
      ) : layers.length === 0 ? (
        <div className="integration-state empty">
          <strong>Nenhuma camada na versão ativa.</strong>
          <span>O projeto existe, mas ainda não possui uma base territorial disponível para leitura.</span>
        </div>
      ) : (
        <>
          <div className="data-summary" aria-label="Resumo das bases">
            <article><span>Versão ativa</span><strong>{activeVersion ? `Versão ${activeVersion.number}` : "—"}</strong><small>{activeVersion?.name ?? "Contrato em validação"}</small></article>
            <article><span>Camadas</span><strong>{layers.length}</strong><small>{layers.filter((layer) => layer.status === "validated").length} validadas</small></article>
            <article><span>Elementos territoriais</span><strong>{featureCount.toLocaleString("pt-BR")}</strong><small>Soma informada pelas camadas</small></article>
          </div>

          <div className="data-grid">
            <aside className="data-layer-list panel-surface" aria-label="Camadas da versão ativa">
              <div className="panel-heading">
                <div><span className="eyebrow">Versão atual</span><h2>Camadas</h2></div>
                <span className="panel-count">{layers.length}</span>
              </div>
              <p className="panel-help">Selecione uma camada para conferir campos, cobertura e recomendações de representação.</p>
              {layers.map((layer) => (
                <div key={layer.id} className="data-layer-row">
                  <button
                    className={selectedLayer?.id === layer.id ? "data-layer-item active" : "data-layer-item"}
                    onClick={() => onSelectLayer(layer.id)}
                  >
                    <span className="data-layer-symbol" style={{ background: layer.color, borderColor: layer.strokeColor }} />
                    <span><strong>{layer.shortName}</strong><small>{layer.featureCount?.toLocaleString("pt-BR") ?? 0} elementos · {layer.geometry} · {geojsonStateLabel(geojsonStateByLayerId[layer.id])}</small></span>
                    <em className={`layer-status ${layer.status ?? "uploaded"}`}>{statusLabels[layer.status ?? "uploaded"]}</em>
                  </button>
                  {deleteArmedLayerId === layer.id ? (
                    <span className="data-layer-delete-confirm">
                      <button
                        className="text-button danger"
                        type="button"
                        disabled={deleteLayer.isPending}
                        onClick={() => handleDeleteClick(layer.id)}
                      >
                        {deleteLayer.isPending ? "Excluindo…" : "Confirmar"}
                      </button>
                      <button
                        className="text-button"
                        type="button"
                        disabled={deleteLayer.isPending}
                        onClick={() => setDeleteArmedLayerId(null)}
                      >
                        Cancelar
                      </button>
                    </span>
                  ) : (
                    <button
                      className="data-layer-delete-button"
                      type="button"
                      aria-label={`Excluir ${layer.shortName}`}
                      title="Excluir camada"
                      onClick={() => handleDeleteClick(layer.id)}
                    >
                      ×
                    </button>
                  )}
                </div>
              ))}
              {deleteLayer.isError && (
                <div className="layer-runtime-message error" role="alert">
                  <span>{deleteLayer.error.message}</span>
                </div>
              )}
            </aside>

            <section className="data-attributes panel-surface" aria-label="Atributos da camada selecionada">
              <div className="panel-heading">
                <div><span className="eyebrow">Camada selecionada</span><h2>{selectedLayer?.shortName ?? "Camada"}</h2></div>
                {selectedLayer?.sourceFilename && <span className="source-file">{selectedLayer.sourceFilename}</span>}
              </div>
              {selectedLayer && geojsonStateByLayerId[selectedLayer.id]?.status === "error" && (
                <div className="layer-runtime-message error" role="alert">
                  <span>{geojsonStateByLayerId[selectedLayer.id].error?.message ?? "A geometria da camada não pôde ser carregada."}</span>
                  <button className="text-button" onClick={() => void onRetryLayer(selectedLayer.id)}>Tentar novamente</button>
                </div>
              )}
              {selectedLayer && geojsonStateByLayerId[selectedLayer.id]?.status === "stale" && (
                <div className="layer-runtime-message warning" role="status">
                  <span>O mapa mantém a última geometria carregada, mas a atualização falhou.</span>
                  <button className="text-button" onClick={() => void onRetryLayer(selectedLayer.id)}>Atualizar novamente</button>
                </div>
              )}
              {selectedLayer && geojsonStateByLayerId[selectedLayer.id]?.status === "loading" && (
                <div className="layer-runtime-message">Carregando geometrias para o mapa…</div>
              )}
              {selectedLayer && geojsonStateByLayerId[selectedLayer.id]?.status === "empty" && (
                <div className="layer-runtime-message empty">A camada existe, mas não possui geometrias para visualizar.</div>
              )}
              {attributesError ? (
                <div className="integration-state error"><strong>Atributos indisponíveis.</strong><span>{attributesError.message}</span></div>
              ) : attributesLoading ? (
                <div className="integration-state">Lendo campos e estatísticas…</div>
              ) : attributes ? (
                <>
                  <div className="attribute-summary">
                    <span><b>{attributes.feature_count.toLocaleString("pt-BR")}</b> elementos</span>
                    <span><b>{attributes.fields.length}</b> campos analisados</span>
                    <span><b>{attributes.compatible_indicators.length}</b> indicadores compatíveis</span>
                  </div>
                  <div className="attribute-table" role="table" aria-label="Campos disponíveis">
                    <div className="attribute-row header" role="row"><span>Campo</span><span>Origem</span><span>Tipo</span><span>Representação</span><span>Valor</span></div>
                    {attributes.fields.map((field) => (
                      <div className="attribute-row" role="row" key={`${field.origin}-${field.field}`}>
                        <strong>{field.field}</strong>
                        <span>{field.origin === "mapped" ? "Mapeado" : "Fonte"}</span>
                        <span>{field.detected_type}</span>
                        <span>{field.recommended_mode ?? field.unsuitable_reason ?? "Estilo único"}</span>
                        <span className="attribute-value-cell" title={sampleValueLabel(attributes.sample_values[field.field])}>
                          {sampleValueLabel(attributes.sample_values[field.field])}
                        </span>
                      </div>
                    ))}
                  </div>
                </>
              ) : (
                <div className="integration-state empty">Selecione uma camada para consultar seus atributos.</div>
              )}
            </section>
          </div>
        </>
      )}
    </div>
  );
}

function sampleValueLabel(values: string[] | undefined): string {
  if (!values || values.length === 0) return "—";
  return values.length > 1 ? `${values[0]} (+${values.length - 1})` : values[0];
}

function geojsonStateLabel(state: LayerGeojsonViewState | undefined): string {
  if (!state || state.status === "loading") return "mapa carregando";
  if (state.status === "error") return "mapa com erro";
  if (state.status === "stale") return "mapa desatualizado";
  if (state.status === "empty") return "sem geometrias";
  return state.isRefreshing ? "mapa atualizando" : "mapa pronto";
}
