import { type FormEvent, useEffect, useState } from "react";
import type { Task } from "../../types";

type TaskDateFormValues = {
	startline: string;
	deadline: string;
	fecha_completada: string;
};

type TaskEditDataTaskFormProps = {
	task: Task | null;
	error: string;
	saving: boolean;
	onClose: () => void;
	onSubmit: (values: TaskDateFormValues) => void;
};

function toInputDate(value?: string | null): string {
	if (!value) {
		return "";
	}

	const date = new Date(value);
	if (Number.isNaN(date.getTime())) {
		return "";
	}

	return date.toISOString().slice(0, 10);
}

const emptyValues: TaskDateFormValues = {
	startline: "",
	deadline: "",
	fecha_completada: "",
};

export default function TaskEditDataTaskForm({
	task,
	error,
	saving,
	onClose,
	onSubmit,
}: TaskEditDataTaskFormProps) {
	const [values, setValues] = useState<TaskDateFormValues>(emptyValues);

	useEffect(() => {
		if (!task) {
			setValues(emptyValues);
			return;
		}

		setValues({
			startline: toInputDate(task.startline),
			deadline: toInputDate(task.deadline),
			fecha_completada: toInputDate(task.fecha_completada),
		});
	}, [task]);

	const handleSubmit = (e: FormEvent<HTMLFormElement>) => {
		e.preventDefault();
		onSubmit(values);
	};

	if (!task) {
		return null;
	}

	return (
		<div className="task-modal" onClick={(e) => e.stopPropagation()} role="dialog" aria-modal="true">
			<div className="task-modal-header">
				<h4>Editar fechas de la tarea</h4>
				<button className="task-modal-close" onClick={onClose} type="button">✕</button>
			</div>

			{error && <p className="error-line">{error}</p>}

			<form className="stack" onSubmit={handleSubmit}>
				<div className="row">
					<p className="muted" style={{ margin: 0 }}>
						{`#${task.id} - ${task.titulo}`}
					</p>
				</div>
				<div className="row">
					<label className="field-label" htmlFor="date-startline">Fecha inicio</label>
					<input
						id="date-startline"
						onChange={(e) => setValues((prev) => ({ ...prev, startline: e.target.value }))}
						type="date"
						value={values.startline}
					/>
				</div>
				<div className="row">
					<label className="field-label" htmlFor="date-deadline">Fecha fin</label>
					<input
						id="date-deadline"
						onChange={(e) => setValues((prev) => ({ ...prev, deadline: e.target.value }))}
						required
						type="date"
						value={values.deadline}
					/>
				</div>
				<div className="row">
					<label className="field-label" htmlFor="date-completed">Fecha completada</label>
					<input
						id="date-completed"
						onChange={(e) => setValues((prev) => ({ ...prev, fecha_completada: e.target.value }))}
						type="date"
						value={values.fecha_completada}
					/>
				</div>
				<div className="actions-row d-flex justify-content-end gap-2">
					<button className="primary-btn" disabled={saving} type="submit">
						{saving ? "Guardando…" : "Guardar fechas"}
					</button>
					<button className="chip-btn" onClick={onClose} type="button">Cancelar</button>
				</div>
			</form>
		</div>
	);
}