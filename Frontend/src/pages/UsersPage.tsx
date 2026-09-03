import { type FormEvent, useCallback, useEffect, useState } from "react";
import { createUser, deleteUser, fetchUsers, updateUser } from "../api";
import type { User, UserCreatePayload, UserUpdatePayload } from "../types";
import UserEditorModal, { type EditorState } from "./components/userEditerForm";

const emptyEditor: EditorState = {
  nombre: "",
  apellido: "",
  email: "",
  descripcion: "",
  password: "",
  status: 1,
  startline: "",
  deadline: "",
};

function toInputDate(raw?: string | null): string {
  if (!raw) return "";
  const date = new Date(raw);
  if (Number.isNaN(date.getTime())) return "";
  return date.toISOString().slice(0, 10);
}

function formatDisplayDate(raw?: string | null): string {
  if (!raw) return "-";
  const date = new Date(raw);
  if (Number.isNaN(date.getTime())) return "-";
  return date.toLocaleDateString("es-ES");
}

export default function UsersPage() {
  const [users, setUsers] = useState<User[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [showModal, setShowModal] = useState(false);
  const [editor, setEditor] = useState<EditorState>(emptyEditor);

  const loadUsers = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const data = await fetchUsers();
      setUsers(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "No se pudieron cargar los usuarios");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadUsers();
  }, [loadUsers]);

  const openCreate = () => {
    setEditor(emptyEditor);
    setError("");
    setShowModal(true);
  };

  const openEdit = (user: User) => {
    setEditor({
      id: user.id,
      nombre: user.nombre,
      apellido: user.apellido,
      email: user.email,
      descripcion: user.descripcion,
      password: user.password,
      status: user.status,
      startline: toInputDate(user.startline),
      deadline: toInputDate(user.deadline),
    });
    setError("");
    setShowModal(true);
  };

  const closeModal = () => {
    setShowModal(false);
    setEditor(emptyEditor);
    setError("");
  };

  const onSubmit = async (e: FormEvent) => {
    e.preventDefault();
    if (
      !editor.nombre.trim() ||
      !editor.apellido.trim() ||
      !editor.email.trim() ||
      !editor.descripcion.trim() ||
      !editor.password.trim()
    ) {
      setError("Por favor completa todos los campos obligatorios.");
      return;
    }

    setSaving(true);
    setError("");
    try {
      if (editor.id) {
        const payload: UserUpdatePayload = {
          nombre: editor.nombre.trim(),
          apellido: editor.apellido.trim(),
          email: editor.email.trim(),
          descripcion: editor.descripcion.trim(),
          password: editor.password.trim(),
          status: editor.status,
          startline: editor.startline || null,
          deadline: editor.deadline || null,
        };
        await updateUser(editor.id, payload);
      } else {
        const payload: UserCreatePayload = {
          nombre: editor.nombre.trim(),
          apellido: editor.apellido.trim(),
          email: editor.email.trim(),
          descripcion: editor.descripcion.trim(),
          password: editor.password.trim(),
          status: editor.status,
          startline: editor.startline || null,
          deadline: editor.deadline || null,
        };
        await createUser(payload);
      }
      await loadUsers();
      closeModal();
    } catch (err) {
      setError(err instanceof Error ? err.message : "No se pudo guardar el usuario");
    } finally {
      setSaving(false);
    }
  };

  const onDelete = async (id: number, nombre: string) => {
    if (!window.confirm(`¿Borrar a ${nombre}?`)) return;
    try {
      await deleteUser(id);
      await loadUsers();
    } catch (err) {
      setError(err instanceof Error ? err.message : "No se pudo borrar el usuario");
    }
  };

  return (
    <div className="users-page">
      <div className="users-toolbar">
        <p className="section-label">Gestión de Usuarios</p>
        <button className="primary-btn" onClick={openCreate} type="button">
          + Nuevo usuario
        </button>
        {error && <p className="error-line" style={{ margin: 0 }}>{error}</p>}
      </div>

      {loading ? (
        <p className="muted">Cargando usuarios…</p>
      ) : (
        <div className="users-table-wrapper">
          {users.length === 0 ? (
            <p className="muted" style={{ padding: "18px 14px" }}>
              No hay usuarios. Crea uno con "+ Nuevo usuario".
            </p>
          ) : (
            <table className="users-table">
              <thead>
                <tr>
                  <th>ID</th>
                  <th>Nombre</th>
                  <th>Apellido</th>
                  <th>Email</th>
                  <th>Descripción</th>
                  <th>Estado</th>
                  <th>Fecha Inicio</th>
                  <th>Fecha Vencimiento</th>
                  <th>Acciones</th>
                </tr>
              </thead>
              <tbody>
                {users.map((user) => (
                  <tr key={user.id}>
                    <td>{user.id}</td>
                    <td>{user.nombre}</td>
                    <td>{user.apellido}</td>
                    <td>{user.email}</td>
                    <td>{user.descripcion}</td>
                    <td>{user.status === 1 ? "Activo" : "Inactivo"}</td>
                    <td>{formatDisplayDate(user.startline)}</td>
                    <td>{formatDisplayDate(user.deadline)}</td>
                    <td className="actions-cell">
                      <button
                        className="chip-btn"
                        onClick={() => openEdit(user)}
                        title="Editar"
                        type="button"
                      >
                        ✏️
                      </button>
                      <button
                        className="chip-btn danger"
                        onClick={() => void onDelete(user.id, `${user.nombre} ${user.apellido}`)}
                        title="Borrar"
                        type="button"
                      >
                        🗑️
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      )}

      {showModal && (
        <UserEditorModal
          editor={editor}
          setEditor={setEditor}
          error={error}
          saving={saving}
          onSubmit={onSubmit}
          onClose={closeModal}
        />
      )}
    </div>
  );
}
