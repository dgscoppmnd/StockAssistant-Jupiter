import type { FormEvent } from "react";
import type { MasterField, MasterRecord } from "../../types";

type Props = {
  title: string;
  fields: MasterField[];
  record: MasterRecord | null;
  values: Record<string, unknown>;
  saving: boolean;
  error: string;
  onChange: (key: string, value: unknown) => void;
  onSubmit: (event: FormEvent) => void;
  onClose: () => void;
};

export default function MasterDataEditorModal({ title, fields, record, values, saving, error, onChange, onSubmit, onClose }: Props) {
  return (
    <div
      className="product-modal-overlay"
      onClick={onClose}
      onKeyDown={(event) => event.key === "Escape" && onClose()}
      role="presentation"
    >
      <div className="product-modal master-modal" onClick={(event) => event.stopPropagation()} role="dialog" aria-modal="true" aria-label={title}>
        <div className="product-modal-header">
          <h3>{record ? `Editar ${title}` : `Nuevo ${title}`}</h3>
          <button className="product-modal-close" onClick={onClose} type="button">×</button>
        </div>

      {error && <p className="error-line">{error}</p>}

        <form className="stack" onSubmit={onSubmit}>
          {fields.map((field) => {
            const inputId = `master-${field.key}`;
            return (
              <div className="master-editor-field" key={field.key}>
                <label className="field-label" htmlFor={inputId}>{field.label}</label>
                {field.type === "textarea" ? (
                  <textarea id={inputId} required={field.required} placeholder={field.placeholder} rows={4} value={String(values[field.key] ?? "")} onChange={(event) => onChange(field.key, event.target.value)} />
                ) : field.type === "checkbox" ? (
                  <label className="master-checkbox" htmlFor={inputId}>
                    <input id={inputId} checked={Boolean(values[field.key])} type="checkbox" onChange={(event) => onChange(field.key, event.target.checked)} />
                    <span>Habilitado</span>
                  </label>
                ) : (
                  <input id={inputId} required={field.required} placeholder={field.placeholder} step={field.type === "decimal" ? "0.000001" : undefined} type={field.type === "decimal" || field.type === "number" ? "number" : "text"} value={String(values[field.key] ?? "")} onChange={(event) => onChange(field.key, event.target.value)} />
                )}
              </div>
            );
          })}
          <div className="actions-row">
            <button className="primary-btn" disabled={saving} type="submit">{saving ? "Guardando..." : record ? "Actualizar" : "Crear"}</button>
            <button className="chip-btn" onClick={onClose} type="button">Cancelar</button>
          </div>
        </form>
      </div>
    </div>
  );
}
