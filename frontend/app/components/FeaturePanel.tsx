import { useMemo } from "react";

import type { CatalogIndicator } from "../features/catalog/api/listCatalogIndicators";
import {
  buildFeatureIndicatorRows,
  selectFeatureProperties,
} from "../features/feature-panel/model/featurePanel";
import type { IndicatorResult } from "../features/results/api/listProjectResults";
import type { AppError } from "../lib/errors";
import type { LayerStyleConfig } from "../lib/types";
import type { SelectedFeature } from "../store/useWorkspaceStore";

interface FeaturePanelProps {
  feature: SelectedFeature;
  layer: LayerStyleConfig;
  catalog: CatalogIndicator[];
  results: IndicatorResult[];
  compatibleIndicatorCodes: string[];
  isLoading: boolean;
  error: AppError | null;
  onRetry: () => void;
  onClose: () => void;
}

export default function FeaturePanel({
  feature,
  layer,
  catalog,
  results,
  compatibleIndicatorCodes,
  isLoading,
  error,
  onRetry,
  onClose,
}: FeaturePanelProps) {
  const properties = useMemo(
    () => selectFeatureProperties(feature.properties),
    [feature.properties],
  );
  const indicators = useMemo(
    () => buildFeatureIndicatorRows({
      catalog,
      results,
      selectedFeature: feature,
      compatibleIndicatorCodes,
    }),
    [catalog, compatibleIndicatorCodes, feature, results],
  );
  const title = properties.find((property) => ["nome", "name"].includes(property.key.toLowerCase()))
    ?.formattedValue;

  return (
    <aside className="feature-panel" aria-label="Painel da feição">
      <header className="feature-panel-header">
        <div>
          <span className="eyebrow">Painel da feição</span>
          <h3>{title && title !== "Sem dado" ? title : layer.shortName}</h3>
          <span className="feature-panel-id">ID {feature.featureId}</span>
        </div>
        <button className="feature-panel-close" onClick={onClose} aria-label="Fechar painel da feição">×</button>
      </header>

      <div className="feature-panel-body">
        <section className="feature-panel-section">
          <div className="feature-panel-section-heading">
            <h4>Atributos</h4>
            <span>{properties.length}</span>
          </div>
          {properties.length ? (
            <dl className="feature-property-list">
              {properties.map((property) => (
                <div key={property.key}>
                  <dt>{property.label}</dt>
                  <dd className={property.formattedValue === "Sem dado" ? "muted" : ""}>
                    {property.formattedValue}
                  </dd>
                </div>
              ))}
            </dl>
          ) : (
            <p className="feature-panel-empty">Esta feição não possui atributos disponíveis.</p>
          )}
        </section>

        <section className="feature-panel-section">
          <div className="feature-panel-section-heading">
            <h4>Indicadores</h4>
            {!isLoading && !error && <span>{indicators.length}</span>}
          </div>

          {isLoading ? (
            <p className="feature-panel-state" role="status">Consultando resultados do projeto…</p>
          ) : error ? (
            <div className="feature-panel-state error" role="alert">
              <strong>Indicadores indisponíveis</strong>
              <span>{error.message}</span>
              <button className="text-button" onClick={onRetry}>Tentar novamente</button>
            </div>
          ) : indicators.length === 0 ? (
            <p className="feature-panel-empty">Nenhum indicador por feição é compatível com esta camada.</p>
          ) : (
            <div className="feature-indicator-list">
              {indicators.map((indicator) => (
                <details className={`feature-indicator ${indicator.status}`} key={indicator.code}>
                  <summary>
                    <span>
                      <strong>{indicator.displayName}</strong>
                      <small>{indicator.theme}</small>
                    </span>
                    <span className="feature-indicator-value">
                      {indicator.formattedValue}
                      {indicator.status === "available" && indicator.unit && <small>{indicator.unit}</small>}
                    </span>
                  </summary>
                  <div className="feature-indicator-trace">
                    <span>Fórmula {indicator.formulaVersion}</span>
                    {indicator.metricCrs && <span>CRS métrico {indicator.metricCrs}</span>}
                    {indicator.warnings.length > 0 && <span>{indicator.warnings.length} aviso(s) de cálculo</span>}
                  </div>
                </details>
              ))}
            </div>
          )}
        </section>
      </div>

      <footer className="feature-panel-footer">
        <span>Leitura temporária</span>
        <span>Configuração no MapDocument: etapa futura</span>
      </footer>
    </aside>
  );
}
