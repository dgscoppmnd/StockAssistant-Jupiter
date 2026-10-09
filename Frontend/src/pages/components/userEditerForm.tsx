import type { Dispatch, FormEvent, SetStateAction } from "react";

export type EditorState = {
  id?: number;
  nombre: string;
  apellido: string;
  email: string;
  descripcion: string;
  password: string;
  status: number;
  startline: string;
  deadline: string;
};

type UserEditorModalProps = {
  editor: EditorState;
  setEditor: Dispatch<SetStateAction<EditorState>>;
  error: string;
  saving: boolean;
  onSubmit: (e: FormEvent) => void | Promise<void>;
  onClose: () => void;
};

export default function UserEditorModal({
  editor,
  setEditor,
  error,
  saving,
  onSubmit,
  onClose,
}: UserEditorModalProps) {
  return (
    <div
      className="product-modal-overlay"
      onClick={onClose}
      onKeyDown={(e) => {
        if (e.key === "Escape") onClose();
      }}
      role="presentation"
    >
      <div
        className="product-modal"
        onClick={(e) => e.stopPropagation()}
        role="dialog"
        aria-modal="true"
      >
        <div className="product-modal-header">
          <h3>{editor.id ? `Editar usuario #${editor.id}` : "Nuevo usuario"}</h3>
          <button className="product-modal-close" onClick={onClose} type="button">
            ✕
          </button>
        </div>

        {error && <p className="error-line">{error}</p>}

        <form className="stack" onSubmit={(e) => void onSubmit(e)}>
          <label className="field-label" htmlFor="nombre">
            Nombre
          </label>
          <input
            id="nombre"
            maxLength={100}
            onChange={(e) => setEditor((p) => ({ ...p, nombre: e.target.value }))}
            placeholder="Ej. Juan"
            required
            value={editor.nombre}
          />

          <label className="field-label" htmlFor="apellido">
            Apellido
          </label>
          <input
            id="apellido"
            maxLength={100}
            onChange={(e) => setEditor((p) => ({ ...p, apellido: e.target.value }))}
            placeholder="Ej. Pérez"
            required
            value={editor.apellido}
          />

          <label className="field-label" htmlFor="email">
            Email
          </label>
          <input
            id="email"
            maxLength={100}
            onChange={(e) => setEditor((p) => ({ ...p, email: e.target.value }))}
            placeholder="Ej. juan@ejemplo.com"
            required
            type="email"
            value={editor.email}
          />

          <label className="field-label" htmlFor="descripcion">
            Descripción
          </label>
          <textarea
            id="descripcion"
            maxLength={200}
            onChange={(e) => setEditor((p) => ({ ...p, descripcion: e.target.value }))}
            placeholder="Ej. Gerente de proyectos"
            required
            rows={2}
            value={editor.descripcion}
          />

          <label className="field-label" htmlFor="password">
            Contraseña
          </label>
          <input
            id="password"
            maxLength={100}
            minLength={6}
            onChange={(e) => setEditor((p) => ({ ...p, password: e.target.value }))}
            placeholder="Mínimo 6 caracteres"
            required
            type="password"
            value={editor.password}
          />

          <label className="field-label" htmlFor="status">
            Estado
          </label>
          <select
            id="status"
            onChange={(e) => setEditor((p) => ({ ...p, status: Number(e.target.value) }))}
            value={editor.status}
          >
            <option value="1">Activo</option>
            <option value="0">Inactivo</option>
          </select>

          <label className="field-label" htmlFor="startline">
            Fecha de inicio (opcional)
          </label>
          <input
            id="startline"
            onChange={(e) => setEditor((p) => ({ ...p, startline: e.target.value }))}
            type="date"
            value={editor.startline}
          />

          <label className="field-label" htmlFor="deadline">
            Fecha de vencimiento (opcional)
          </label>
          <input
            id="deadline"
            onChange={(e) => setEditor((p) => ({ ...p, deadline: e.target.value }))}
            type="date"
            value={editor.deadline}
          />

          <div className="actions-row">
            <button className="primary-btn" disabled={saving} type="submit">
              {saving ? "Guardando…" : editor.id ? "Actualizar" : "Crear usuario"}
            </button>
            <button className="chip-btn" onClick={onClose} type="button">
              Cancelar
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
