import { FormEvent, useEffect, useState } from "react";
import { askExecutive, fetchAutomationRules, fetchAutomationRuns, fetchPurchaseProposals, runAutomationRule, updateAutomationRule } from "../api";
import type { AutomationRule, AutomationRun, ExecutiveResult, PurchaseProposal } from "../types";
import SectionIcon from "./components/SectionIcon";

export default function ExecutivePage() {
  const [rules, setRules] = useState<AutomationRule[]>([]);
  const [runs, setRuns] = useState<AutomationRun[]>([]);
  const [proposals, setProposals] = useState<PurchaseProposal[]>([]);
  const [question, setQuestion] = useState("");
  const [productId, setProductId] = useState("");
  const [answer, setAnswer] = useState<ExecutiveResult | null>(null);
  const [status, setStatus] = useState("Cargando coordinación...");
  const [error, setError] = useState("");

  const load = async () => {
    try {
      const [nextRules, nextRuns, nextProposals] = await Promise.all([fetchAutomationRules(), fetchAutomationRuns(), fetchPurchaseProposals()]);
      setRules(nextRules); setRuns(nextRuns); setProposals(nextProposals); setStatus("Estado de automatizaciones sincronizado."); setError("");
    } catch (err) { setError(err instanceof Error ? err.message : "No se pudo cargar la coordinacion"); }
  };
  useEffect(() => { void load(); }, []);

  const query = async (event: FormEvent) => {
    event.preventDefault();
    try { setAnswer(await askExecutive({ question, product_id: productId ? Number(productId) : undefined })); setStatus("Decision registrada y trazable."); setError(""); }
    catch (err) { setError(err instanceof Error ? err.message : "No se pudo coordinar la consulta"); }
  };
  const toggle = async (rule: AutomationRule) => {
    try { await updateAutomationRule(rule.id, !rule.is_active); await load(); } catch (err) { setError(err instanceof Error ? err.message : "No se pudo actualizar la automatizacion"); }
  };
  const run = async (ruleId: number) => {
    try { await runAutomationRule(ruleId); setStatus("Ejecucion registrada. Las propuestas siguen pendientes de aprobacion."); await load(); } catch (err) { setError(err instanceof Error ? err.message : "No se pudo ejecutar la automatizacion"); }
  };

  return <div className="grid executive-page">
    <section className="card executive-hero"><p className="section-label">Fase 4 · Agente Ejecutivo</p><h3><SectionIcon kind="executive" />Coordina, explica y deja el control en manos humanas</h3><p>Este agente consulta herramientas verificables y nunca crea pedidos definitivos ni altera inventario.</p><p className="status-line">{status}</p>{error && <p className="error-line">{error}</p>}</section>
    <section className="grid two-columns"><article className="card"><p className="section-label">Consulta ejecutiva</p><h3><SectionIcon kind="route" />Enrutamiento trazable</h3><form className="stack" onSubmit={query}><textarea required placeholder="Ejemplo: ¿qué productos tienen riesgo de rotura de stock?" value={question} onChange={(event) => setQuestion(event.target.value)} rows={3} /><input min="1" placeholder="ID de producto opcional" type="number" value={productId} onChange={(event) => setProductId(event.target.value)} /><button className="primary-btn" type="submit">Consultar al Ejecutivo</button></form>{answer && <div className="agent-result"><strong>Enrutado a: {answer.routed_agent}</strong><p>Herramienta: {answer.tool}</p><small>{answer.execution_policy}</small><details open><summary>Resultado de la consulta</summary><pre style={{ whiteSpace: "pre-wrap", overflowWrap: "anywhere" }}>{JSON.stringify(answer.result, null, 2)}</pre></details></div>}</article>
      <article className="card"><p className="section-label">Propuestas de compra</p><h3><SectionIcon kind="approval" />Aprobación humana obligatoria</h3><div className="inventory-list">{proposals.map((proposal) => <div className="inventory-list-item" key={proposal.id}><strong>{proposal.product_name}</strong><span>{proposal.suggested_qty} {proposal.base_unit_code} · {proposal.warehouse_name}</span><small>{proposal.status}: {proposal.justification}</small></div>)}{!proposals.length && <p className="muted">No hay propuestas pendientes.</p>}</div></article></section>
    <section className="card"><p className="section-label">Automatizaciones del backend</p><h3><SectionIcon kind="automation" />Activar, ejecutar y auditar</h3><div className="inventory-table">{rules.map((rule) => <div className="inventory-table-row executive-rule" key={rule.id}><span><strong>{rule.name}</strong><small>{rule.description}</small></span><span>{rule.is_active ? "Activa" : "Pausada"}</span><span><button className="chip-btn" onClick={() => void toggle(rule)} type="button">{rule.is_active ? "Pausar" : "Activar"}</button><button className="primary-btn" onClick={() => void run(rule.id)} type="button">Ejecutar</button></span></div>)}</div></section>
    <section className="card"><p className="section-label">Auditoria</p><h3><SectionIcon kind="audit" />Ultimas ejecuciones</h3><div className="inventory-table">{runs.map((run) => <div className="inventory-table-row" key={run.id}><span>{run.rule_code}</span><span>{run.status}</span><span>{new Date(run.started_at).toLocaleString()}</span></div>)}{!runs.length && <p className="muted">Aun no hay ejecuciones auditadas.</p>}</div></section>
  </div>;
}
