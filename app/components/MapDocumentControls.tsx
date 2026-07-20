"use client";

import type {
  MapDocument,
  MapDocumentWithWarnings,
} from "../features/map-documents/api/mapDocuments";

interface MapDocumentControlsProps {
  documents: MapDocument[];
  activeDocumentId: string | null;
  activeRevision: number | null;
  name: string;
  hasUnsavedChanges: boolean;
  lastSavedAt: string | null;
  integrityWarnings: MapDocumentWithWarnings["integrity_warnings"];
  conflictDocument: MapDocument | null;
  isLoading: boolean;
  isSaving: boolean;
  isOpening: boolean;
  isDeleting: boolean;
  deleteArmed: boolean;
  error: Error | null;
  onNameChange: (name: string) => void;
  onOpen: (documentId: string) => void;
  onNew: () => void;
  onSave: () => void;
  onDelete: () => void;
  onCancelDelete: () => void;
  onLoadConflict: () => void;
  onKeepConflictAsCopy: () => void;
}

export default function MapDocumentControls({
  documents,
  activeDocumentId,
  activeRevision,
  name,
  hasUnsavedChanges,
  lastSavedAt,
  integrityWarnings,
  conflictDocument,
  isLoading,
  isSaving,
  isOpening,
  isDeleting,
  deleteArmed,
  error,
  onNameChange,
  onOpen,
  onNew,
  onSave,
  onDelete,
  onCancelDelete,
  onLoadConflict,
  onKeepConflictAsCopy,
}: MapDocumentControlsProps) {
  const busy = isSaving || isOpening || isDeleting;
  return (
    <div className="map-document-controls">
      <div className="document-picker">
        <label htmlFor="map-document">Composição salva</label>
        <div className="document-picker-row">
          <select
            id="map-document"
            value={activeDocumentId ?? ""}
            onChange={(event) => event.target.value && onOpen(event.target.value)}
            disabled={isLoading || busy || documents.length === 0}
          >
            <option value="">{isLoading ? "Carregando…" : documents.length ? "Rascunho ainda não salvo" : "Nenhuma composição salva"}</option>
            {documents.map((document) => (
              <option key={document.id} value={document.id}>
                {document.name} · r{document.revision}
              </option>
            ))}
          </select>
          <button className="text-button" type="button" onClick={onNew} disabled={busy}>Nova</button>
        </div>
      </div>

      <div className="document-title-field">
        <label htmlFor="document-name">Nome da composição</label>
        <input
          id="document-name"
          value={name}
          onChange={(event) => onNameChange(event.target.value)}
          disabled={busy}
        />
      </div>

      <div className="document-actions">
        <span className={hasUnsavedChanges ? "save-state pending" : "save-state"}>
          {isSaving
            ? "Salvando…"
            : hasUnsavedChanges
              ? "Alterações não salvas"
              : activeRevision
                ? `Revisão ${activeRevision}${lastSavedAt ? ` · salva às ${lastSavedAt}` : ""}`
                : "Rascunho local"}
        </span>
        <button className="secondary-button" type="button" onClick={onSave} disabled={busy || !name.trim()}>
          {activeDocumentId ? "Salvar alterações" : "Criar composição"}
        </button>
        {activeDocumentId && !deleteArmed && (
          <button className="text-button danger" type="button" onClick={onDelete} disabled={busy}>Excluir</button>
        )}
        {activeDocumentId && deleteArmed && (
          <span className="delete-confirmation" role="alert">
            <span>Excluir definitivamente?</span>
            <button className="text-button danger" type="button" onClick={onDelete} disabled={busy}>Confirmar</button>
            <button className="text-button" type="button" onClick={onCancelDelete}>Cancelar</button>
          </span>
        )}
      </div>

      {error && <div className="document-message error" role="alert"><strong>Não foi possível sincronizar.</strong><span>{error.message}</span></div>}
      {integrityWarnings.length > 0 && (
        <div className="document-message warning" role="status">
          <strong>{integrityWarnings.length} referência{integrityWarnings.length > 1 ? "s exigem" : " exige"} atenção</strong>
          <span>O documento foi aberto sem correções automáticas. Revise as camadas indicadas antes de salvar.</span>
          <ul>{integrityWarnings.map((warning) => <li key={`${warning.layer_id}-${warning.code}`}>{warning.message}</li>)}</ul>
        </div>
      )}
      {conflictDocument && (
        <div className="document-message conflict" role="alert">
          <div><strong>Existe uma revisão mais recente no servidor.</strong><span>Seu rascunho local foi preservado e não será sobrescrito automaticamente.</span></div>
          <div className="conflict-actions">
            <button className="secondary-button" type="button" onClick={onKeepConflictAsCopy}>Manter como nova cópia</button>
            <button className="text-button" type="button" onClick={onLoadConflict}>Carregar revisão {conflictDocument.revision}</button>
          </div>
        </div>
      )}
    </div>
  );
}
