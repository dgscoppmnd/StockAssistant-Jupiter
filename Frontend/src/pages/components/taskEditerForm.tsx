import { type Dispatch, type FormEvent, type SetStateAction, useCallback, useMemo, useRef, useState } from "react";
import ReactQuill from "react-quill";
import "react-quill/dist/quill.snow.css";
import type { Task, User } from "../../types";

export type EditorState = {
	id?: number;
	id_padre?: number | null;
	id_user?: number | null;
	titulo: string;
	contenido: string;
	startline: string;
	deadline: string;
    fecha_completada: string;
	completada: boolean;
};

export const emptyEditor: EditorState = {
	titulo: "",
	contenido: "",
	startline: "",
	deadline: "",
    fecha_completada: "",
	completada: false,
	id_padre: null,
	id_user: null,
};

type TaskEditerFormProps = {
	editor: EditorState;
	tasks: Task[];
	users: User[];
	saving: boolean;
	error: string;
	onClose: () => void;
	onSubmit: (e: FormEvent<HTMLFormElement>) => void;
	onUploadImage: (file: File) => Promise<string>;
	setEditor: Dispatch<SetStateAction<EditorState>>;
};

const quillToolbar = [
        [{ header: [1, 2, false] }],
        ["bold", "italic", "underline", "strike"],
        [{ list: "ordered" }, { list: "bullet" }],
        ["link", "image"],
        ["clean"],
    ];

const quillFormats = [
    "header",
    "bold",
    "italic",
    "underline",
    "strike",
    "list",
    "bullet",
    "link",
    "image",
];

export default function TaskEditerForm({
	editor,
	tasks,
	users,
	saving,
	error,
	onClose,
	onSubmit,
    onUploadImage,
	setEditor,
}: TaskEditerFormProps) {
    const quillRef = useRef<ReactQuill | null>(null);
    const [uploadingImage, setUploadingImage] = useState(false);
    const [uploadError, setUploadError] = useState("");

    const insertImageFromFile = useCallback(
        async (file: File) => {
            setUploadError("");
            setUploadingImage(true);
            try {
                const imageUrl = await onUploadImage(file);
                const editorInstance = quillRef.current?.getEditor();
                if (!editorInstance) {
                    return;
                }

                const range = editorInstance.getSelection(true);
                const index = range ? range.index : editorInstance.getLength();
                editorInstance.insertEmbed(index, "image", imageUrl, "user");
                editorInstance.setSelection(index + 1, 0, "silent");
                setEditor((prev) => ({ ...prev, contenido: editorInstance.root.innerHTML }));
            } catch (uploadErr) {
                setUploadError(uploadErr instanceof Error ? uploadErr.message : "No se pudo subir la imagen.");
            } finally {
                setUploadingImage(false);
            }
        },
        [onUploadImage, setEditor]
    );

    const onToolbarImage = useCallback(() => {
        const input = document.createElement("input");
        input.type = "file";
        input.accept = "image/*";
        input.onchange = () => {
            const selected = input.files?.[0];
            if (!selected) {
                return;
            }
            void insertImageFromFile(selected);
        };
        input.click();
    }, [insertImageFromFile]);

    const quillModules = useMemo(
        () => ({
            toolbar: {
                container: quillToolbar,
                handlers: {
                    image: onToolbarImage,
                },
            },
        }),
        [onToolbarImage]
    );

	return (
		<div className="task-modal" onClick={(e) => e.stopPropagation()} role="dialog" aria-modal="true">
			<div className="task-modal-header">
				{/* <h3>{editor.id ? `Editar tarea #${editor.id}` : "Nueva tarea"}</h3> */}
                <h4>{editor.id ? `Editar tarea` : "Nueva tarea"}</h4>
				<button className="task-modal-close" onClick={onClose} type="button">✕</button>
			</div>

			{error && <p className="error-line">{error}</p>}
            {uploadError && <p className="error-line">{uploadError}</p>}

			<form className="stack" onSubmit={(e) => void onSubmit(e)}>
                <div className="row">
                    <label className="field-label" htmlFor="id_padre">Tarea padre</label>
                    <select
                        id="id_padre"
                        onChange={(e) =>
                            setEditor((p) => ({
                                ...p,
                                id_padre: e.target.value === "" ? null : Number(e.target.value),
                            }))
                        }
                        value={editor.id_padre ?? ""}
                    >
                        <option value="">— Sin padre (raíz) —</option>
                        {tasks
                            .filter((t) => t.id !== editor.id)
                            .map((t) => (
                                <option key={t.id} value={t.id}>{t.titulo}</option>
                            ))}
                    </select>
                </div>
                <div className="row">
                        <label className="field-label" htmlFor="titulo">Título</label>
                        <input
                            id="titulo"
                            maxLength={100}
                            onChange={(e) => setEditor((p) => ({ ...p, titulo: e.target.value }))}
                            required
                            value={editor.titulo}
                        />                           
                </div>
                <div className="row">
                    <div className="col-8 d-flex flex-column">
                        <label className="field-label" htmlFor="id_user">Responsable de la tarea</label>
                        <select
                            id="id_user"
                            onChange={(e) =>
                                setEditor((p) => ({
                                    ...p,
                                    id_user: e.target.value === "" ? null : Number(e.target.value),
                                }))
                            }
                            value={editor.id_user ?? ""}
                        >
                            <option value="">— Sin responsable —</option>
                            {users.map((u) => (
                                <option key={u.id} value={u.id}>{`${u.nombre} ${u.apellido}`.trim() || u.email}</option>
                            ))}
                        </select>                        
                        <label className="field-label" htmlFor="contenido">Contenido</label>
                        <ReactQuill
                            className="task-rich-editor"
                            key={editor.id ?? "new-task"}
                            formats={quillFormats}
                            id="contenido"
                            ref={quillRef}
                            modules={quillModules}
                            onChange={(value) => setEditor((p) => ({ ...p, contenido: value }))}
                            placeholder="Describe la tarea"
                            theme="snow"
                            value={editor.contenido}
                        />
                        {uploadingImage && <p className="muted" style={{ marginTop: "6px" }}>Subiendo imagen...</p>}
                    </div>
                    <div className="col-4">
                        <div className="row">

                        </div>
                        <div className="row">
                            <label className="field-label" htmlFor="startline">Fecha inicio</label>
                            <input
                                id="startline"
                                onChange={(e) => setEditor((p) => ({ ...p, startline: e.target.value }))}
                                type="date"
                                value={editor.startline}
                            />
                        </div>
                        <div className="row">
                            <label className="field-label" htmlFor="deadline">Fecha fin</label>
                            <input
                                id="deadline"
                                onChange={(e) => setEditor((p) => ({ ...p, deadline: e.target.value }))}
                                required
                                type="date"
                                value={editor.deadline}
                            />
                        </div>
                        <div className="row">
                            <label className="field-label" htmlFor="fecha_completada">Fecha completada</label>
                            <input
                                id="fecha_completada"
                                onChange={(e) => setEditor((p) => ({ ...p, fecha_completada: e.target.value }))}
                                type="date"
                                value={editor.fecha_completada}
                            />
                        </div>
                        <div className="row">
                            <label className="toggle-row" htmlFor="completada">
                                <input
                                    checked={editor.completada}
                                    id="completada"
                                    onChange={(e) => setEditor((p) => ({ ...p, completada: e.target.checked }))}
                                    type="checkbox"
                                />
                                Marcar completada
                            </label>                            
                        </div>
                    </div>
                </div>
				<div className="actions-row d-flex justify-content-end gap-2">
                    <button className="primary-btn" disabled={saving || uploadingImage} type="submit">
						{saving ? "Guardando…" : editor.id ? "Actualizar" : "Crear tarea"}
					</button>
					<button className="chip-btn" onClick={onClose} type="button">Cancelar</button>
				</div>
			</form>
		</div>
	);
}
