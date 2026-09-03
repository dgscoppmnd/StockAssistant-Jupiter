import { type FormEvent } from "react";

import type { Task, User } from "../../types";

type WorksheetEditor = {
	id?: number;
	user_id: number | null;
	client: string;
	related_task_id: number | null;
	start_datetime: string;
	end_datetime: string;
	description: string;
};

type WorksheetFormProps = {
	closeModal: () => void;
	error: string;
	saving: boolean;
	editor: WorksheetEditor;
	editorMinutes: number;
	usersSorted: User[];
	pendingTasksFiltered: Task[];
	taskSearch: string;
	setTaskSearch: (value: string) => void;
	setEditor: (updater: (prev: WorksheetEditor) => WorksheetEditor) => void;
	onSubmit: (event: FormEvent) => Promise<void>;
	onDelete: () => Promise<void>;
	minutesToHHMM: (minutes: number) => string;
};

export default function WorksheetForm({
	closeModal,
	error,
	saving,
	editor,
	editorMinutes,
	usersSorted,
	pendingTasksFiltered,
	taskSearch,
	setTaskSearch,
	setEditor,
	onSubmit,
	onDelete,
	minutesToHHMM,
}: WorksheetFormProps) {
	return (
		<div
			className="worksheet-modal-overlay"
			onClick={closeModal}
			onKeyDown={(event) => {
				if (event.key === "Escape") closeModal();
			}}
			role="presentation"
		>
			<div
				className="worksheet-modal"
				onClick={(event) => event.stopPropagation()}
				role="dialog"
				aria-modal="true"
				aria-label="Edicion de registro de tiempo"
			>
				<div className="worksheet-modal-header">
					<h3>Edicion de registro de tiempo</h3>
					<button className="worksheet-modal-close" onClick={closeModal} type="button">
						X
					</button>
				</div>

				{error && <p className="error-line">{error}</p>}

				<form className="worksheet-form" onSubmit={(event) => void onSubmit(event)}>
					<div className="row">
						<div className="col-12 d-flex flex-column">
							<label className="field-label" htmlFor="worksheet-editor-user">Usuario</label>
							<select
								id="worksheet-editor-user"
								value={editor.user_id === null ? "" : String(editor.user_id)}
								onChange={(event) => {
									const value = event.target.value;
									setEditor((prev) => ({
										...prev,
										user_id: value ? Number(value) : null,
										related_task_id: null,
									}));
								}}
								required
							>
								<option value="">Selecciona usuario</option>
								{usersSorted.map((item) => {
									const displayName = `${item.nombre} ${item.apellido}`.trim() || item.email;
									return (
										<option key={item.id} value={String(item.id)}>
											{displayName}
										</option>
									);
								})}
							</select>
						</div>
					</div>
                    <div className="row">
                        <div className="col-12 d-flex flex-column">
							<label className="field-label" htmlFor="worksheet-editor-task-filter">Filtro de tarea pendiente</label>
							<input
								id="worksheet-editor-task-filter"
								onChange={(event) => setTaskSearch(event.target.value)}
								placeholder="Filtrar por titulo"
								value={taskSearch}
							/>

							<label className="field-label" htmlFor="worksheet-editor-task">Tarea relacionada (opcional)</label>
							<select
								id="worksheet-editor-task"
								value={editor.related_task_id === null ? "" : String(editor.related_task_id)}
								onChange={(event) => {
									const value = event.target.value;
									setEditor((prev) => ({ ...prev, related_task_id: value ? Number(value) : null }));
								}}
							>
								<option value="">Sin tarea relacionada</option>
								{pendingTasksFiltered.map((task) => (
									<option key={task.id} value={String(task.id)}>{`#${task.id} ${task.titulo}`}</option>
								))}
							</select>                            
                        </div>
                    </div>                                
					<div className="row">
						<div className="col-6 d-flex flex-column">
							<label className="field-label" htmlFor="worksheet-editor-description">Descripcion de la tarea</label>
							<textarea
								id="worksheet-editor-description"
								maxLength={250}
								onChange={(event) => setEditor((prev) => ({ ...prev, description: event.target.value }))}
								placeholder="Describe el trabajo realizado"
								rows={3}
								value={editor.description}
							/>
						</div>
						<div className="col-6 d-flex flex-column">
							<label className="field-label" htmlFor="worksheet-editor-client">Cliente</label>
							<input
								id="worksheet-editor-client"
								maxLength={200}
								onChange={(event) => setEditor((prev) => ({ ...prev, client: event.target.value }))}
								placeholder="Nombre del cliente"
								required
								value={editor.client}
							/>
							<label className="field-label" htmlFor="worksheet-editor-start">Fecha hora de inicio</label>
							<input
								id="worksheet-editor-start"
								type="datetime-local"
								onChange={(event) => setEditor((prev) => ({ ...prev, start_datetime: event.target.value }))}
								required
								value={editor.start_datetime}
							/>

							<label className="field-label" htmlFor="worksheet-editor-end">Fecha hora de fin</label>
							<input
								id="worksheet-editor-end"
								type="datetime-local"
								onChange={(event) => setEditor((prev) => ({ ...prev, end_datetime: event.target.value }))}
								required
								value={editor.end_datetime}
							/>
							<label className="field-label" htmlFor="worksheet-editor-minutes">Tiempo en horas empleado (hh:mm)</label>
							<input id="worksheet-editor-minutes" readOnly value={minutesToHHMM(editorMinutes)} />
						</div>
					</div>
					<div className="actions-row">
						<button className="primary-btn" disabled={saving} type="submit">
							{editor.id ? "Guardar cambios" : "Crear registro"}
						</button>
						{editor.id && (
							<button className="chip-btn danger" disabled={saving} onClick={() => void onDelete()} type="button">
								Borrar
							</button>
						)}
					</div>
				</form>
			</div>
		</div>
	);
}
