import { type FormEvent, useCallback, useEffect, useMemo, useState } from "react";

import {
  createWorksheetRegister,
  deleteWorksheetRegister,
  fetchTasksForGantt,
  fetchUsers,
  fetchWorksheetRegisters,
  updateWorksheetRegister,
} from "../api";
import { useAuth } from "../auth";
import WorksheetForm from "./components/worksheetform";
import WorksheetStatistic from "./components/worksheetstatistic";
import type { Task, User, WorksheetRegister, WorksheetRegisterPayload } from "../types";

type WorksheetEditor = {
  id?: number;
  user_id: number | null;
  client: string;
  related_task_id: number | null;
  start_datetime: string;
  end_datetime: string;
  description: string;
};

const WEEKDAY_LABELS = ["Lun", "Mar", "Mie", "Jue", "Vie", "Sab", "Dom"];

const EMPTY_EDITOR: WorksheetEditor = {
  user_id: null,
  client: "",
  related_task_id: null,
  start_datetime: "",
  end_datetime: "",
  description: "",
};

function pad2(value: number): string {
  return String(value).padStart(2, "0");
}

function toMonthValue(date: Date): string {
  return `${date.getFullYear()}-${pad2(date.getMonth() + 1)}`;
}

function toDateKey(date: Date): string {
  return `${date.getFullYear()}-${pad2(date.getMonth() + 1)}-${pad2(date.getDate())}`;
}

function fromDateKeyToDateTime(dateKey: string, hour: number, minutes: number): string {
  return `${dateKey}T${pad2(hour)}:${pad2(minutes)}`;
}

function extractDateTimeParts(raw?: string | null): { dateKey: string; time: string } | null {
  if (!raw) return null;

  const normalized = raw.trim().replace(" ", "T");
  const match = normalized.match(/^(\d{4}-\d{2}-\d{2})T(\d{2}:\d{2})/);
  if (match) {
    return {
      dateKey: match[1],
      time: match[2],
    };
  }

  const date = new Date(raw);
  if (Number.isNaN(date.getTime())) return null;

  return {
    dateKey: `${date.getUTCFullYear()}-${pad2(date.getUTCMonth() + 1)}-${pad2(date.getUTCDate())}`,
    time: `${pad2(date.getUTCHours())}:${pad2(date.getUTCMinutes())}`,
  };
}

function toInputDateTime(raw?: string | null): string {
  const parts = extractDateTimeParts(raw);
  if (!parts) return "";
  return `${parts.dateKey}T${parts.time}`;
}

function toWeekdayOffset(dayIndex: number): number {
  return (dayIndex + 6) % 7;
}

function buildMonthCells(selectedMonth: string): Array<{ key: string; date: Date | null }> {
  const [year, month] = selectedMonth.split("-").map(Number);
  const firstDay = new Date(year, month - 1, 1);
  const firstOffset = toWeekdayOffset(firstDay.getDay());
  const daysInMonth = new Date(year, month, 0).getDate();
  const totalCells = Math.max(28, Math.ceil((firstOffset + daysInMonth) / 7) * 7);

  const cells: Array<{ key: string; date: Date | null }> = [];
  for (let i = 0; i < totalCells; i += 1) {
    const dayNumber = i - firstOffset + 1;
    if (dayNumber < 1 || dayNumber > daysInMonth) {
      cells.push({ key: `empty-${i}`, date: null });
      continue;
    }
    cells.push({ key: `day-${year}-${month}-${dayNumber}`, date: new Date(year, month - 1, dayNumber) });
  }

  return cells;
}

function getMinutesBetween(startValue: string, endValue: string): number {
  const start = new Date(startValue);
  const end = new Date(endValue);
  if (Number.isNaN(start.getTime()) || Number.isNaN(end.getTime())) return 0;
  const diff = Math.floor((end.getTime() - start.getTime()) / 60000);
  return Math.max(diff, 0);
}

function minutesToHHMM(minutes: number): string {
  const safe = Math.max(minutes, 0);
  const hours = Math.floor(safe / 60);
  const mins = safe % 60;
  return `${pad2(hours)}:${pad2(mins)}`;
}

function formatDateTime(raw: string): string {
  const parts = extractDateTimeParts(raw);
  return parts?.time ?? "-";
}

function formatDayHeader(date: Date): string {
  return date.toLocaleDateString("es-ES", {
    day: "2-digit",
    month: "2-digit",
  });
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

export default function WorksheetRegisterPage() {
  const { user } = useAuth();

  const [records, setRecords] = useState<WorksheetRegister[]>([]);
  const [users, setUsers] = useState<User[]>([]);
  const [calendarTasks, setCalendarTasks] = useState<Task[]>([]);
  const [pendingTasks, setPendingTasks] = useState<Task[]>([]);
  const [taskSearch, setTaskSearch] = useState("");
  const [selectedUserId, setSelectedUserId] = useState<number | null>(null);
  const [selectedMonth, setSelectedMonth] = useState<string>(toMonthValue(new Date()));
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [showModal, setShowModal] = useState(false);
  const [editor, setEditor] = useState<WorksheetEditor>(EMPTY_EDITOR);

  const monthOptions = useMemo(() => buildMonthOptions(), []);
  const monthCells = useMemo(() => buildMonthCells(selectedMonth), [selectedMonth]);
  const editorMinutes = useMemo(() => getMinutesBetween(editor.start_datetime, editor.end_datetime), [editor.start_datetime, editor.end_datetime]);

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

  const pendingTasksFiltered = useMemo(() => {
    const needle = taskSearch.trim().toLowerCase();
    if (!needle) return pendingTasks;
    return pendingTasks.filter((task) => task.titulo.toLowerCase().includes(needle));
  }, [pendingTasks, taskSearch]);

  const pendingTasksById = useMemo(() => {
    return new Map(pendingTasks.map((task) => [task.id, task] as const));
  }, [pendingTasks]);

  const calendarTasksById = useMemo(() => {
    return new Map(calendarTasks.map((task) => [task.id, task] as const));
  }, [calendarTasks]);

  const recordsByDate = useMemo(() => {
    const grouped = new Map<string, WorksheetRegister[]>();
    for (const record of records) {
      const key = extractDateTimeParts(record.start_datetime)?.dateKey;
      if (!key) {
        continue;
      }
      if (!grouped.has(key)) {
        grouped.set(key, []);
      }
      grouped.get(key)!.push(record);
    }

    for (const dayRecords of grouped.values()) {
      dayRecords.sort((a, b) => a.start_datetime.localeCompare(b.start_datetime));
    }

    return grouped;
  }, [records]);

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
      setError(err instanceof Error ? err.message : "No se pudieron cargar los registros");
    } finally {
      setLoading(false);
    }
  }, [selectedMonth, selectedUserId]);

  const loadPendingTasks = useCallback(async (userId: number | null) => {
    if (!userId) {
      setPendingTasks([]);
      return;
    }

    try {
      const userTasks = await fetchTasksForGantt({ userIds: [userId] });
      setPendingTasks(userTasks.filter((task) => !task.completada));
    } catch {
      setPendingTasks([]);
    }
  }, []);

  useEffect(() => {
    void loadUsers();
  }, [loadUsers]);

  useEffect(() => {
    void loadRecords();
  }, [loadRecords]);

  useEffect(() => {
    const userIds = Array.from(new Set(records.map((record) => record.user_id))).filter((id): id is number => typeof id === "number");
    if (userIds.length === 0) {
      setCalendarTasks([]);
      return;
    }

    let cancelled = false;
    const loadCalendarTasks = async () => {
      try {
        const tasks = await fetchTasksForGantt({ userIds });
        if (!cancelled) {
          setCalendarTasks(tasks);
        }
      } catch {
        if (!cancelled) {
          setCalendarTasks([]);
        }
      }
    };

    void loadCalendarTasks();

    return () => {
      cancelled = true;
    };
  }, [records]);

  useEffect(() => {
    if (!showModal) return;
    void loadPendingTasks(editor.user_id);
  }, [editor.user_id, loadPendingTasks, showModal]);

  const openCreate = (dateKey: string) => {
    const defaultUserId = selectedUserId ?? user?.id ?? users[0]?.id ?? null;
    setTaskSearch("");
    setEditor({
      ...EMPTY_EDITOR,
      user_id: defaultUserId,
      start_datetime: fromDateKeyToDateTime(dateKey, 9, 0),
      end_datetime: fromDateKeyToDateTime(dateKey, 10, 0),
    });
    setError("");
    setShowModal(true);
  };

  const openEdit = (record: WorksheetRegister) => {
    setTaskSearch("");
    setEditor({
      id: record.id,
      user_id: record.user_id,
      client: record.client,
      related_task_id: record.related_task_id ?? null,
      start_datetime: toInputDateTime(record.start_datetime),
      end_datetime: toInputDateTime(record.end_datetime),
      description: record.description ?? "",
    });
    setError("");
    setShowModal(true);
  };

  const closeModal = () => {
    setShowModal(false);
    setEditor(EMPTY_EDITOR);
    setPendingTasks([]);
    setTaskSearch("");
    setError("");
  };

  const onSubmit = async (event: FormEvent) => {
    event.preventDefault();

    if (!editor.user_id) {
      setError("Selecciona un usuario para el registro.");
      return;
    }
    if (!editor.client.trim()) {
      setError("El cliente es obligatorio.");
      return;
    }
    if (!editor.start_datetime || !editor.end_datetime) {
      setError("Las fechas de inicio y fin son obligatorias.");
      return;
    }
    if (editorMinutes <= 0) {
      setError("La fecha de fin debe ser mayor que la fecha de inicio.");
      return;
    }
    if (editor.description.length > 250) {
      setError("La descripcion no puede superar 250 caracteres.");
      return;
    }

    const payload: WorksheetRegisterPayload = {
      user_id: editor.user_id,
      client: editor.client.trim(),
      related_task_id: editor.related_task_id,
      start_datetime: editor.start_datetime,
      end_datetime: editor.end_datetime,
      description: editor.description.trim(),
    };

    setSaving(true);
    setError("");
    try {
      if (editor.id) {
        await updateWorksheetRegister(editor.id, payload);
      } else {
        await createWorksheetRegister(payload);
      }
      await loadRecords();
      closeModal();
    } catch (err) {
      setError(err instanceof Error ? err.message : "No se pudo guardar el registro");
    } finally {
      setSaving(false);
    }
  };

  const onDelete = async () => {
    if (!editor.id) return;
    if (!window.confirm("¿Borrar este registro de tiempo?")) return;

    setSaving(true);
    setError("");
    try {
      await deleteWorksheetRegister(editor.id);
      await loadRecords();
      closeModal();
    } catch (err) {
      setError(err instanceof Error ? err.message : "No se pudo borrar el registro");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="worksheet-page">
      <div className="worksheet-toolbar">
        <p className="section-label">TaskManager · Worksheet Register</p>
        <label className="worksheet-toolbar-field" htmlFor="worksheet-user-filter">
          <span>Usuario</span>
          <select
            id="worksheet-user-filter"
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

        <label className="worksheet-toolbar-field" htmlFor="worksheet-month-filter">
          <span>Mes</span>
          <select
            id="worksheet-month-filter"
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

        {error && <p className="error-line" style={{ margin: 0 }}>{error}</p>}
      </div>

      <div className="worksheet-calendar-shell">
        <div className="worksheet-weekday-row">
          {WEEKDAY_LABELS.map((label) => (
            <span key={label} className="worksheet-weekday-cell">{label}</span>
          ))}
        </div>

        {loading ? (
          <p className="muted" style={{ margin: 0, padding: "12px" }}>Cargando registros...</p>
        ) : (
          <div className="worksheet-calendar-grid">
            {monthCells.map((cell) => {
              if (!cell.date) {
                return <div key={cell.key} className="worksheet-day-cell worksheet-day-cell-empty" />;
              }

              const dateKey = toDateKey(cell.date);
              const dayRecords = recordsByDate.get(dateKey) ?? [];

              return (
                <div key={cell.key} className="worksheet-day-cell">
                  <div className="worksheet-day-cell-header">
                    <span className="worksheet-day-label">{formatDayHeader(cell.date)}</span>
                    <button className="worksheet-add-btn" onClick={() => openCreate(dateKey)} title="Agregar registro" type="button">
                      +
                    </button>
                  </div>

                  <div className="worksheet-day-list">
                    {dayRecords.length === 0 ? (
                      <p className="worksheet-empty-day">Sin registros</p>
                    ) : (
                      dayRecords.map((record) => {
                        const relatedTask = record.related_task_id
                          ? calendarTasksById.get(record.related_task_id) ?? pendingTasksById.get(record.related_task_id)
                          : undefined;

                        const taskTitle = record.related_task_id
                          ? relatedTask?.titulo
                            ? `Tarea #${record.related_task_id} · ${relatedTask.titulo}`
                            : `Tarea #${record.related_task_id}`
                          : "Sin tarea relacionada";

                        const descriptionTooltip = record.description?.trim()
                          ? `${record.description.trim()}`
                          : "Sin descripcion";

                        return (
                          <button
                            key={record.id}
                            className="worksheet-entry-btn"
                            onClick={() => openEdit(record)}
                            title={descriptionTooltip}
                            type="button"
                          >
                            <div className="worksheet-entry-topline">
                              <span className="worksheet-entry-time">
                                {formatDateTime(record.start_datetime)} - {formatDateTime(record.end_datetime)}
                              </span>
                              <span className="worksheet-entry-duration">{minutesToHHMM(record.minutes_spent)}</span>
                            </div>
                            <span className="worksheet-entry-client">{record.client}</span>
                            <span className="worksheet-entry-task">{taskTitle}</span>
                          </button>
                        );
                      })
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>

      <WorksheetStatistic
        records={records}
        tasks={calendarTasks}
        users={users}
        selectedMonth={selectedMonth}
        selectedUserLabel={selectedUserLabel}
      />

      {showModal && (
        <WorksheetForm
          closeModal={closeModal}
          error={error}
          saving={saving}
          editor={editor}
          editorMinutes={editorMinutes}
          usersSorted={usersSorted}
          pendingTasksFiltered={pendingTasksFiltered}
          taskSearch={taskSearch}
          setTaskSearch={setTaskSearch}
          setEditor={setEditor}
          onSubmit={onSubmit}
          onDelete={onDelete}
          minutesToHHMM={minutesToHHMM}
        />
      )}
    </div>
  );
}
