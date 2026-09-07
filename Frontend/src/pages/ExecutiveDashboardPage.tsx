import { FormEvent, useEffect, useState } from "react";
import { analyzeWithStockAssistantAgent, fetchExecutiveDashboard } from "../api";
import { useAuth } from "../auth";
import type { ExecutiveDashboard } from "../types";
import SectionIcon from "./components/SectionIcon";

type ChatMessage = { role: "user" | "assistant"; text: string; createdAt: string };
const HISTORY_KEY = "stockassistant-stock-assistant-history";

function number(value: number | null | undefined, digits = 0): string {
  return value === null || value === undefined ? "--" : new Intl.NumberFormat("es-ES", { maximumFractionDigits: digits }).format(value);
}

function ShortChart({ title, items, first, second }: { title: string; items: Array<Record<string, string | number>>; first: string; second?: string }) {
  const max = Math.max(1, ...items.flatMap((item) => [Number(item[first]) || 0, Number(item[second ?? first]) || 0]));
  if (!items.length) return <EmptyChart title={title} />;
  return <div className="dashboard-chart" aria-label={title} role="img">
    <div className="dashboard-chart-bars">
      {items.map((item, index) => (
        <div className="dashboard-chart-column" key={`${item.label ?? item.product_name ?? index}`} title={`${item.label ?? item.product_name ?? "Dato"}: ${number(Number(item[first]))}${second ? ` / ${number(Number(item[second]))}` : ""}`}>
          <span className="chart-bar chart-bar-primary" style={{ height: `${Math.max(4, (Number(item[first]) / max) * 100)}%` }} />
          {second && <span className="chart-bar chart-bar-secondary" style={{ height: `${Math.max(4, (Number(item[second]) / max) * 100)}%` }} />}
        </div>
      ))}
    </div>
    <div className="chart-axis-labels">{items.map((item, index) => <span key={index}>{String(item.label ?? item.product_name ?? item.day ?? "").slice(0, 8)}</span>)}</div>
  </div>;
}

function EmptyChart({ title }: { title: string }) {
  return <div className="dashboard-chart-empty" role="status"><strong>{title}</strong><span>Sin movimientos suficientes para el período seleccionado.</span></div>;
}

function downloadCsv(data: ExecutiveDashboard) {
  const rows = [
    ["Prioridad", "Producto", "Bodega", "Stock actual", "Punto reposición", "Acción"],
    ...data.priority_purchases.map((row) => [row.priority, row.product_name, row.warehouse_name, row.available_qty, row.reorder_point, row.recommended_action]),
  ];
  const csv = rows.map((row) => row.map((cell) => `"${String(cell ?? "").replace(/"/g, '""')}"`).join(",")).join("\n");
  const link = document.createElement("a");
  link.href = URL.createObjectURL(new Blob([csv], { type: "text/csv;charset=utf-8" }));
  link.download = "prioridades-inventario.csv";
  link.click();
  URL.revokeObjectURL(link.href);
}

export default function ExecutiveDashboardPage() {
  const { user } = useAuth();
  const [periodDays, setPeriodDays] = useState(30);
  const [data, setData] = useState<ExecutiveDashboard | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [showAlerts, setShowAlerts] = useState(false);
  const [prompt, setPrompt] = useState("");
  const [chatLoading, setChatLoading] = useState(false);
  const [messages, setMessages] = useState<ChatMessage[]>(() => {
    try { return JSON.parse(window.localStorage.getItem(HISTORY_KEY) ?? "[]") as ChatMessage[]; } catch { return []; }
  });

  const load = async () => {
    setLoading(true); setError("");
    try { setData(await fetchExecutiveDashboard(periodDays)); }
    catch (err) { setError(err instanceof Error ? err.message : "No se pudo cargar el dashboard."); }
    finally { setLoading(false); }
  };
  useEffect(() => { void load(); }, [periodDays]);
  useEffect(() => { window.localStorage.setItem(HISTORY_KEY, JSON.stringify(messages.slice(-20))); }, [messages]);

  const askAssistant = async (event: FormEvent) => {
    event.preventDefault(); const question = prompt.trim(); if (!question) return;
    setPrompt(""); setChatLoading(true);
    setMessages((current) => [...current, { role: "user", text: question, createdAt: new Date().toISOString() }]);
    try {
      const response = await analyzeWithStockAssistantAgent({ prompt: question, provider: "openai", use_web: false, use_tools: true, max_web_results: 5, max_tool_results: 10 });
      const sources = (response.web_results ?? []).map((source) => source.url).filter(Boolean);
      const sourceLabel = sources.length ? sources.join(", ") : "agente StockAssistant y herramientas habilitadas";
      const answer = `${response.response || "Sin respuesta del asistente."}\n\nFuente: ${sourceLabel}.\nPeríodo de referencia: últimos ${periodDays} días.\nConfianza: depende de la cobertura de los datos disponibles; no se ha usado una predicción entrenada.`;
      setMessages((current) => [...current, { role: "assistant", text: answer, createdAt: new Date().toISOString() }]);
    } catch (err) { setMessages((current) => [...current, { role: "assistant", text: err instanceof Error ? err.message : "No se pudo consultar al asistente.", createdAt: new Date().toISOString() }]); }
    finally { setChatLoading(false); }
  };

  const alerts = data?.alerts ?? [];
  return <section className="executive-dashboard">
    <header className="dashboard-topbar">
      <div><p className="section-label">Operación conectada</p><h2>Resumen ejecutivo</h2><p className="muted">Indicadores calculados con inventario, pedidos y movimientos reales.</p></div>
      <div className="dashboard-topbar-actions">
        <label>Período<select aria-label="Período de datos" value={periodDays} onChange={(event) => setPeriodDays(Number(event.target.value))}><option value={7}>Últimos 7 días</option><option value={30}>Últimos 30 días</option><option value={90}>Últimos 90 días</option></select></label>
        <button className="chip-btn" disabled={!data} onClick={() => data && downloadCsv(data)} type="button">Exportar CSV</button>
        <button className="primary-btn" disabled={loading} onClick={() => void load()} type="button">{loading ? "Actualizando..." : "Actualizar"}</button>
        <button aria-expanded={showAlerts} className="dashboard-notifications" onClick={() => setShowAlerts((value) => !value)} type="button">Alertas <b>{alerts.length}</b></button>
        <div className="dashboard-profile">{user?.nombre?.slice(0, 1) || "U"}<span>{user ? `${user.nombre} ${user.apellido}`.trim() : "Sesión activa"}</span></div>
      </div>
    </header>
    {error && <div className="dashboard-error" role="alert">No se pudo obtener el resumen: {error}</div>}
    {showAlerts && <div className="dashboard-alert-drawer">{alerts.length ? alerts.slice(0, 4).map((alert, index) => <p key={index}><strong>{String(alert.product_name)}:</strong> {String(alert.message)}</p>) : <p>No hay alertas activas.</p>}</div>}
    <div className="dashboard-layout">
      <div className="dashboard-main">
        <div className="dashboard-kpis">
          <article className="dashboard-kpi"><span>Nivel de servicio</span><strong>{number(data?.metrics.service_level_pct, 1)}{data?.metrics.service_level_pct !== null && data?.metrics.service_level_pct !== undefined ? "%" : ""}</strong><small>Despachado / solicitado, {periodDays} días</small></article>
          <article className="dashboard-kpi"><span>Rotación</span><strong>{number(data?.metrics.turnover, 2)}</strong><small>Unidades despachadas / stock actual</small></article>
          <article className="dashboard-kpi warning"><span>Inventario excedente</span><strong>{number(data?.metrics.excess_units)}</strong><small>{number(data?.metrics.excess_items)} referencias sobre objetivo</small></article>
          <article className="dashboard-kpi muted-kpi"><span>Ahorro potencial</span><strong>{data?.metrics.potential_savings === null || !data ? "--" : number(data.metrics.potential_savings)}</strong><small>{data?.metrics.potential_savings_note ?? "Calculando..."}</small></article>
        </div>
        <article className="card dashboard-purchases"><div className="dashboard-section-head"><div><p className="section-label">Acción prioritaria</p><h3><SectionIcon kind="cart" />Compras prioritarias</h3></div><span>{data?.priority_purchases.length ?? 0} referencias</span></div>
          <div className="dashboard-table-wrap"><table><thead><tr><th>Prioridad</th><th>Producto</th><th>Bodega</th><th>Actual</th><th>Óptimo</th><th>Acción</th><th>Impacto</th></tr></thead><tbody>{loading ? <tr><td colSpan={7}>Cargando prioridades...</td></tr> : data?.priority_purchases.length ? data.priority_purchases.map((row, index) => <tr key={`${row.product_id}-${index}`}><td><span className={`priority-pill ${row.priority}`}>{String(row.priority)}</span></td><td>{String(row.product_name)}</td><td>{String(row.warehouse_name)}</td><td>{number(Number(row.available_qty))}</td><td>{number(Number(row.reorder_point))}</td><td>{String(row.recommended_action)}</td><td>{number(Number(row.estimated_impact))} {String(row.base_unit_code)}</td></tr>) : <tr><td colSpan={7}>No hay compras prioritarias con los datos disponibles.</td></tr>}</tbody></table></div>
        </article>
        <div className="dashboard-charts-grid">
          <article className="card"><p className="section-label">Unidades</p><h3><SectionIcon kind="trend" />Evolución de stock y consumo</h3><ShortChart title="Entradas y consumo por día" items={(data?.stock_evolution ?? []).map((item) => ({ ...item, label: item.day }))} first="entries" second="consumption" /><p className="chart-legend"><i className="chart-bar-primary" /> Entradas <i className="chart-bar-secondary" /> Consumo</p></article>
          <article className="card"><p className="section-label">Cobertura</p><h3><SectionIcon kind="coverage" />Demanda registrada frente a disponible</h3><ShortChart title="Disponible y despachado por producto" items={(data?.forecast_vs_available ?? []).map((item) => ({ ...item }))} first="available_qty" second="dispatched_qty" /><p className="chart-legend"><i className="chart-bar-primary" /> Disponible <i className="chart-bar-secondary" /> Despachado; sin forecast entrenado</p></article>
          <article className="card"><p className="section-label">Estado</p><h3><SectionIcon kind="risk" />Distribución de riesgos</h3><ShortChart title="Distribución de riesgos" items={(data?.risk_distribution ?? []).map((item) => ({ ...item }))} first="value" /></article>
          <article className="card"><p className="section-label">Proveedores</p><h3><SectionIcon kind="supplier" />Coste, cumplimiento y lead time</h3>{data?.supplier_comparison.length ? <div className="supplier-list">{data.supplier_comparison.map((supplier) => <div key={supplier.name}><strong>{supplier.name}</strong><span>Sin histórico de coste, fecha comprometida o lead time.</span></div>)}</div> : <EmptyChart title="Comparativa de proveedores" />}</article>
        </div>
        <article className="dashboard-ai-cta"><div><p className="section-label">Recomendación IA</p><h3>Convierte las alertas en un plan de compra justificable.</h3><p>Consulta a Stock Assistant usando el mismo agente de StockAssistant. La respuesta indica sus fuentes cuando existan.</p></div><button className="primary-btn" onClick={() => document.getElementById("stock-assistant-input")?.focus()} type="button">Analizar con Stock Assistant</button></article>
      </div>
      <aside className="dashboard-side">
        <article className="card dashboard-alerts"><p className="section-label"><SectionIcon kind="alert" />Alertas inteligentes</p><h3>Qué requiere atención</h3>{alerts.length ? alerts.slice(0, 6).map((alert, index) => <div className={`alert-item ${alert.severity}`} key={index}><span>{String(alert.kind).replace(/_/g, " ")}</span><strong>{String(alert.product_name)}</strong><p>{String(alert.message)}</p></div>) : <p className="muted">No hay alertas activas con la configuración actual.</p>}</article>
        <article className="card stock-assistant"><p className="section-label">Stock Assistant</p><h3><SectionIcon kind="assistant" />Asistente operativo</h3><div className="assistant-history" aria-live="polite">{messages.length ? messages.slice(-6).map((message, index) => <div className={`assistant-message ${message.role}`} key={`${message.createdAt}-${index}`}><strong>{message.role === "user" ? "Tú" : "StockAssistant"}</strong><p>{message.text}</p></div>) : <p className="muted">Pregunta por compras, roturas o inventario disponible.</p>}</div><form onSubmit={(event) => void askAssistant(event)}><label className="sr-only" htmlFor="stock-assistant-input">Consulta para Stock Assistant</label><textarea id="stock-assistant-input" onChange={(event) => setPrompt(event.target.value)} placeholder="Ej.: ¿Qué debo reponer primero?" value={prompt} /><button className="primary-btn" disabled={chatLoading} type="submit">{chatLoading ? "Analizando..." : "Preguntar"}</button></form><small>Fuente: agente StockAssistant. Período de referencia: últimos {periodDays} días. Confianza: depende de los datos disponibles.</small></article>
      </aside>
    </div>
  </section>;
}
