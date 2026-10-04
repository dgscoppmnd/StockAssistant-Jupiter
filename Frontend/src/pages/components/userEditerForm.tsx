import { useState, type Dispatch, type FormEvent, type SetStateAction } from "react";

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
  const [showPassword, setShowPassword] = useState(false);
  const isEditing = editor.id !== undefined;

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
          <div className="password-input-wrapper">
            <input
              autoComplete="new-password"
              id="password"
              maxLength={100}
              minLength={6}
              onChange={(e) => setEditor((p) => ({ ...p, password: e.target.value }))}
              placeholder={isEditing ? "Dejar vacío para conservar la actual" : "Mínimo 6 caracteres"}
              required={!isEditing}
              type={showPassword ? "text" : "password"}
              value={editor.password}
            />
            <button
              aria-label={showPassword ? "Ocultar contraseña" : "Mostrar contraseña"}
              aria-pressed={showPassword}
              className="password-visibility-button"
              onClick={() => setShowPassword((visible) => !visible)}
              title={showPassword ? "Ocultar contraseña" : "Mostrar contraseña"}
              type="button"
            >
              {showPassword ? (
                <svg aria-hidden="true" viewBox="0 0 24 24">
                  <path d="m3 3 18 18M10.6 10.7a2 2 0 0 0 2.7 2.7M9.9 4.2A10.9 10.9 0 0 1 12 4c5.5 0 9 8 9 8a18.5 18.5 0 0 1-2.1 3.2M6.6 6.6C4.2 8.2 3 12 3 12s3.5 8 9 8a9.8 9.8 0 0 0 4-.9" />
                </svg>
              ) : (
                <svg aria-hidden="true" viewBox="0 0 24 24">
                  <path d="M3 12s3.5-8 9-8 9 8 9 8-3.5 8-9 8-9-8-9-8Z" />
                  <circle cx="12" cy="12" r="3" />
                </svg>
              )}
            </button>
          </div>

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
