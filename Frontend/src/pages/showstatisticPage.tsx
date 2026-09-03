import { useCallback, useEffect, useMemo, useState } from "react";

import { fetchTasksForGantt, fetchUsers, fetchWorksheetRegisters } from "../api";
import { useAuth } from "../auth";
import type { Task, User, WorksheetRegister } from "../types";
import WorksheetStatistic from "./components/worksheetstatistic";

function pad2(value: number): string {
	return String(value).padStart(2, "0");
}

function toMonthValue(date: Date): string {
	return `${date.getFullYear()}-${pad2(date.getMonth() + 1)}`;
}

function buildMonthOptions(): Array<{ value: string; label: string }> {
	const now = new Date();
	const options: Array<{ value: string; label: string }> = [];
	for (let year = 2000; year <= now.getFullYear(); year += 1) {
		const maxMonth = year === now.getFullYear() ? now.getMonth() + 1 : 12;
		for (let month = 1; month <= maxMonth; month += 1) {
			const value = `${year}-${pad2(month)}`;
			options.push({ value, label: value });
		}
	}
	return options.reverse();
}

function formatHours(totalMinutes: number): string {
	const hours = totalMinutes / 60;
	return hours.toLocaleString("es-ES", {
		minimumFractionDigits: 2,
		maximumFractionDigits: 2,
	});
}

export default function ShowStatisticPage() {
	const { user } = useAuth();

	const [records, setRecords] = useState<WorksheetRegister[]>([]);
	const [users, setUsers] = useState<User[]>([]);
	const [tasks, setTasks] = useState<Task[]>([]);
	const [selectedUserId, setSelectedUserId] = useState<number | null>(null);
	const [selectedMonth, setSelectedMonth] = useState<string>(toMonthValue(new Date()));
	const [loading, setLoading] = useState(true);
	const [error, setError] = useState("");

	const monthOptions = useMemo(() => buildMonthOptions(), []);

	const usersSorted = useMemo(() => {
		return [...users].sort((a, b) => {
			const nameA = `${a.nombre} ${a.apellido}`.trim() || a.email;
			const nameB = `${b.nombre} ${b.apellido}`.trim() || b.email;
			return nameA.localeCompare(nameB, "es", { sensitivity: "base" });
		});
	}, [users]);

	const usersById = useMemo(() => {
		return new Map(
			users.map((item) => {
				const fullName = `${item.nombre} ${item.apellido}`.trim();
				return [item.id, fullName || item.email] as const;
			})
		);
	}, [users]);

	const selectedUserLabel = useMemo(() => {
		if (selectedUserId === null) {
			return "Todos los usuarios";
		}
		return usersById.get(selectedUserId) ?? `Usuario #${selectedUserId}`;
	}, [selectedUserId, usersById]);

	const totalMinutes = useMemo(
		() => records.reduce((accumulator, record) => accumulator + record.minutes_spent, 0),
		[records]
	);

	const loadUsers = useCallback(async () => {
		try {
			const usersData = await fetchUsers();
			setUsers(usersData);
			setSelectedUserId((prev) => {
				if (prev !== null && usersData.some((item) => item.id === prev)) {
					return prev;
				}
				if (user && usersData.some((item) => item.id === user.id)) {
					return user.id;
				}
				return null;
			});
		} catch {
			setUsers([]);
		}
	}, [user]);

	const loadRecords = useCallback(async () => {
		setLoading(true);
		setError("");
		try {
			const [year, month] = selectedMonth.split("-").map(Number);
			const items = await fetchWorksheetRegisters({ year, month, user_id: selectedUserId ?? undefined });
			setRecords(items);
		} catch (err) {
			setError(err instanceof Error ? err.message : "No se pudieron cargar las estadisticas");
			setRecords([]);
		} finally {
			setLoading(false);
		}
	}, [selectedMonth, selectedUserId]);

	useEffect(() => {
		void loadUsers();
	}, [loadUsers]);

	useEffect(() => {
		void loadRecords();
	}, [loadRecords]);

	useEffect(() => {
		const userIds = Array.from(new Set(records.map((record) => record.user_id))).filter((id): id is number => typeof id === "number");
		if (userIds.length === 0) {
			setTasks([]);
			return;
		}

		let cancelled = false;

		const loadTasks = async () => {
			try {
				const data = await fetchTasksForGantt({ userIds });
				if (!cancelled) {
					setTasks(data);
				}
			} catch {
				if (!cancelled) {
					setTasks([]);
				}
			}
		};

		void loadTasks();

		return () => {
			cancelled = true;
		};
	}, [records]);

	return (
		<div className="worksheet-page">
			<div className="worksheet-toolbar">
				<p className="section-label">TaskManager · Estadisticas de trabajo</p>

				<label className="worksheet-toolbar-field" htmlFor="show-statistic-user-filter">
					<span>Usuario</span>
					<select
						id="show-statistic-user-filter"
						value={selectedUserId === null ? "all" : String(selectedUserId)}
						onChange={(event) => {
							const value = event.target.value;
							setSelectedUserId(value === "all" ? null : Number(value));
						}}
					>
						<option value="all">Todos los usuarios</option>
						{usersSorted.map((item) => {
							const displayName = `${item.nombre} ${item.apellido}`.trim() || item.email;
							return (
								<option key={item.id} value={String(item.id)}>
									{displayName}
								</option>
							);
						})}
					</select>
				</label>

				<label className="worksheet-toolbar-field" htmlFor="show-statistic-month-filter">
					<span>Mes</span>
					<select
						id="show-statistic-month-filter"
						value={selectedMonth}
						onChange={(event) => setSelectedMonth(event.target.value)}
					>
						{monthOptions.map((option) => (
							<option key={option.value} value={option.value}>
								{option.label}
							</option>
						))}
					</select>
				</label>

				<p className="muted" style={{ margin: 0 }}>
					Horas trabajadas: {formatHours(totalMinutes)} h ({records.length} registros)
				</p>

				{error && <p className="error-line" style={{ margin: 0 }}>{error}</p>}
			</div>

			{loading ? (
				<p className="muted" style={{ margin: 0, padding: "12px" }}>Cargando estadisticas...</p>
			) : (
				<WorksheetStatistic
					records={records}
					tasks={tasks}
					users={users}
					selectedMonth={selectedMonth}
					selectedUserLabel={selectedUserLabel}
				/>
			)}
		</div>
	);
}
