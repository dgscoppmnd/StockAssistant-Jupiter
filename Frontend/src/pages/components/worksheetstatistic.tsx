import { useMemo } from "react";

import type { Task, User, WorksheetRegister } from "../../types";

type WorksheetStatisticProps = {
	records: WorksheetRegister[];
	tasks: Task[];
	users: User[];
	selectedMonth: string;
	selectedUserLabel: string;
};

type StatisticRow = {
	key: string;
	client: string;
	taskLabel: string;
	minutes: number;
	cost: number;
};

function pad2(value: number): string {
	return String(value).padStart(2, "0");
}

function formatMinutesToDDHHMM(totalMinutes: number): string {
	const safeMinutes = Math.max(0, totalMinutes);
	const totalHours = Math.floor(safeMinutes / 60);
	const minutes = safeMinutes % 60;
	const days = Math.floor(totalHours / 24);
	const hours = totalHours % 24;
	return `${pad2(days)}:${pad2(hours)}:${pad2(minutes)}`;
}

function formatCost(value: number): string {
	return value.toLocaleString("es-ES", {
		minimumFractionDigits: 2,
		maximumFractionDigits: 2,
	});
}

function buildTaskLabel(relatedTaskId: number | null | undefined, tasksById: Map<number, Task>): string {
	if (!relatedTaskId) {
		return "Sin tarea relacionada";
	}

	const task = tasksById.get(relatedTaskId);
	if (!task) {
		return `Tarea #${relatedTaskId}`;
	}

	return `Tarea #${relatedTaskId} · ${task.titulo}`;
}

export default function WorksheetStatistic({
	records,
	tasks,
	users,
	selectedMonth,
	selectedUserLabel,
}: WorksheetStatisticProps) {
	const tasksById = useMemo(() => new Map(tasks.map((task) => [task.id, task] as const)), [tasks]);
	const userCostById = useMemo(() => new Map(users.map((user) => [user.id, user.costohora] as const)), [users]);

	const rows = useMemo(() => {
		const grouped = new Map<string, StatisticRow>();

		for (const record of records) {
			const normalizedClient = record.client.trim() || "Sin cliente";
			const taskLabel = buildTaskLabel(record.related_task_id, tasksById);
			const key = `${normalizedClient}__${record.related_task_id ?? "none"}`;
			const userHourlyCost = userCostById.get(record.user_id) ?? 0;
			const recordCost = (record.minutes_spent / 60) * userHourlyCost;
			const existing = grouped.get(key);

			if (existing) {
				existing.minutes += record.minutes_spent;
				existing.cost += recordCost;
				continue;
			}

			grouped.set(key, {
				key,
				client: normalizedClient,
				taskLabel,
				minutes: record.minutes_spent,
				cost: recordCost,
			});
		}

		return Array.from(grouped.values()).sort((left, right) => {
			const clientCompare = left.client.localeCompare(right.client, "es", { sensitivity: "base" });
			if (clientCompare !== 0) {
				return clientCompare;
			}
			return left.taskLabel.localeCompare(right.taskLabel, "es", { sensitivity: "base" });
		});
	}, [records, tasksById, userCostById]);

	const totals = useMemo(() => {
		return rows.reduce(
			(accumulator, row) => ({
				minutes: accumulator.minutes + row.minutes,
				cost: accumulator.cost + row.cost,
			}),
			{ minutes: 0, cost: 0 }
		);
	}, [rows]);

	return (
		<section className="worksheet-statistic-shell" aria-label="Resumen mensual de horas trabajadas">
			<div className="worksheet-statistic-header">
				<div>
					<p className="section-label">Worksheet Statistic</p>
					<h3>Resumen mensual por cliente y tarea</h3>
				</div>
				<p className="worksheet-statistic-meta">
					{selectedMonth} · {selectedUserLabel}
				</p>
			</div>

			<div className="worksheet-statistic-table-wrap">
				<table className="worksheet-statistic-table">
					<thead>
						<tr>
							<th scope="col">Cliente</th>
							<th scope="col">Tarea</th>
							<th scope="col">Horas trabajadas</th>
							<th scope="col">Costo</th>
						</tr>
					</thead>
					<tbody>
						{rows.length === 0 ? (
							<tr>
								<td className="worksheet-statistic-empty" colSpan={4}>
									Sin registros para el filtro actual.
								</td>
							</tr>
						) : (
							rows.map((row) => (
								<tr key={row.key}>
									<td>{row.client}</td>
									<td>{row.taskLabel}</td>
									<td>{formatMinutesToDDHHMM(row.minutes)}</td>
									<td>{formatCost(row.cost)}</td>
								</tr>
							))
						)}
					</tbody>
					<tfoot>
						<tr>
							<th colSpan={2} scope="row">Total del mes</th>
							<th>{formatMinutesToDDHHMM(totals.minutes)}</th>
							<th>{formatCost(totals.cost)}</th>
						</tr>
					</tfoot>
				</table>
			</div>
		</section>
	);
}
