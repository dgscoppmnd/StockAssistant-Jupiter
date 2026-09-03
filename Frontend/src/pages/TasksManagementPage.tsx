import { type CSSProperties, type ChangeEvent, type FormEvent, useCallback, useEffect, useMemo, useRef, useState } from "react";
import DOMPurify from "dompurify";
import ReactQuill from "react-quill";
import { createPortal } from "react-dom";
import {
  createTask,
  deleteTask,
  fetchTaskChildrenStatusCount,
  fetchTasksForGantt,
  fetchUsers,
  importTasksCsv,
  moveTask,
  uploadTaskImage,
  updateTask,
} from "../api";
import type { Task, TaskChildrenStatusCount, User } from "../types";
import TaskEditerForm, { emptyEditor, type EditorState } from "./components/taskEditerForm";
import TaskEditDataTaskForm from "./components/taskEditDataTaskForm";

const CONTENT_PREVIEW_LENGTH = 80;
const TIMELINE_DAY_WIDTH_PX = 24;
const ONE_DAY_MS = 86_400_000;

function stripHtml(value: string): string {
  return value
    .replace(/<[^>]*>/g, " ")
    .replace(/&nbsp;/gi, " ")
    .replace(/\s+/g, " ")
    .trim();
}

function hasMeaningfulContent(value: string): boolean {
  return stripHtml(value).length > 0;
}

function hasRichMarkup(value: string): boolean {
  return /<[^>]+>/.test(value);
}

function sanitizeTaskContent(value: string): string {
  return DOMPurify.sanitize(value, {
    ADD_DATA_URI_TAGS: ["img"],
  });
}

function extensionFromMimeType(mimeType: string): string {
  switch (mimeType) {
    case "image/png":
      return "png";
    case "image/jpeg":
    case "image/jpg":
      return "jpg";
    case "image/webp":
      return "webp";
    case "image/gif":
      return "gif";
    case "image/svg+xml":
      return "svg";
    default:
      return "bin";
  }
}

async function replaceInlineImagesWithUploadedUrls(contentHtml: string, taskId?: number | null): Promise<string> {
  if (!contentHtml.includes("data:image/")) {
    return contentHtml;
  }

  const parser = new DOMParser();
  const documentRoot = parser.parseFromString(contentHtml, "text/html");
  const images = Array.from(documentRoot.querySelectorAll("img"));

  for (let index = 0; index < images.length; index += 1) {
    const image = images[index];
    const source = image.getAttribute("src") ?? "";
    if (!source.startsWith("data:image/")) {
      continue;
    }

    const blob = await fetch(source).then((response) => response.blob());
    const extension = extensionFromMimeType(blob.type || "");
    const file = new File([blob], `task-inline-${Date.now()}-${index}.${extension}`, {
      type: blob.type || "application/octet-stream",
    });
    const uploaded = await uploadTaskImage(file, taskId);
    image.setAttribute("src", uploaded.url);
    image.removeAttribute("srcset");
  }

  return documentRoot.body.innerHTML;
}

function toInputDate(raw?: string | null): string {
  if (!raw) return "";
  const date = new Date(raw);
  if (Number.isNaN(date.getTime())) return "";
  return date.toISOString().slice(0, 10);
}

function asUnix(value?: string | null): number {
  if (!value) return Number.NaN;
  const ts = new Date(value).getTime();
  return Number.isNaN(ts) ? Number.NaN : ts;
}

function toDayStartTs(ts: number): number {
  const date = new Date(ts);
  date.setHours(0, 0, 0, 0);
  return date.getTime();
}

function getDurationDays(startRaw?: string | null, deadlineRaw?: string | null): string {
  const startTs = asUnix(startRaw);
  const deadlineTs = asUnix(deadlineRaw);

  if (Number.isNaN(startTs) || Number.isNaN(deadlineTs)) {
    return "N/A";
  }

  const startDay = toDayStartTs(startTs);
  const deadlineDay = toDayStartTs(deadlineTs);

  if (deadlineDay < startDay) {
    return "0";
  }

  return String(Math.floor((deadlineDay - startDay) / ONE_DAY_MS) + 1);
}

function getAllDescendantIds(tasks: Task[], parentId: number): Set<number> {
  const result = new Set<number>();
  const queue = [parentId];
  while (queue.length) {
    const id = queue.shift()!;
    for (const t of tasks) {
      if (t.id_padre === id && !result.has(t.id)) {
        result.add(t.id);
        queue.push(t.id);
      }
    }
  }
  return result;
}

type FlatRow = { task: Task; depth: number };

function buildFlatTree(tasks: Task[], collapsed: Set<number>): FlatRow[] {
  const childrenOf = new Map<number | null, Task[]>();
  for (const t of tasks) {
    const key = t.id_padre ?? null;
    if (!childrenOf.has(key)) childrenOf.set(key, []);
    childrenOf.get(key)!.push(t);
  }
  for (const children of childrenOf.values()) {
    children.sort(
      (a, b) =>
        (asUnix(a.startline ?? a.created_at) || 0) -
        (asUnix(b.startline ?? b.created_at) || 0)
    );
  }
  const result: FlatRow[] = [];
  const walk = (parentId: number | null, depth: number) => {
    for (const task of childrenOf.get(parentId) ?? []) {
      result.push({ task, depth });
      if (!collapsed.has(task.id)) walk(task.id, depth + 1);
    }
  };
  walk(null, 0);
  return result;
}

type TimelineSegment = { label: string; width: number; key: string };
type TimelineLayout = {
  totalWidth: number;
  years: TimelineSegment[];
  months: TimelineSegment[];
  days: TimelineSegment[];
};

type TaskActionsMenuState = {
  taskId: number;
  x: number;
  y: number;
  triggerId: string;
};

const TASK_ACTIONS_MENU_WIDTH = 220;
const TASK_ACTIONS_MENU_ESTIMATED_HEIGHT = 210;

function buildTimelineLayout(stats: { min: number; max: number }): TimelineLayout {
  if (!stats.min || !stats.max) {
    return { totalWidth: TIMELINE_DAY_WIDTH_PX, years: [], months: [], days: [] };
  }

  const start = new Date(toDayStartTs(stats.min));
  const end = new Date(toDayStartTs(stats.max));
  if (end < start) {
    return { totalWidth: TIMELINE_DAY_WIDTH_PX, years: [], months: [], days: [] };
  }

  const years: TimelineSegment[] = [];
  const months: TimelineSegment[] = [];
  const days: TimelineSegment[] = [];

  let currentYear: number | null = null;
  let currentYearStart = 0;
  let currentMonthKey: string | null = null;
  let currentMonthStart = 0;
  let index = 0;
  const cur = new Date(start);

  while (cur <= end) {
    const year = cur.getFullYear();
    const month = cur.getMonth();
    const monthKey = `${year}-${month}`;

    if (currentYear === null) {
      currentYear = year;
      currentYearStart = index;
    }
    if (year !== currentYear) {
      years.push({
        label: String(currentYear),
        width: (index - currentYearStart) * TIMELINE_DAY_WIDTH_PX,
        key: `year-${currentYear}`,
      });
      currentYear = year;
      currentYearStart = index;
    }

    if (currentMonthKey === null) {
      currentMonthKey = monthKey;
      currentMonthStart = index;
    }
    if (monthKey !== currentMonthKey) {
      const [prevYear, prevMonth] = currentMonthKey.split("-").map(Number);
      months.push({
        label: new Date(prevYear, prevMonth, 1).toLocaleDateString("es", { month: "short" }) + ` ${currentYear}`,
        width: (index - currentMonthStart) * TIMELINE_DAY_WIDTH_PX,
        key: `month-${currentMonthKey}`,
      });
      currentMonthKey = monthKey;
      currentMonthStart = index;
    }

    days.push({
      label: String(cur.getDate()),
      width: TIMELINE_DAY_WIDTH_PX,
      key: `day-${year}-${month + 1}-${cur.getDate()}`,
    });

    cur.setDate(cur.getDate() + 1);
    index += 1;
  }

  if (currentYear !== null) {
    years.push({
      label: String(currentYear),
      width: (index - currentYearStart) * TIMELINE_DAY_WIDTH_PX,
      key: `year-${currentYear}-last`,
    });
  }
  if (currentMonthKey !== null) {
    const [lastYear, lastMonth] = currentMonthKey.split("-").map(Number);
    months.push({
      label: new Date(lastYear, lastMonth, 1).toLocaleDateString("es", { month: "short" }) + ` ${lastYear}`,
      width: (index - currentMonthStart) * TIMELINE_DAY_WIDTH_PX,
      key: `month-${currentMonthKey}-last`,
    });
  }

  return {
    totalWidth: Math.max(days.length * TIMELINE_DAY_WIDTH_PX, TIMELINE_DAY_WIDTH_PX),
    years,
    months,
    days,
  };
}

function GanttTimelineHeader({ layout }: { layout: TimelineLayout }) {
  return (
    <div className="gantt-timeline-header" style={{ minWidth: `${layout.totalWidth}px` }}>
      <div className="gantt-timeline-row years">
        {layout.years.map((cell) => (
          <span className="gantt-timeline-cell" key={cell.key} style={{ width: `${cell.width}px` }}>
            {cell.label}
          </span>
        ))}
      </div>
      <div className="gantt-timeline-row months">
        {layout.months.map((cell) => (
          <span className="gantt-timeline-cell" key={cell.key} style={{ width: `${cell.width}px` }}>
            {cell.label}
          </span>
        ))}
      </div>
      <div className="gantt-timeline-row days">
        {layout.days.map((cell) => (
          <span className="gantt-timeline-cell" key={cell.key} style={{ width: `${cell.width}px` }}>
            {cell.label}
          </span>
        ))}
      </div>
    </div>
  );
}

export default function TasksManagementPage() {
  const [tasks, setTasks] = useState<Task[]>([]);
  const [users, setUsers] = useState<User[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [collapsed, setCollapsed] = useState<Set<number>>(new Set());
  const [showModal, setShowModal] = useState(false);
  const [showDateModal, setShowDateModal] = useState(false);
  const [editor, setEditor] = useState<EditorState>(emptyEditor);
  const [dateEditorTask, setDateEditorTask] = useState<Task | null>(null);
  const [draggedId, setDraggedId] = useState<number | null>(null);
  const [dropTargetId, setDropTargetId] = useState<number | null>(null);
  const [expandedContentIds, setExpandedContentIds] = useState<Set<number>>(new Set());
  const [isFilterPanelCollapsed, setIsFilterPanelCollapsed] = useState(true);
  const [selectedUserIds, setSelectedUserIds] = useState<Set<number>>(new Set());
  const [dateField, setDateField] = useState<"inicio" | "fin" | "completada">("inicio");
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");
  const [subtaskStatusByTaskId, setSubtaskStatusByTaskId] = useState<Record<number, TaskChildrenStatusCount>>({});
  const [focusTaskId, setFocusTaskId] = useState<number | null>(null);
  const [highlightedTaskId, setHighlightedTaskId] = useState<number | null>(null);
  const [actionsMenu, setActionsMenu] = useState<TaskActionsMenuState | null>(null);
  const csvInputRef = useRef<HTMLInputElement | null>(null);
  const ganttTableRef = useRef<HTMLDivElement | null>(null);
  const taskActionsMenuRef = useRef<HTMLDivElement | null>(null);
  const taskActionsMenuItemRefs = useRef<Array<HTMLButtonElement | null>>([]);
  const pendingMoveScrollRestoreRef = useRef<{
    windowX: number;
    windowY: number;
    tableScrollTop: number;
    tableScrollLeft: number;
  } | null>(null);
  const keepScrollOnNextFocusRef = useRef(false);
  const highlightTimeoutRef = useRef<number | null>(null);

  const selectedUserIdsArray = useMemo(() => Array.from(selectedUserIds), [selectedUserIds]);

  const loadTasks = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      setTasks(
        await fetchTasksForGantt({
          userIds: selectedUserIdsArray,
          dateFrom: dateFrom || undefined,
          dateTo: dateTo || undefined,
          dateField,
        })
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : "No se pudieron cargar las tareas");
    } finally {
      setLoading(false);
    }
  }, [selectedUserIdsArray, dateField, dateFrom, dateTo]);

  const loadUsers = useCallback(async () => {
    try {
      setUsers(await fetchUsers());
    } catch {
      setUsers([]);
    }
  }, []);

  useEffect(() => {
    void loadTasks();
  }, [loadTasks]);

  useEffect(() => {
    void loadUsers();
  }, [loadUsers]);

  useEffect(() => {
    let cancelled = false;

    if (!tasks.length) {
      setSubtaskStatusByTaskId({});
      return;
    }

    const loadSubtaskStatuses = async () => {
      const results = await Promise.allSettled(
        tasks.map(async (task) => ({
          taskId: task.id,
          status: await fetchTaskChildrenStatusCount(task.id),
        }))
      );

      if (cancelled) return;

      const next: Record<number, TaskChildrenStatusCount> = {};
      for (const result of results) {
        if (result.status === "fulfilled") {
          next[result.value.taskId] = result.value.status;
        }
      }
      setSubtaskStatusByTaskId(next);
    };

    void loadSubtaskStatuses();

    return () => {
      cancelled = true;
    };
  }, [tasks]);

  useEffect(() => {
    if (loading) {
      return;
    }

    const pending = pendingMoveScrollRestoreRef.current;
    if (!pending) {
      return;
    }

    window.scrollTo(pending.windowX, pending.windowY);
    if (ganttTableRef.current) {
      ganttTableRef.current.scrollTop = pending.tableScrollTop;
      ganttTableRef.current.scrollLeft = pending.tableScrollLeft;
    }

    keepScrollOnNextFocusRef.current = true;
    pendingMoveScrollRestoreRef.current = null;
  }, [tasks, loading]);

  useEffect(() => {
    return () => {
      if (highlightTimeoutRef.current !== null) {
        window.clearTimeout(highlightTimeoutRef.current);
      }
    };
  }, []);

  useEffect(() => {
    if (!actionsMenu) {
      return;
    }

    const closeOnPointerDown = (event: PointerEvent) => {
      const target = event.target;
      if (!(target instanceof Node)) {
        setActionsMenu(null);
        return;
      }

      const trigger = document.getElementById(actionsMenu.triggerId);
      if (
        taskActionsMenuRef.current?.contains(target) ||
        (trigger && trigger.contains(target))
      ) {
        return;
      }

      setActionsMenu(null);
    };

    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        setActionsMenu(null);
      }
    };

    const closeOnViewportChange = () => {
      setActionsMenu(null);
    };

    document.addEventListener("pointerdown", closeOnPointerDown);
    document.addEventListener("keydown", closeOnEscape);
    window.addEventListener("scroll", closeOnViewportChange, true);
    window.addEventListener("resize", closeOnViewportChange);

    return () => {
      document.removeEventListener("pointerdown", closeOnPointerDown);
      document.removeEventListener("keydown", closeOnEscape);
      window.removeEventListener("scroll", closeOnViewportChange, true);
      window.removeEventListener("resize", closeOnViewportChange);
    };
  }, [actionsMenu]);

  useEffect(() => {
    if (!actionsMenu) {
      return;
    }

    const focusTimer = window.setTimeout(() => {
      taskActionsMenuItemRefs.current[0]?.focus();
    }, 0);

    return () => {
      window.clearTimeout(focusTimer);
    };
  }, [actionsMenu]);

  useEffect(() => {
    if (focusTaskId === null) {
      return;
    }

    if (saving || loading) {
      return;
    }

    let cancelled = false;
    let attempts = 0;
    const maxAttempts = 8;

    const restoreFocus = () => {
      if (cancelled) {
        return;
      }

      const target = document.querySelector<HTMLButtonElement>(
        `button[data-task-complete-id="${focusTaskId}"]`
      );

      if (target && !target.disabled) {
        const preserveScroll = keepScrollOnNextFocusRef.current;
        target.focus({ preventScroll: preserveScroll });
        if (!preserveScroll) {
          target.scrollIntoView({ block: "nearest", inline: "nearest" });
        } else {
          setHighlightedTaskId(focusTaskId);
          if (highlightTimeoutRef.current !== null) {
            window.clearTimeout(highlightTimeoutRef.current);
          }
          highlightTimeoutRef.current = window.setTimeout(() => {
            setHighlightedTaskId(null);
            highlightTimeoutRef.current = null;
          }, 1000);
        }
        keepScrollOnNextFocusRef.current = false;
        setFocusTaskId(null);
        return;
      }

      attempts += 1;
      if (attempts >= maxAttempts) {
        setFocusTaskId(null);
        return;
      }

      window.setTimeout(restoreFocus, 40);
    };

    const firstAttempt = window.setTimeout(restoreFocus, 0);

    return () => {
      cancelled = true;
      window.clearTimeout(firstAttempt);
    };
  }, [tasks, focusTaskId, saving, loading]);

  const flatRows = useMemo(() => buildFlatTree(tasks, collapsed), [tasks, collapsed]);

  const usersById = useMemo(() => {
    return new Map(
      users.map((user) => {
        const fullName = `${user.nombre} ${user.apellido}`.trim();
        return [user.id, fullName || user.email] as const;
      })
    );
  }, [users]);

  const usersSorted = useMemo(() => {
    return [...users].sort((a, b) => {
      const nameA = `${a.nombre} ${a.apellido}`.trim() || a.email;
      const nameB = `${b.nombre} ${b.apellido}`.trim() || b.email;
      return nameA.localeCompare(nameB, "es", { sensitivity: "base" });
    });
  }, [users]);

  const timelineStats = useMemo(() => {
    if (!tasks.length) return { min: 0, max: 1, span: 1, dayMin: 0, dayMax: 0, totalDays: 1 };
    const starts = tasks.map((t) => asUnix(t.startline ?? t.created_at)).filter((v) => !Number.isNaN(v));
    const ends = tasks.map((t) => asUnix(t.deadline)).filter((v) => !Number.isNaN(v));
    if (!starts.length || !ends.length) {
      return { min: 0, max: 1, span: 1, dayMin: 0, dayMax: 0, totalDays: 1 };
    }
    const dayMin = toDayStartTs(Math.min(...starts));
    const dayMax = toDayStartTs(Math.max(...ends));
    const min = dayMin;
    const max = dayMax + ONE_DAY_MS;
    const span = Math.max(max - min, ONE_DAY_MS);
    const totalDays = Math.max(Math.floor((dayMax - dayMin) / ONE_DAY_MS) + 1, 1);
    return { min, max, span, dayMin, dayMax, totalDays };
  }, [tasks]);

  const timelineLayout = useMemo(() => buildTimelineLayout(timelineStats), [timelineStats]);

  const ganttTableStyle = useMemo(
    () =>
      ({
        "--timeline-days": `${timelineStats.totalDays}`,
        "--timeline-day-width": `${TIMELINE_DAY_WIDTH_PX}px`,
      }) as CSSProperties,
    [timelineStats.totalDays]
  );

  const hasChildren = useCallback((id: number) => tasks.some((t) => t.id_padre === id), [tasks]);

  const parentTaskIds = useMemo(() => {
    const parentIds = new Set<number>();
    for (const task of tasks) {
      if (task.id_padre != null) {
        parentIds.add(task.id_padre);
      }
    }
    return parentIds;
  }, [tasks]);

  const collapseAllParents = () => {
    setCollapsed(new Set(parentTaskIds));
  };

  const expandAllTasks = () => {
    setCollapsed(new Set());
  };

  const isAnyUserFilterApplied = selectedUserIds.size > 0;
  const isAnyDateFilterApplied = Boolean(dateFrom || dateTo);
  const isAnyFilterApplied = isAnyUserFilterApplied || isAnyDateFilterApplied;

  const toggleUserFilter = (userId: number) => {
    setSelectedUserIds((prev) => {
      const next = new Set(prev);
      if (next.has(userId)) {
        next.delete(userId);
      } else {
        next.add(userId);
      }
      return next;
    });
  };

  const clearFilters = () => {
    setSelectedUserIds(new Set());
    setDateFrom("");
    setDateTo("");
  };

  const openCreate = (idPadre?: number | null) => {
    setEditor({ ...emptyEditor, id_padre: idPadre ?? null });
    setError("");
    setShowModal(true);
  };

  const openEdit = (task: Task) => {
    setEditor({
      id: task.id,
      id_padre: task.id_padre ?? null,
      id_user: task.id_user ?? null,
      titulo: task.titulo,
      contenido: task.contenido,
      startline: toInputDate(task.startline),
      deadline: toInputDate(task.deadline),
        fecha_completada: toInputDate(task.fecha_completada),
      completada: task.completada,
    });
    setError("");
    setShowModal(true);
  };

  const openDateEdit = (task: Task) => {
    setDateEditorTask(task);
    setError("");
    setShowDateModal(true);
  };

  const closeModal = () => {
    setShowModal(false);
    setEditor(emptyEditor);
    setError("");
  };

  const closeDateModal = () => {
    setShowDateModal(false);
    setDateEditorTask(null);
    setError("");
  };

  const onUploadImage = useCallback(
    async (file: File): Promise<string> => {
      const uploaded = await uploadTaskImage(file, editor.id ?? null);
      return uploaded.url;
    },
    [editor.id]
  );

  const onSubmit = async (e: FormEvent) => {
    e.preventDefault();
    if (!editor.titulo.trim() || !hasMeaningfulContent(editor.contenido) || !editor.deadline) {
      setError("Completa título, contenido y fecha fin.");
      return;
    }
    setSaving(true);
    setError("");
    try {
      const normalizedContent = await replaceInlineImagesWithUploadedUrls(editor.contenido.trim(), editor.id ?? null);

      if (editor.id) {
        const previousTask = tasks.find((task) => task.id === editor.id);
        const previousParentId = previousTask?.id_padre ?? null;

        const updatedTask = await updateTask(editor.id, {
          titulo: editor.titulo.trim(),
          contenido: normalizedContent,
          startline: editor.startline || null,
          deadline: editor.deadline,
          fecha_completada: editor.fecha_completada || null,
          completada: editor.completada,
          id_padre: editor.id_padre,
          id_user: editor.id_user,
        });

        const nextParentId = updatedTask.id_padre ?? null;
        const parentChanged = previousParentId !== nextParentId;

        if (parentChanged) {
          setFocusTaskId(updatedTask.id);
          await loadTasks();
        } else {
          setTasks((prev) => prev.map((item) => (item.id === updatedTask.id ? updatedTask : item)));
        }
      } else {
        await createTask({
          titulo: editor.titulo.trim(),
          contenido: normalizedContent,
          startline: editor.startline || null,
          deadline: editor.deadline,
          fecha_completada: editor.fecha_completada || null,
          id_padre: editor.id_padre,
          id_user: editor.id_user,
        });
        await loadTasks();
      }
      closeModal();
    } catch (err) {
      setError(err instanceof Error ? err.message : "No se pudo guardar la tarea");
    } finally {
      setSaving(false);
    }
  };

  const onDelete = async (id: number) => {
    if (!window.confirm("¿Borrar esta tarea?")) return;
    try {
      await deleteTask(id);
      await loadTasks();
    } catch (err) {
      setError(err instanceof Error ? err.message : "No se pudo borrar la tarea");
    }
  };

  const onToggleCompleted = async (task: Task) => {
    const nextCompleted = !task.completada;
    const today = new Date().toISOString().slice(0, 10);

    setFocusTaskId(task.id);
    setSaving(true);
    setError("");
    try {
      const updatedTask = await updateTask(task.id, {
        titulo: task.titulo.trim(),
        contenido: task.contenido.trim(),
        startline: task.startline ?? null,
        deadline: task.deadline,
        fecha_completada: nextCompleted ? (task.fecha_completada ?? today) : null,
        completada: nextCompleted,
        id_padre: task.id_padre ?? null,
        id_user: task.id_user ?? null,
      });
      setTasks((prev) => prev.map((item) => (item.id === updatedTask.id ? updatedTask : item)));
    } catch (err) {
      setError(err instanceof Error ? err.message : "No se pudo actualizar el estado de la tarea");
    } finally {
      setSaving(false);
    }
  };

  const onSubmitDateEdit = async (values: { startline: string; deadline: string; fecha_completada: string }) => {
    if (!dateEditorTask) {
      return;
    }

    setSaving(true);
    setError("");

    try {
      const updatedTask = await updateTask(dateEditorTask.id, {
        titulo: dateEditorTask.titulo.trim(),
        contenido: dateEditorTask.contenido.trim(),
        startline: values.startline || null,
        deadline: values.deadline,
        fecha_completada: values.fecha_completada || null,
        completada: dateEditorTask.completada,
        id_padre: dateEditorTask.id_padre ?? null,
        id_user: dateEditorTask.id_user ?? null,
      });

      setTasks((prev) => prev.map((item) => (item.id === updatedTask.id ? updatedTask : item)));
      closeDateModal();
    } catch (err) {
      setError(err instanceof Error ? err.message : "No se pudieron actualizar las fechas de la tarea");
    } finally {
      setSaving(false);
    }
  };

  const toggleCollapse = (id: number) => {
    setCollapsed((prev) => {
      const next = new Set(prev);
      next.has(id) ? next.delete(id) : next.add(id);
      return next;
    });
  };

  const toggleContent = (id: number) => {
    setExpandedContentIds((prev) => {
      const next = new Set(prev);
      next.has(id) ? next.delete(id) : next.add(id);
      return next;
    });
  };

  const onDragEnd = () => {
    setDraggedId(null);
    setDropTargetId(null);
  };

  const onDrop = async (e: React.DragEvent, targetId: number | null) => {
    e.preventDefault();
    if (draggedId === null || draggedId === targetId) { onDragEnd(); return; }
    if (targetId !== null) {
      const descendants = getAllDescendantIds(tasks, draggedId);
      if (descendants.has(targetId)) { onDragEnd(); return; }
    }

    const draggedTask = tasks.find((task) => task.id === draggedId);
    const currentParentId = draggedTask?.id_padre ?? null;
    if (currentParentId === targetId) {
      onDragEnd();
      return;
    }

    const tableEl = ganttTableRef.current;
    pendingMoveScrollRestoreRef.current = {
      windowX: window.scrollX,
      windowY: window.scrollY,
      tableScrollTop: tableEl?.scrollTop ?? 0,
      tableScrollLeft: tableEl?.scrollLeft ?? 0,
    };
    setFocusTaskId(draggedId);

    try {
      await moveTask(draggedId, targetId);
      await loadTasks();
    } catch (err) {
      pendingMoveScrollRestoreRef.current = null;
      keepScrollOnNextFocusRef.current = false;
      setFocusTaskId(null);
      setError(err instanceof Error ? err.message : "No se pudo mover la tarea");
    }
    onDragEnd();
  };

  const onImportClick = () => {
    csvInputRef.current?.click();
  };

  const closeActionsMenu = () => {
    setActionsMenu(null);
  };

  const openActionsMenu = (taskId: number, triggerElement: HTMLButtonElement) => {
    const rect = triggerElement.getBoundingClientRect();
    const viewportPadding = 8;
    const openDownward = rect.bottom + TASK_ACTIONS_MENU_ESTIMATED_HEIGHT <= window.innerHeight - viewportPadding;
    const rawLeft = rect.right - TASK_ACTIONS_MENU_WIDTH;
    const x = Math.max(
      viewportPadding,
      Math.min(rawLeft, window.innerWidth - TASK_ACTIONS_MENU_WIDTH - viewportPadding)
    );
    const y = openDownward
      ? rect.bottom + 6
      : Math.max(viewportPadding, rect.top - TASK_ACTIONS_MENU_ESTIMATED_HEIGHT - 6);

    setActionsMenu({
      taskId,
      x,
      y,
      triggerId: triggerElement.id,
    });
  };

  const onDuplicateTask = async (task: Task) => {
    setSaving(true);
    setError("");

    try {
      const normalizedContent = await replaceInlineImagesWithUploadedUrls(task.contenido.trim(), task.id);

      await createTask({
        titulo: `${task.titulo.trim()} (copia)`,
        contenido: normalizedContent,
        startline: task.startline ?? null,
        deadline: task.deadline,
        fecha_completada: null,
        id_padre: task.id_padre ?? null,
        id_user: task.id_user ?? null,
      });

      await loadTasks();
    } catch (err) {
      setError(err instanceof Error ? err.message : "No se pudo duplicar la tarea");
    } finally {
      setSaving(false);
    }
  };

  const onCsvSelected = async (e: ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    e.target.value = "";
    if (!file) {
      return;
    }
    if (!file.name.toLowerCase().endsWith(".csv")) {
      setError("Selecciona un archivo CSV válido.");
      return;
    }

    setSaving(true);
    setError("");
    try {
      const result = await importTasksCsv(file);
      await loadTasks();
      await loadUsers();
      setError(
        `Importación completada: ${result.imported_tasks} tareas, ${result.created_users} usuarios creados${
          result.unresolved_relations.length ? `. Relaciones no resueltas: ${result.unresolved_relations.join(", ")}` : ""
        }`
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : "No se pudo importar el CSV");
    } finally {
      setSaving(false);
    }
  };

  const menuTask = useMemo(
    () => (actionsMenu ? tasks.find((task) => task.id === actionsMenu.taskId) ?? null : null),
    [actionsMenu, tasks]
  );

  const onTaskMenuKeyDown = (event: React.KeyboardEvent<HTMLDivElement>) => {
    if (!actionsMenu) {
      return;
    }

    const items = taskActionsMenuItemRefs.current.filter(
      (item): item is HTMLButtonElement => item !== null
    );

    if (!items.length) {
      return;
    }

    const currentIndex = items.findIndex((item) => item === document.activeElement);
    const nextIndex = (index: number) => {
      const boundedIndex = (index + items.length) % items.length;
      items[boundedIndex]?.focus();
    };

    if (event.key === "ArrowDown") {
      event.preventDefault();
      nextIndex(currentIndex + 1);
      return;
    }

    if (event.key === "ArrowUp") {
      event.preventDefault();
      nextIndex(currentIndex - 1);
      return;
    }

    if (event.key === "Home") {
      event.preventDefault();
      items[0]?.focus();
      return;
    }

    if (event.key === "End") {
      event.preventDefault();
      items[items.length - 1]?.focus();
      return;
    }

    if (event.key === "Escape") {
      event.preventDefault();
      closeActionsMenu();
      document.getElementById(actionsMenu.triggerId)?.focus();
    }
  };

  return (
    <div className="gantt-page">
      <div className="gantt-page-header">
          <p className="section-label">TasksManagement · Gantt</p>
      </div>
      <div className="row">
          <div className="col-8">    
            <section className="gantt-filter-panel" aria-label="Filtros de tareas">
              <button
                aria-expanded={!isFilterPanelCollapsed}
                className="gantt-filter-toggle"
                onClick={() => setIsFilterPanelCollapsed((prev) => !prev)}
                type="button"
              >
                {isFilterPanelCollapsed ? "▶ Mostrar filtros de usuarios y fechas" : "▼ Ocultar filtros de usuarios y fechas"}
              </button>
              {!isFilterPanelCollapsed && (
                <div className="gantt-filter-body">
                  <div className="gantt-filter-summary-row">
                    <p className="gantt-filter-summary">
                      {isAnyFilterApplied
                        ? `Filtros activos: ${selectedUserIds.size} usuario(s)${isAnyDateFilterApplied ? `, rango por fecha de ${dateField}` : ""}`
                        : "Sin filtros: se muestran todas las tareas"}
                    </p>
                    <button
                      className="chip-btn-mini"
                      disabled={!isAnyFilterApplied}
                      onClick={clearFilters}
                      type="button"
                    >
                      Quitar filtros
                    </button>
                  </div>

                  <div className="gantt-date-filter-grid">
                    <label className="gantt-date-filter-field">
                      <span>Filtrar por</span>
                      <select value={dateField} onChange={(e) => setDateField(e.target.value as "inicio" | "fin" | "completada")}> 
                        <option value="inicio">Fecha de inicio</option>
                        <option value="fin">Fecha de fin</option>
                        <option value="completada">Fecha completada</option>
                      </select>
                    </label>
                    <label className="gantt-date-filter-field">
                      <span>Desde</span>
                      <input type="date" value={dateFrom} onChange={(e) => setDateFrom(e.target.value)} />
                    </label>
                    <label className="gantt-date-filter-field">
                      <span>Hasta</span>
                      <input type="date" value={dateTo} onChange={(e) => setDateTo(e.target.value)} />
                    </label>
                  </div>

                  <div className="gantt-user-filter-list">
                    {usersSorted.map((user) => {
                      const fullName = `${user.nombre} ${user.apellido}`.trim();
                      const displayName = fullName || user.email;
                      const isSelected = selectedUserIds.has(user.id);

                      return (
                        <label className="gantt-user-filter-item" key={user.id}>
                          <input
                            checked={isSelected}
                            onChange={() => toggleUserFilter(user.id)}
                            type="checkbox"
                          />
                          <span className="gantt-user-filter-name">{displayName}</span>
                        </label>
                      );
                    })}
                    {!usersSorted.length && <p className="muted" style={{ margin: 0 }}>No hay usuarios disponibles.</p>}
                  </div>
                </div>
              )}
            </section>
          </div>
          <div className="col-4 gantt-toolbar">
              <button className="primary-btn" disabled={saving} onClick={() => openCreate()} type="button">+ Nueva tarea</button>
              <button className="primary-btn" disabled={saving} onClick={onImportClick} type="button">Importar</button>
              <input
                accept=".csv,text/csv"
                onChange={onCsvSelected}
                ref={csvInputRef}
                style={{ display: "none" }}
                type="file"
              />
              {error && <p className="error-line" style={{ margin: 0 }}>{error}</p>}
          </div>
      </div>

      {loading ? (
        <p className="muted">Cargando tareas…</p>
      ) : (
        <div
          className={`gantt-table${dropTargetId === -1 ? " gantt-root-drop-active" : ""}`}
          ref={ganttTableRef}
          style={ganttTableStyle}
          onDragLeave={() => { if (dropTargetId === -1) setDropTargetId(null); }}
          onDragOver={(e) => { e.preventDefault(); setDropTargetId(-1); }}
          onDrop={(e) => void onDrop(e, null)}
        >
          <div className="gantt-header-row">
            <div className="gantt-label-col gantt-label-header">
              <div className="d-flex align-items-center justify-content-between w-100" style={{ gap: "8px" }}>
                <span>Tarea</span>
                <div className="d-flex align-items-center" style={{ gap: "6px" }}>
                  <button
                    className="chip-btn-mini"
                    aria-label="Contraer todas las tareas padre"
                    disabled={!parentTaskIds.size}
                    onClick={collapseAllParents}
                    title="Contraer todas las tareas padre"
                    type="button"
                  >
                    ⤒
                  </button>
                  <button
                    className="chip-btn-mini"
                    aria-label="Expandir todas las tareas"
                    disabled={!parentTaskIds.size}
                    onClick={expandAllTasks}
                    title="Expandir todas las tareas"
                    type="button"
                  >
                    ⤓
                  </button>
                </div>
              </div>
            </div>
            <div className="gantt-content-col gantt-label-header">Contenido</div>
            <div className="gantt-dates-col gantt-label-header">Fechas</div>
            <div className="gantt-bar-col"><GanttTimelineHeader layout={timelineLayout} /></div>
          </div>

          {flatRows.map(({ task, depth }) => {
            const start = asUnix(task.startline ?? task.created_at);
            const end = asUnix(task.deadline);
            const left = ((start - timelineStats.min) / timelineStats.span) * 100;
            const width = ((end - start) / timelineStats.span) * 100;
            const isParent = hasChildren(task.id);
            const isCollapsed = collapsed.has(task.id);
            const ownerName = task.id_user ? usersById.get(task.id_user) : undefined;
            const isContentExpanded = expandedContentIds.has(task.id);
            const plainContent = stripHtml(task.contenido);
            const hasRichContent = hasRichMarkup(task.contenido);
            const hasLongContent = plainContent.length > CONTENT_PREVIEW_LENGTH;
            const canToggleContent = hasLongContent || hasRichContent;
            const contentPreview = hasLongContent
              ? `${plainContent.slice(0, CONTENT_PREVIEW_LENGTH)}...`
              : plainContent || (hasRichContent ? "Contenido con formato" : "Sin contenido");
            const safeContentHtml = sanitizeTaskContent(task.contenido);
            const previewContentHtml = hasRichContent ? safeContentHtml : "";
            const subtaskStatus = subtaskStatusByTaskId[task.id];
            const hasSubtasks = (subtaskStatus?.count_subtasks ?? 0) > 0;

            return (
              <div
                className={`gantt-tree-row${draggedId === task.id ? " dragging" : ""}${dropTargetId === task.id ? " drop-target" : ""}${highlightedTaskId === task.id ? " recently-focused" : ""}`}
                draggable
                key={task.id}
                onDragEnd={onDragEnd}
                onDragLeave={() => { if (dropTargetId === task.id) setDropTargetId(null); }}
                onDragOver={(e) => { e.preventDefault(); e.stopPropagation(); setDropTargetId(task.id); }}
                onDragStart={() => setDraggedId(task.id)}
                onDrop={(e) => { e.stopPropagation(); void onDrop(e, task.id); }}
              >
                <div className="gantt-label-col" style={{ paddingLeft: `${8 + depth * 22}px` }}>
                  {isParent ? (
                    <button className="gantt-toggle" onClick={() => toggleCollapse(task.id)} type="button">
                      {isCollapsed ? "▶" : "▼"}
                    </button>
                  ) : (
                    <span className="gantt-toggle-placeholder" />
                  )}
                  <div className="gantt-task-info">
                    <div className="gantt-task-title-row">
                      <span className={`gantt-task-title${task.completada ? " done" : ""} ${isParent ? " isParent" : ""}`}>{`#${task.id} - ${task.titulo}`}</span>
                      <div className="gantt-row-actions" onMouseDown={(e) => e.stopPropagation()}>
                        <button
                          aria-label={task.completada ? "Marcar como pendiente" : "Completar tarea"}
                          className="gantt-row-action-btn gantt-row-action-btn-complete"
                          data-task-complete-id={task.id}
                          disabled={saving}
                          onClick={() => void onToggleCompleted(task)}
                          title="Completar tarea"
                          type="button"
                        >
                          <svg viewBox="0 0 24 24" aria-hidden="true">
                            <path d="M9.2 16.1 5.7 12.6 4.3 14l4.9 4.9L20 8.1l-1.4-1.4z" fill="currentColor" />
                          </svg>
                        </button>
                        <button
                          aria-label="Editar tarea"
                          className="gantt-row-action-btn gantt-row-action-btn-edit"
                          disabled={saving}
                          onClick={() => openEdit(task)}
                          title="Editar tarea"
                          type="button"
                        >
                          <svg viewBox="0 0 24 24" aria-hidden="true">
                            <path d="m3 17.2 4-.9 9.6-9.6a1.7 1.7 0 0 0 0-2.4L14.8 2.5a1.7 1.7 0 0 0-2.4 0L2.8 12.1 2 16.9A1 1 0 0 0 3 18zM13.6 3.9l2.5 2.5-1.3 1.3-2.5-2.5 1.3-1.3zM4.7 13.1l6.2-6.2 2.5 2.5-6.2 6.2-2 .4.5-1.9z" fill="currentColor" />
                          </svg>
                        </button>
                        <button
                          aria-expanded={actionsMenu?.taskId === task.id}
                          aria-haspopup="menu"
                          aria-label="Más acciones"
                          className="gantt-row-action-btn gantt-row-action-btn-menu"
                          disabled={saving}
                          id={`task-actions-menu-button-${task.id}`}
                          onClick={(event) => {
                            if (actionsMenu?.taskId === task.id) {
                              closeActionsMenu();
                            } else {
                              openActionsMenu(task.id, event.currentTarget);
                            }
                          }}
                          title="Más acciones"
                          type="button"
                        >
                          <svg viewBox="0 0 24 24" aria-hidden="true">
                            <path d="M6 10a2 2 0 1 0 0 4 2 2 0 0 0 0-4Zm6 0a2 2 0 1 0 0 4 2 2 0 0 0 0-4Zm6 0a2 2 0 1 0 0 4 2 2 0 0 0 0-4Z" fill="currentColor" />
                          </svg>
                        </button>
                      </div>
                    </div>
                    <div className="gantt-task-meta-row">
                      <div className="gantt-task-owner-wrap">
                      <span className={`gantt-task-owner${task.completada ? " done" : ""} ${isParent ? " isParent" : ""}`}>{ownerName ? `` : "Sin responsable"}</span>
                      <span className={`gantt-task-owner${task.completada ? " done" : ""} ${isParent ? " isParent" : ""}`}>{ownerName ? `${ownerName}` : ""}</span>
                      </div>
                      <div className="gantt-task-progress-wrap">
                          <span className={`gantt-task-progress${task.completada ? " done" : ""}`}>
                            {hasSubtasks && (
                                `${Math.round((subtaskStatus.completed_subtasks / subtaskStatus.count_subtasks) * 100)}% ${subtaskStatus.completed_subtasks}/${subtaskStatus.count_subtasks}`
                            )} 
                          </span>                        
                      </div>
                    </div>  
                  </div>
                </div>

                <div className="gantt-content-col">
                  <div className={`gantt-task-content${isContentExpanded ? " expanded" : ""}${!isContentExpanded && hasRichContent ? " rich-preview" : ""}`}>
                    {isContentExpanded ? (
                      <ReactQuill
                        className="gantt-task-content-viewer"
                        key={`${task.id}-${task.updated_at}`}
                        readOnly
                        theme="bubble"
                        value={safeContentHtml}
                      />
                    ) : hasRichContent ? (
                      <div
                        className="gantt-task-content-html gantt-task-content-html-preview"
                        dangerouslySetInnerHTML={{ __html: previewContentHtml }}
                      />
                    ) : (
                      <>
                        <span>{contentPreview}</span>
                        {canToggleContent && (
                          <>
                            {" "}
                            <button
                              aria-label="Expandir contenido"
                              className="gantt-content-more-link"
                              onClick={() => toggleContent(task.id)}
                              title="Ver contenido completo"
                              type="button"
                            >
                              (Ver más)
                            </button>
                          </>
                        )}
                      </>
                    )}
                  </div>
                  {canToggleContent && (
                    <button
                      aria-label={isContentExpanded ? "Contraer contenido" : "Expandir contenido"}
                      className="gantt-content-toggle"
                      onClick={() => toggleContent(task.id)}
                      title={isContentExpanded ? "Contraer contenido" : "Ver contenido completo"}
                      type="button"
                    >
                      {isContentExpanded ? "▴" : "▾"}
                    </button>
                  )}
                </div>

                  <div className="gantt-dates-col">
                  <div className="row w-100">
                    <div className="col-12">
                      <span className="gantt-task-dates dates-startline" onDoubleClick={() => openDateEdit(task)} title="Doble clic para editar fechas">
                          {`${task.startline || task.created_at ? `${toInputDate(task.startline ?? task.created_at)}` : ""}`}
                      </span>                      
                    </div>
                  </div>
                  <div className="row w-100">
                    <div className="col-12">
                      <span className="gantt-task-dates dates-deadline" onDoubleClick={() => openDateEdit(task)} title="Doble clic para editar fechas">
                        {`${toInputDate(task.deadline)}`}
                      </span>
                    </div>
                  </div>
                  <div className="row w-100">
                    <div className="col-12">
                      <span className="gantt-task-dates" onDoubleClick={() => openDateEdit(task)} title="Doble clic para editar fechas">
                        {`${toInputDate(task.fecha_completada) ? `Acabada: ${toInputDate(task.fecha_completada)}` : "-"}`}
                      </span>
                    </div>
                  </div>
                  <div className="row w-100">
                    <div className="col-12">
                      <span className="gantt-task-dates worksheet-entry-duration">
                        {`Días: ${getDurationDays(task.startline ?? task.created_at, task.deadline)}`}
                      </span>
                    </div>
                  </div>
                </div>

                <div className="gantt-bar-col">
                  <div className="gantt-bar-inner" style={{ minWidth: `${timelineLayout.totalWidth}px` }}>
                    <div className="gantt-track">
                      <span
                        className={`gantt-bar${task.completada ? " done" : ""}`}
                        style={{ left: `${Math.max(left, 0)}%`, width: `${Math.max(width, 1.5)}%` }}
                      />
                    </div>
                  </div>
                </div>
              </div>
            );
          })}

          {!flatRows.length && (
            <p className="muted" style={{ padding: "18px 14px" }}>No hay tareas. Crea una con "+ Nueva tarea".</p>
          )}
        </div>
      )}

      {actionsMenu && menuTask && createPortal(
        <div
          className="gantt-task-actions-menu"
          id={`gantt-task-actions-menu-${menuTask.id}`}
          onKeyDown={onTaskMenuKeyDown}
          ref={taskActionsMenuRef}
          role="menu"
          style={{ left: `${actionsMenu.x}px`, top: `${actionsMenu.y}px` }}
        >
          <button
            aria-label="Crear subtarea"
            className="gantt-task-actions-menu-item"
            onClick={() => {
              closeActionsMenu();
              openCreate(menuTask.id);
            }}
            ref={(element) => {
              taskActionsMenuItemRefs.current[0] = element;
            }}
            role="menuitem"
            type="button"
          >
            <span className="gantt-task-actions-menu-icon" aria-hidden="true">
              <svg viewBox="0 0 24 24">
                <path d="M11 5h2v6h6v2h-6v6h-2v-6H5v-2h6z" fill="currentColor" />
              </svg>
            </span>
            <span>Crear subtarea</span>
          </button>
          <button
            aria-label="Duplicar tarea"
            className="gantt-task-actions-menu-item"
            disabled={saving}
            onClick={() => {
              closeActionsMenu();
              void onDuplicateTask(menuTask);
            }}
            ref={(element) => {
              taskActionsMenuItemRefs.current[1] = element;
            }}
            role="menuitem"
            type="button"
          >
            <span className="gantt-task-actions-menu-icon" aria-hidden="true">
              <svg viewBox="0 0 24 24">
                <path d="M8 8V4h12v12h-4v4H4V8h4Zm2 0h6v6h2V6h-8v2Zm4 2H6v8h8v-8Z" fill="currentColor" />
              </svg>
            </span>
            <span>Duplicar tarea</span>
          </button>
          <button
            aria-label={menuTask.completada ? "Marcar como pendiente" : "Completar tarea"}
            className="gantt-task-actions-menu-item gantt-task-actions-menu-item-mobile"
            disabled={saving}
            onClick={() => {
              closeActionsMenu();
              void onToggleCompleted(menuTask);
            }}
            ref={(element) => {
              taskActionsMenuItemRefs.current[2] = element;
            }}
            role="menuitem"
            type="button"
          >
            <span className="gantt-task-actions-menu-icon" aria-hidden="true">
              <svg viewBox="0 0 24 24">
                <path d="M9.2 16.1 5.7 12.6 4.3 14l4.9 4.9L20 8.1l-1.4-1.4z" fill="currentColor" />
              </svg>
            </span>
            <span>Completar tarea</span>
          </button>
          <button
            aria-label="Editar tarea"
            className="gantt-task-actions-menu-item gantt-task-actions-menu-item-mobile"
            disabled={saving}
            onClick={() => {
              closeActionsMenu();
              openEdit(menuTask);
            }}
            ref={(element) => {
              taskActionsMenuItemRefs.current[3] = element;
            }}
            role="menuitem"
            type="button"
          >
            <span className="gantt-task-actions-menu-icon" aria-hidden="true">
              <svg viewBox="0 0 24 24">
                <path d="m3 17.2 4-.9 9.6-9.6a1.7 1.7 0 0 0 0-2.4L14.8 2.5a1.7 1.7 0 0 0-2.4 0L2.8 12.1 2 16.9A1 1 0 0 0 3 18zM13.6 3.9l2.5 2.5-1.3 1.3-2.5-2.5 1.3-1.3zM4.7 13.1l6.2-6.2 2.5 2.5-6.2 6.2-2 .4.5-1.9z" fill="currentColor" />
              </svg>
            </span>
            <span>Editar tarea</span>
          </button>
          <div className="gantt-task-actions-menu-separator" role="separator" />
          <button
            aria-label="Eliminar tarea"
            className="gantt-task-actions-menu-item danger"
            disabled={saving}
            onClick={() => {
              closeActionsMenu();
              void onDelete(menuTask.id);
            }}
            ref={(element) => {
              taskActionsMenuItemRefs.current[4] = element;
            }}
            role="menuitem"
            type="button"
          >
            <span className="gantt-task-actions-menu-icon" aria-hidden="true">
              <svg viewBox="0 0 24 24">
                <path d="M9 3h6l1 2h5v2H3V5h5l1-2Zm1 6h2v9h-2V9Zm4 0h2v9h-2V9ZM7 9h2v9H7V9Z" fill="currentColor" />
              </svg>
            </span>
            <span>Eliminar tarea</span>
          </button>
        </div>,
        document.body
      )}

      {showModal && (
        <div
          className="task-modal-overlay"
          onClick={closeModal}
          onKeyDown={(e) => { if (e.key === "Escape") closeModal(); }}
          role="presentation"
        >
          <TaskEditerForm
            editor={editor}
            error={error}
            onClose={closeModal}
            onSubmit={onSubmit}
            onUploadImage={onUploadImage}
            saving={saving}
            setEditor={setEditor}
            tasks={tasks}
            users={users}
          />
        </div>
      )}

      {showDateModal && (
        <div
          className="task-modal-overlay"
          onClick={closeDateModal}
          onKeyDown={(e) => { if (e.key === "Escape") closeDateModal(); }}
          role="presentation"
        >
          <TaskEditDataTaskForm
            error={error}
            onClose={closeDateModal}
            onSubmit={(values) => void onSubmitDateEdit(values)}
            saving={saving}
            task={dateEditorTask}
          />
        </div>
      )}
    </div>
  );
}
