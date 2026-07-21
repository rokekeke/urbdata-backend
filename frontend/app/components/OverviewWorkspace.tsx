"use client";

import { useState, type FormEvent } from "react";

import { useCreateProject, type Project } from "../features/projects";
import { useUploadLayer } from "../features/layers/hooks/useUploadLayer";
import type { ImportProfile, LayerType } from "../features/layers/api/uploadLayer";
import type { ProjectLayer } from "../features/layers/api/listProjectLayers";
import type { AppError } from "../lib/errors";

interface NamedSlot {
  layerType: LayerType;
  label: string;
  description: string;
}

// As tres entradas reais de um projeto (fluxo confirmado com a equipe de
// exportacao): matricula (perimetro), projeto (territorio - subdivisao
// completa por macroarea) e eixos das vias (sistema_viario, ainda pendente
// de entrega na maioria dos projetos de teste). Camadas derivadas (quadras)
// ou menos usadas no inicio de um projeto (uso_solo, equipamentos, ...)
// nao entram aqui - continuam alcancaveis pela API, so nao tem atalho nesta
// tela.
const NAMED_SLOTS: NamedSlot[] = [
  { layerType: "perimetro", label: "Matrícula", description: "Limite do imóvel (perímetro)." },
  {
    layerType: "territorio",
    label: "Projeto",
    description: "Subdivisão territorial completa (lotes, sistema viário, AVL, APP, ACI).",
  },
  {
    layerType: "sistema_viario",
    label: "Eixos das vias",
    description: "Linhas de centro do sistema viário, para a rede de conectividade.",
  },
];

interface OverviewWorkspaceProps {
  projects: Project[];
  projectsLoading: boolean;
  projectsError: AppError | null;
  activeProjectId: string | null;
  activeVersionId: string | null;
  projectLayers: ProjectLayer[];
  onSelectProject: (id: string | null) => void;
  onOpenData: () => void;
}

export default function OverviewWorkspace({
  projects,
  projectsLoading,
  projectsError,
  activeProjectId,
  activeVersionId,
  projectLayers,
  onSelectProject,
  onOpenData,
}: OverviewWorkspaceProps) {
  const [showCreateForm, setShowCreateForm] = useState(false);
  const [newProjectName, setNewProjectName] = useState("");
  const [newProjectMunicipality, setNewProjectMunicipality] = useState("");
  const createProject = useCreateProject();

  async function handleCreateProject(event: FormEvent) {
    event.preventDefault();
    const name = newProjectName.trim();
    if (!name || createProject.isPending) return;
    try {
      const created = await createProject.mutateAsync({
        name,
        municipality: newProjectMunicipality.trim() || null,
      });
      onSelectProject(created.id);
      setNewProjectName("");
      setNewProjectMunicipality("");
      setShowCreateForm(false);
    } catch {
      // o estado de erro do mutation ja fica visivel no formulario
    }
  }

  return (
    <div className="overview-view">
      <header className="workspace-header">
        <div>
          <span className="eyebrow">Projeto</span>
          <h1>Visão geral</h1>
          <p>Selecione um projeto existente, crie um novo ou envie os arquivos de teste.</p>
        </div>
      </header>

      <section className="overview-layout">
        <aside className="overview-projects-panel panel-surface" aria-label="Projetos">
          <div className="panel-heading">
            <div>
              <span className="eyebrow">Projetos</span>
              <h2>Selecionar</h2>
            </div>
            <span className="panel-count">{projects.length}</span>
          </div>

          {projectsError && (
            <div className="diagnostic-global-alert" role="alert">
              <strong>Não foi possível carregar os projetos.</strong>
              <span>{projectsError.message}</span>
            </div>
          )}

          {projectsLoading ? (
            <p className="panel-help">Carregando projetos…</p>
          ) : projects.length === 0 ? (
            <p className="panel-help">Nenhum projeto ainda. Crie o primeiro abaixo.</p>
          ) : (
            <ul className="overview-project-list">
              {projects.map((project) => (
                <li key={project.id}>
                  <button
                    className={project.id === activeProjectId ? "overview-project-card active" : "overview-project-card"}
                    onClick={() => onSelectProject(project.id)}
                  >
                    <strong>{project.name}</strong>
                    <small>{[project.municipality, project.state].filter(Boolean).join(" · ") || "Contexto não informado"}</small>
                  </button>
                </li>
              ))}
            </ul>
          )}

          {!showCreateForm ? (
            <button className="secondary-button" onClick={() => setShowCreateForm(true)}>
              Criar novo projeto
            </button>
          ) : (
            <form className="overview-create-form" onSubmit={(event) => void handleCreateProject(event)}>
              <label className="compact-field">
                <span>Nome do projeto</span>
                <input
                  value={newProjectName}
                  onChange={(event) => setNewProjectName(event.target.value)}
                  placeholder="Ex.: Loteamento Teste"
                  required
                />
              </label>
              <label className="compact-field">
                <span>Município (opcional)</span>
                <input
                  value={newProjectMunicipality}
                  onChange={(event) => setNewProjectMunicipality(event.target.value)}
                />
              </label>
              <div className="overview-form-actions">
                <button type="button" className="text-button" onClick={() => setShowCreateForm(false)}>Cancelar</button>
                <button type="submit" className="primary-button" disabled={!newProjectName.trim() || createProject.isPending}>
                  {createProject.isPending ? "Criando…" : "Criar projeto"}
                </button>
              </div>
              {createProject.isError && (
                <div className="diagnostic-run-feedback error" role="alert">
                  <span>{createProject.error.message}</span>
                </div>
              )}
            </form>
          )}
        </aside>

        <main className="overview-upload-panel panel-surface" aria-label="Envio de arquivos">
          <div className="panel-heading">
            <div>
              <span className="eyebrow">Dados de teste</span>
              <h2>Enviar arquivos</h2>
            </div>
            <span className="panel-count">{projectLayers.length}</span>
          </div>

          {!activeProjectId ? (
            <p className="panel-help">Selecione ou crie um projeto para enviar os arquivos.</p>
          ) : (
            <div className="overview-upload-slots">
              {NAMED_SLOTS.map((slot) => (
                <UploadSlot
                  key={slot.layerType}
                  slot={slot}
                  projectId={activeProjectId}
                  versionId={activeVersionId}
                  existingLayer={projectLayers.find((layer) => layer.layer_type === slot.layerType)}
                  onOpenData={onOpenData}
                />
              ))}
            </div>
          )}
        </main>
      </section>
    </div>
  );
}

function UploadSlot({
  slot,
  projectId,
  versionId,
  existingLayer,
  onOpenData,
}: {
  slot: NamedSlot;
  projectId: string;
  versionId: string | null;
  existingLayer: ProjectLayer | undefined;
  onOpenData: () => void;
}) {
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [isSplitProfile, setIsSplitProfile] = useState(false);
  const [attributesFile, setAttributesFile] = useState<File | null>(null);
  const [attributesJoinKey, setAttributesJoinKey] = useState("");
  const [geometryJoinKey, setGeometryJoinKey] = useState("");
  const upload = useUploadLayer(projectId, versionId);

  const splitFieldsComplete = !isSplitProfile || (attributesFile && attributesJoinKey.trim());

  function resetForm() {
    setSelectedFile(null);
    setAttributesFile(null);
    setAttributesJoinKey("");
    setGeometryJoinKey("");
    setIsSplitProfile(false);
  }

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    if (!selectedFile || !splitFieldsComplete || upload.isPending) return;
    const importProfile: ImportProfile | undefined = isSplitProfile ? "split" : undefined;
    try {
      await upload.mutateAsync({
        layerType: slot.layerType,
        file: selectedFile,
        importProfile,
        attributesFile: isSplitProfile ? (attributesFile ?? undefined) : undefined,
        attributesJoinKey: isSplitProfile ? attributesJoinKey.trim() : undefined,
        geometryJoinKey: isSplitProfile ? geometryJoinKey.trim() || undefined : undefined,
      });
      resetForm();
    } catch {
      // o estado de erro do mutation ja fica visivel abaixo
    }
  }

  const attributesInputId = `attributes-file-${slot.layerType}`;
  const attributesJoinKeyId = `attributes-join-key-${slot.layerType}`;
  const geometryJoinKeyId = `geometry-join-key-${slot.layerType}`;

  return (
    <div className="overview-upload-slot">
      <div className="overview-upload-slot-heading">
        <div>
          <strong>{slot.label}</strong>
          <small>{slot.description}</small>
        </div>
        {existingLayer ? (
          <span className="overview-slot-status filled">{existingLayer.feature_count} elementos</span>
        ) : (
          <span className="overview-slot-status pending">Pendente</span>
        )}
      </div>
      <form className="overview-upload-slot-form" onSubmit={(event) => void handleSubmit(event)}>
        <input
          type="file"
          accept=".geojson,.json,application/geo+json"
          onChange={(event) => setSelectedFile(event.target.files?.[0] ?? null)}
        />

        <label className="overview-split-toggle">
          <input
            type="checkbox"
            checked={isSplitProfile}
            onChange={(event) => setIsSplitProfile(event.target.checked)}
          />
          <span>Os atributos vêm num arquivo CSV separado</span>
        </label>

        {isSplitProfile && (
          <div className="overview-split-fields">
            <label className="compact-field" htmlFor={attributesInputId}>
              <span>Tabela de atributos (CSV)</span>
              <input
                id={attributesInputId}
                type="file"
                accept=".csv,text/csv"
                onChange={(event) => setAttributesFile(event.target.files?.[0] ?? null)}
              />
            </label>
            <label className="compact-field" htmlFor={attributesJoinKeyId}>
              <span>Coluna do CSV usada como chave</span>
              <input
                id={attributesJoinKeyId}
                value={attributesJoinKey}
                onChange={(event) => setAttributesJoinKey(event.target.value)}
                placeholder="Ex.: Name"
                required
              />
            </label>
            <details className="overview-split-advanced">
              <summary>Avançado</summary>
              <label className="compact-field" htmlFor={geometryJoinKeyId}>
                <span>Property do GeoJSON usada como chave (padrão: id da feição)</span>
                <input
                  id={geometryJoinKeyId}
                  value={geometryJoinKey}
                  onChange={(event) => setGeometryJoinKey(event.target.value)}
                  placeholder="Ex.: URBDATA_ID"
                />
              </label>
            </details>
          </div>
        )}

        <button
          type="submit"
          className="secondary-button"
          disabled={!selectedFile || !splitFieldsComplete || upload.isPending}
        >
          {upload.isPending ? "Enviando…" : existingLayer ? "Reenviar" : "Enviar"}
        </button>
      </form>

      {upload.isError && (
        <div className="diagnostic-run-feedback error" role="alert">
          <span>{upload.error.message}</span>
          <ErrorContextLists context={upload.error.context} />
        </div>
      )}

      {upload.isSuccess && (
        <div className="diagnostic-run-feedback success" role="status">
          <span>{upload.data.feature_count} elementos registrados.</span>
          <JoinSummaryDetail joinSummary={upload.data.join_summary} />
          <button className="text-button" onClick={onOpenData}>Ver em Dados</button>
        </div>
      )}
    </div>
  );
}

interface JoinSummaryShape {
  geometry_count: number;
  attribute_count: number;
  matched: number;
}

function JoinSummaryDetail({ joinSummary }: { joinSummary: Record<string, unknown> | null }) {
  if (!joinSummary) return null;
  const summary = joinSummary as unknown as JoinSummaryShape;
  return (
    <span className="overview-join-summary">
      {summary.matched} de {summary.geometry_count} geometrias combinadas com {summary.attribute_count}{" "}
      linhas do CSV.
    </span>
  );
}

// f2.2/f6.1 (nota 53/54): a nota pede a lista explicita de chaves ausentes,
// excedentes e duplicadas na resposta de erro - nao so a frase solta de
// error.message. Generico o suficiente para cobrir qualquer chave de
// contexto com lista nao vazia, sem acoplar a um codigo de erro especifico.
const CONTEXT_LIST_LABELS: Record<string, string> = {
  duplicate_geometry_keys: "Chaves duplicadas na geometria",
  duplicate_attribute_keys: "Chaves duplicadas no CSV",
  missing_geometry_keys: "Chaves do CSV sem geometria correspondente",
  missing_attribute_keys: "Chaves da geometria sem linha correspondente no CSV",
  empty_geometry_feature_indices: "Feições com chave vazia (posição no arquivo)",
  empty_attribute_row_indices: "Linhas do CSV com chave vazia (posição no arquivo)",
};

function ErrorContextLists({ context }: { context: Record<string, unknown> }) {
  const entries = Object.entries(context).filter(
    (entry): entry is [string, unknown[]] => Array.isArray(entry[1]) && entry[1].length > 0,
  );
  if (entries.length === 0) return null;
  return (
    <ul className="overview-error-context-list">
      {entries.map(([key, values]) => (
        <li key={key}>
          <strong>{CONTEXT_LIST_LABELS[key] ?? key}:</strong> {values.join(", ")}
        </li>
      ))}
    </ul>
  );
}
