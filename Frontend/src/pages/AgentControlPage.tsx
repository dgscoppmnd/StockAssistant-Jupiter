import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { automationRequest, runAutomationRule } from '../api';
import ObservedAi from './components/ObservedAi';
import TraceInterpretation from './components/TraceInterpretation';

export type Rule = {latest_run_status?:string;pending_proposals?:number;executed_actions?:number;last_provider_signal?:string;failures?:number;id: number; name: string; code: string; description: string; current_version: number; is_active: boolean; last_run_at: string | null; next_run_at: string | null; config: Record<string, unknown> | null};
type Run = {id: number; rule_id: number; rule_code: string; rule_name: string; status: string; rule_version: number; started_at: string; completed_at: string | null; latency_ms: number | null; result: Record<string, unknown> | null; error_message: string | null; config_snapshot?: {allow_unmetered_paid_ai?: boolean} | null};
type Evaluation = {expected_dispatch:string;observed:{sold:string;returned:string};forecast_metrics:{mae:string;wape:string | null;bias:string};objective_met:boolean | null;net_benefit:string | null;period_start:string;period_end:string};
type Proposal = {id: number; run_id: number; rule_id: number; product_id: number; warehouse_id: number; product_name: string; warehouse_name: string; action: string; status: string; expires_at: string; purchase_pending_qty:string | null; plan: {reason: string; unit: string; action: {quantity: string}; alternatives: unknown[]; assumptions: string[]}; evaluation: Evaluation | null};
type Event = {id: number; phase: string; created_at: string; detail: Record<string, unknown>};
type BusinessSnapshot = {as_of:string;scope_limit:number;rows:{product_id:number;warehouse_id:number;product_name:string;unit:string;available:string;coverage_days:string | null;historical_cost_capital:string | null;unavailable_now:boolean;stock_updated_at:string;dispatch_90_days:string}[]};
type Metrics = {objective_evaluable:number;objective_success_rate:number | null;business_snapshot:BusinessSnapshot;executions: number; technical_success_rate: number | null; median_ms: number | null; p95_ms: number | null; failures: number; degraded: number; reliability: string; limitations: string; tokens: number | null; usage: {metered_calls: number}; schema_compliance_rate: number | null; tool_calls: number; policy_blocks: number; provider_failures: number; events: {phase: string; count: number}[]; decisions: {action: string; status: string; count: number; evaluated: number}[]; series: {day: string; executions: number; failures: number; degraded: number; median_ms: number | null}[]};
const display = (value: unknown) => value === null || value === undefined ? 'No disponible' : String(value);
const date = (value: string | null) => value ? new Date(value).toLocaleString() : 'No disponible';
const labels: Record<string, string> = {replenish: 'Reposición', transfer: 'Traslado físico', suspend_reorder: 'Suspender reposición automática', promotion: 'Recomendación comercial', supplier_return: 'Devolución a proveedor'};
const phases = ['observation', 'analysis', 'tools', 'proposal', 'validation', 'approval', 'execution', 'evaluation'];

function Series({title,points,unit}: {title:string; points:{label:string;value:number | null}[];unit:string}) {
  const observed=points.filter(p=>p.value !== null);
  const max=Math.max(1,...observed.map(p=>p.value ?? 0));
  return <article className="card"><h3>{title}</h3>{!observed.length ? <p>No disponible: sin observaciones.</p> : <>
    <svg viewBox="0 0 600 140" role="img" aria-label={`${title}, ${observed.length} observaciones. Valores disponibles en la tabla.`}>
      <line x1="20" y1="120" x2="580" y2="120" stroke="currentColor" />
      {observed.map((p,i)=><g key={p.label}><rect x={25+i*550/observed.length} y={115-(p.value ?? 0)/max*95} width={Math.min(30,450/observed.length)} height={Math.max(1,(p.value ?? 0)/max*95)} fill="currentColor"><title>{p.label}: {p.value} {unit}</title></rect></g>)}
    </svg>
    <p>Muestra: {observed.length} días · cambio entre las dos últimas observaciones: {observed.length < 2 ? 'No disponible' : `${((observed[observed.length-1].value ?? 0)-(observed[observed.length-2].value ?? 0)).toFixed(2)} ${unit}`}</p>
    <details><summary>Valores y fechas (UTC)</summary><table><thead><tr><th>Fecha</th><th>Valor ({unit})</th></tr></thead><tbody>{points.map(p=><tr key={p.label}><td>{p.label}</td><td>{display(p.value)}</td></tr>)}</tbody></table></details>
  </>}</article>;
}

export default function AgentControlPage() {
  const [rules, setRules] = useState<Rule[]>([]), [runs, setRuns] = useState<Run[]>([]), [proposals, setProposals] = useState<Proposal[]>([]);
  const [metrics, setMetrics] = useState<Metrics | null>(null), [events, setEvents] = useState<Event[]>([]);
  const [eventsRunId,setEventsRunId] = useState<number | null>(null);
  const [selected, setSelected] = useState<number | null>(null), [ruleFilter, setRuleFilter] = useState(''), [stateFilter, setStateFilter] = useState('');
  const [days, setDays] = useState('30'), [product, setProduct] = useState(''), [warehouse, setWarehouse] = useState('');
  const [version,setVersion] = useState(''), [model,setModel] = useState('');
  const [error, setError] = useState(''), [loading, setLoading] = useState(true), [connected, setConnected] = useState(false), [stopped, setStopped] = useState(false);
  const [permissions, setPermissions] = useState<string[]>([]), [busy, setBusy] = useState(false), [reason, setReason] = useState('');
  const [quote, setQuote] = useState({supplier_id: '', unit_price: '', valid_until: '', reference: ''}), [physical, setPhysical] = useState(false);
  const [receiptFor,setReceiptFor]=useState<number | null>(null), [receiptQty,setReceiptQty]=useState(''), [receiptKey,setReceiptKey]=useState(''), [receiptPhysical,setReceiptPhysical]=useState(false);
  const load = async () => {
    try {
      const [r, x, p, m, c] = await Promise.all([
        automationRequest<Rule[]>('/rules'), automationRequest<Run[]>('/runs'), automationRequest<Proposal[]>('/proposals'),
        automationRequest<Metrics>(`/metrics?days=${days}${ruleFilter ? `&rule_id=${ruleFilter}` : ''}${version ? `&version=${version}` : ''}${model ? `&model=${encodeURIComponent(model)}` : ''}`),
        automationRequest<{stopped: boolean; permissions: string[]}>('/control')]);
      setRules(r); setRuns(x); setProposals(p); setMetrics(m); setStopped(c.stopped); setPermissions(c.permissions); setError(''); setConnected(true);
    } catch (e) {setError(e instanceof Error ? e.message : 'Error al cargar'); setConnected(false);} finally {setLoading(false);}
  };
  useEffect(() => {
    let cancelled = false, timer: ReturnType<typeof setTimeout>;
    const poll = async () => {if (document.visibilityState === 'visible') await load(); if (!cancelled) timer = setTimeout(poll, 15000);};
    void poll(); return () => {cancelled = true; clearTimeout(timer);};
  }, [days, ruleFilter,version,model]);
  useEffect(() => {
    if (!selected) return;
    let cancelled = false, timer: ReturnType<typeof setTimeout>;
    const poll = async () => {
      try { const data = await automationRequest<Event[]>(`/runs/${selected}/events`); if (!cancelled) {setEvents(data);setEventsRunId(selected);} }
      catch (e) {if (!cancelled) setError(String(e));}
      if (!cancelled) timer = setTimeout(poll, 10000);
    };
    setEvents([]);setEventsRunId(null); void poll(); return () => {cancelled = true; clearTimeout(timer);};
  }, [selected]);
  const action = async (fn: () => Promise<unknown>) => {setBusy(true); try {await fn(); await load();} catch(e) {setError(e instanceof Error ? e.message : String(e));} finally {setBusy(false);setPhysical(false);}};
  const filteredProposals = proposals.filter(p => (!ruleFilter || p.rule_id === Number(ruleFilter)) && (!product || p.product_id === Number(product)) && (!warehouse || p.warehouse_id === Number(warehouse)));
  const filteredRuns = runs.filter(r => (!ruleFilter || r.rule_id === Number(ruleFilter)) && (!stateFilter || r.status === stateFilter) && (!version || r.rule_version === Number(version)) && (!model || (r.result?.ai as {model?:string} | undefined)?.model === model) &&
    new Date(r.started_at).getTime() >= Date.now() - Number(days)*86400000 && ((!product && !warehouse) || filteredProposals.some(p => p.run_id === r.id)));
  const lastPhase = events.length ? events[events.length - 1].phase : null;
  const current = lastPhase ? ({model_call:'analysis',schema_valid:'analysis',schema_rejected:'analysis',decision:'proposal',review:'evaluation',physical_receipt:'execution'} as Record<string,string>)[lastPhase] ?? lastPhase : null;
  return <div className="grid agent-control">
    <section className="card"><p className="section-label">Operación trazable</p><h3>Centro de control de agentes</h3>
      <p>AutomationService coordina reglas. Ejecutivo, inventario y comercial aportan servicios especializados; cada regla es una programación, no un agente independiente.</p>
      <p role="status" aria-live="polite">{loading ? 'Cargando…' : connected ? 'Conectado · actualización cada 15 segundos' : 'Desconectado · reintentando'} · {stopped ? 'Operaciones detenidas' : 'Operaciones habilitadas según políticas'}</p>
      {error && <p className="error-line" role="alert">{error}</p>}
      <Link to="/agentes/reglas">Abrir editor de reglas</Link>{' '}
      <button className="chip-btn" disabled={busy || !permissions.includes('activate')} onClick={() => void action(() => automationRequest('/control', 'PUT', {stopped: !stopped}))}>{stopped ? 'Reanudar' : 'Detener operaciones'}</button>
    </section>
    <section className="card"><h3>Filtros</h3><div className="agent-fields">
      <label>Regla<select value={ruleFilter} onChange={e => setRuleFilter(e.target.value)}><option value="">Todas</option>{rules.map(r => <option value={r.id} key={r.id}>{r.name}</option>)}</select></label>
      <label>Periodo<select value={days} onChange={e => setDays(e.target.value)}>{[7,30,90,365].map(n => <option value={n} key={n}>{n} días</option>)}</select></label>
      <label>Estado<select value={stateFilter} onChange={e => setStateFilter(e.target.value)}><option value="">Todos</option>{['running','completed','degraded','failed'].map(s => <option key={s}>{s}</option>)}</select></label>
      <label>Producto (ID)<input type="number" min="1" value={product} onChange={e => setProduct(e.target.value)} /></label>
      <label>Almacén (ID)<input type="number" min="1" value={warehouse} onChange={e => setWarehouse(e.target.value)} /></label>
      <label>Versión de regla<input type="number" min="0" value={version} onChange={e=>setVersion(e.target.value)} /></label>
      <label>Modelo (nombre exacto)<input value={model} onChange={e=>setModel(e.target.value)} /></label>
    </div><small>Filtros de producto y almacén enlazan ejecuciones con propuestas persistidas. Se muestran las 100 ejecuciones más recientes.</small></section>
    <section className="grid two-columns" aria-label="Métricas operativas">
      <article className="card"><h3>Ejecuciones: {display(metrics?.executions)}</h3><p>Éxito técnico: {metrics?.technical_success_rate == null ? 'No disponible' : `${(metrics.technical_success_rate*100).toFixed(1)} %`}</p><p>Muestra: {display(metrics?.executions)} · periodo: {days} días</p><p>Degradadas: {display(metrics?.degraded)} · fallos: {display(metrics?.failures)}</p></article>
      <article className="card"><h3>Latencia y consumo</h3><p>Mediana: {display(metrics?.median_ms)} ms · P95: {display(metrics?.p95_ms)} ms</p><p>Tokens informados: {display(metrics?.tokens)} · llamadas con uso informado: {display(metrics?.usage?.metered_calls)}</p><p>Coste y coste por tarea: No disponibles</p><p>{metrics?.limitations}</p></article>
      <article className="card"><h3>Calidad de decisiones</h3><p>Objetivo de despachos cumplido: {metrics?.objective_success_rate == null ? "No disponible" : `${(metrics.objective_success_rate*100).toFixed(1)} %`} · muestra evaluable: {display(metrics?.objective_evaluable)}</p><p>{metrics?.reliability ?? 'Evidencia insuficiente'}</p><p>Aprobar o completar una ejecución no demuestra acierto. Sin historial completo de disponibilidad no se calculan probabilidades de éxito.</p><p>Calidad de datos: parcial · incertidumbre: sin calibrar · políticas: consultar eventos · fiabilidad histórica: insuficiente.</p></article>
      <article className="card"><h3>Eventos y políticas</h3><p>Herramientas: {display(metrics?.tool_calls)} · bloqueos de políticas: {display(metrics?.policy_blocks)} · fallos del proveedor: {display(metrics?.provider_failures)}</p><p>Respuestas válidas entre llamadas al modelo: {metrics?.schema_compliance_rate == null ? 'No disponible' : `${(metrics.schema_compliance_rate*100).toFixed(1)} %`}</p>{metrics?.events.map(e => <p key={e.phase}>{e.phase}: {e.count}</p>)}{!metrics?.events.length && <p>Sin eventos en este periodo.</p>}</article>
    </section>
    <section className="grid two-columns" aria-label="Evolución de métricas">
      <Series title="Fallos por día" unit="ejecuciones" points={(metrics?.series ?? []).map(p=>({label:p.day,value:p.failures}))} />
      <Series title="Latencia mediana por día" unit="ms" points={(metrics?.series ?? []).map(p=>({label:p.day,value:p.median_ms}))} />
      <article className="card"><h3>Coste y resultado de negocio</h3><p>Serie de coste monetario: No disponible. Margen realizado, roturas históricas y beneficio neto atribuible: No disponibles sin evidencia suficiente.</p><p>Los resultados medidos y la comparación de previsiones se consultan por decisión.</p></article>
      <article className="card"><h3>Decisiones por tipo y estado</h3><table><thead><tr><th>Tipo</th><th>Estado</th><th>Muestra</th><th>Evaluadas</th></tr></thead><tbody>{metrics?.decisions.map(d=><tr key={d.action+d.status}><td>{labels[d.action] ?? d.action}</td><td>{d.status}</td><td>{d.count}</td><td>{d.evaluated}</td></tr>)}</tbody></table>{!metrics?.decisions.length && <p>Sin decisiones persistidas en este periodo.</p>}</article>
    </section>
    <section className="card"><h3>Inventario observado y capital</h3><p>Instantánea: {date(metrics?.business_snapshot?.as_of ?? null)} · máximo {display(metrics?.business_snapshot?.scope_limit)} entidades. Cobertura calculada con despachos de 90 días; capital valorado a coste histórico de recepción. Sin referencia temporal comparable.</p><div className="agent-table-scroll"><table><thead><tr><th>Producto / almacén</th><th>Disponible</th><th>Cobertura (días)</th><th>Despachos (90 días)</th><th>Capital a coste histórico</th><th>Estado actual</th><th>Actualización stock</th></tr></thead><tbody>{metrics?.business_snapshot?.rows.filter(r=>(!product || r.product_id===Number(product)) && (!warehouse || r.warehouse_id===Number(warehouse))).map(r=><tr key={`${r.product_id}-${r.warehouse_id}`}><td>{r.product_name} / #{r.warehouse_id}</td><td>{r.available} {r.unit}</td><td>{display(r.coverage_days)}</td><td>{r.dispatch_90_days}</td><td>{display(r.historical_cost_capital)}</td><td>{r.unavailable_now ? 'Sin disponibilidad' : 'Disponible'}</td><td>{date(r.stock_updated_at)}</td></tr>)}</tbody></table></div><p>Rotación basada en inventario medio, roturas históricas y margen realizado: No disponibles. La falta de stock actual no demuestra pérdida de ventas. Los importes usan la base de cambio registrada en las recepciones; no se mezclan con presupuestos EUR confirmados.</p></section>
    <section className="card"><h3>Agente operativo · reglas programadas</h3>{rules.map(r => <article className="agent-rule" key={r.id}><strong>{r.name} · v{r.current_version}</strong><p>{r.latest_run_status === 'running' ? 'Analizando' : (r.failures ?? 0) >= 3 ? 'Error: requiere intervención' : (r.pending_proposals ?? 0) > 0 ? 'Esperando aprobación' : r.latest_run_status === 'degraded' ? 'Degradado' : r.is_active ? 'Programada' : 'Inactiva'} · modo: {display(r.config?.mode ?? 'assisted')}</p><p>Última: {date(r.last_run_at)} · próxima: {r.is_active ? date(r.next_run_at) : 'Pausada'}</p><p>{r.description}</p><p>Propuestas pendientes: {display(r.pending_proposals)} · acciones ejecutadas: {display(r.executed_actions)} · última señal del proveedor: {r.last_provider_signal === "provider_failure" ? "Fallo observado" : r.last_provider_signal ? "Respondió; consultar validación" : "No disponible"}</p><button className="chip-btn" disabled={busy || stopped || !permissions.includes('activate')} onClick={() => void action(() => runAutomationRule(r.id))}>Analizar ahora</button></article>)}</section>
    <section className="card"><h3>Actividad por ejecución</h3>{!filteredRuns.length && <p>No hay ejecuciones para estos filtros.</p>}
      <div className="agent-table-scroll"><table><thead><tr><th>Ejecución</th><th>Regla</th><th>Estado</th><th>Inicio</th><th>Duración</th><th>IA observada</th></tr></thead><tbody>{filteredRuns.map(r => <tr key={r.id}><td><button className="chip-btn" onClick={() => setSelected(r.id)}>#{r.id} · trazabilidad</button></td><td>{r.rule_name} · v{r.rule_version}</td><td>{r.status}{r.error_message && <p>{r.error_message}</p>}</td><td>{date(r.started_at)}</td><td>{display(r.latency_ms)} ms</td><td><ObservedAi run={r} /></td></tr>)}</tbody></table></div>
    </section>
    {selected && <section className="card"><h3>Traza de ejecución #{selected}</h3><p>Último evento observado: {lastPhase ?? "Sin eventos"}</p><ol className="agent-flow" aria-label="Flujo observado">{phases.map(p => <li key={p} aria-current={current === p ? 'step' : undefined}>{p}{current === p ? ' · actual' : ''}</li>)}</ol>
      {!events.length && <p>Cargando eventos o ejecución sin eventos.</p>}<ol>{events.map(e => <li key={e.id}><strong>{e.phase} · {date(e.created_at)}</strong><details><summary>Evidencias y resultado</summary><pre>{JSON.stringify(e.detail,null,2)}</pre></details></li>)}</ol>
      {filteredProposals.filter(p => p.run_id === selected).map(p => <a key={p.id} href={`#proposal-${p.id}`}>Abrir propuesta #{p.id} </a>)}
      <TraceInterpretation key={selected} runId={selected} ready={eventsRunId===selected} revision={`${events[events.length-1]?.id ?? 0}:${runs.find(r=>r.id===selected)?.status ?? ''}`} />
    </section>}
    <section className="card"><h3>Revisar propuestas y resultados</h3><label>Motivo de aprobación o rechazo<input value={reason} onChange={e => setReason(e.target.value)} minLength={3} maxLength={500} /></label>
      <details><summary>Oferta de compra confirmada para la siguiente ejecución</summary><div className="agent-fields">
        <label>Proveedor (ID)<input type="number" min="1" value={quote.supplier_id} onChange={e => setQuote({...quote,supplier_id:e.target.value})} /></label>
        <label>Precio por unidad base (EUR)<input type="number" min="0.0001" step="0.0001" value={quote.unit_price} onChange={e => setQuote({...quote,unit_price:e.target.value})} /></label>
        <label>Oferta válida hasta<input type="datetime-local" value={quote.valid_until} onChange={e => setQuote({...quote,valid_until:e.target.value})} /></label>
        <label>Referencia de oferta<input value={quote.reference} onChange={e => setQuote({...quote,reference:e.target.value})} /></label>
      </div></details>
      <label><input type="checkbox" checked={physical} onChange={e => setPhysical(e.target.checked)} /> Confirmo que el traslado seleccionado se ha realizado físicamente</label>
      {!filteredProposals.length && <p>No hay propuestas para estos filtros.</p>}{filteredProposals.map(p => <article className="agent-rule" id={`proposal-${p.id}`} key={p.id}>
        <h4>#{p.id} · {labels[p.action] ?? p.action} · {p.product_name}</h4><p>{p.warehouse_name} · {p.plan.action.quantity} {p.plan.unit} · {p.status} · caduca {date(p.expires_at)}</p><p>{p.plan.reason}</p>
        <button className="chip-btn" onClick={() => setSelected(p.run_id)}>Ver ejecución #{p.run_id}</button>
        <details><summary>Evidencias, cálculos y alternativas</summary><pre>{JSON.stringify(p.plan,null,2)}</pre></details>
        {p.status === 'pending_approval' && <><button className="chip-btn" disabled={busy || reason.trim().length < 3 || !permissions.includes('approve')} onClick={() => void action(() => automationRequest(`/proposals/${p.id}/decision`,'POST',{approve:true,reason}))}>Aprobar</button><button className="chip-btn" disabled={busy || reason.trim().length < 3 || !permissions.includes('approve')} onClick={() => void action(() => automationRequest(`/proposals/${p.id}/decision`,'POST',{approve:false,reason}))}>Rechazar</button></>}
        {p.status === 'approved' && <button className="primary-btn" disabled={busy || stopped || !permissions.includes('execute')} onClick={() => void action(() => automationRequest(`/proposals/${p.id}/execute`,'POST',{
          physical_confirmed: physical, quote: p.action === 'replenish' ? {supplier_id:Number(quote.supplier_id),unit_price:quote.unit_price,currency_code:'EUR',valid_until:quote.valid_until ? new Date(quote.valid_until).toISOString() : '',reference:quote.reference} : null
        }))}>Ejecutar acción aprobada #{p.id}</button>}
        {p.status === 'executed' && p.action === 'replenish' && <><p>Pendiente de recepción: {display(p.purchase_pending_qty)} {p.plan.unit}</p><button className="chip-btn" disabled={busy || !permissions.includes('execute') || Number(p.purchase_pending_qty) <= 0} onClick={()=>{setReceiptFor(p.id);setReceiptQty('');setReceiptKey(crypto.randomUUID());setReceiptPhysical(false);}}>Registrar recepción física del pedido #{p.id}</button></>}
        {receiptFor === p.id && <form className="stack" onSubmit={e=>{e.preventDefault();void action(async()=>{await automationRequest(`/proposals/${p.id}/receipt`,'POST',{operation_key:receiptKey,quantity:receiptQty,physical_confirmed:receiptPhysical,reason});setReceiptFor(null);});}}>
          <label>Cantidad recibida ({p.plan.unit})<input required type="number" step="0.0001" min="0.0001" max={p.purchase_pending_qty ?? undefined} value={receiptQty} onChange={e=>setReceiptQty(e.target.value)} /></label>
          <label><input required type="checkbox" checked={receiptPhysical} onChange={e=>setReceiptPhysical(e.target.checked)} /> Confirmo la recepción física de estas unidades</label>
          <button className="primary-btn" type="submit" disabled={busy || stopped || reason.trim().length < 3}>Confirmar recepción #{p.id}</button>
        </form>}
        <details><summary>Evaluación posterior</summary>{p.evaluation ? <><p>Periodo: {date(p.evaluation.period_start)} — {date(p.evaluation.period_end)}. Evaluación descriptiva sin atribución causal.</p><table><thead><tr><th>Previsto (unidades)</th><th>Despachado (unidades)</th><th>Devuelto</th><th>MAE</th><th>WAPE</th><th>Sesgo</th><th>Objetivo verificado</th></tr></thead><tbody><tr><td>{p.evaluation.expected_dispatch}</td><td>{p.evaluation.observed.sold}</td><td>{p.evaluation.observed.returned}</td><td>{p.evaluation.forecast_metrics.mae}</td><td>{display(p.evaluation.forecast_metrics.wape)}</td><td>{p.evaluation.forecast_metrics.bias}</td><td>{display(p.evaluation.objective_met)}</td></tr></tbody></table><Series title={`Previsto y observado · propuesta #${p.id}`} unit={p.plan.unit} points={[{label:'Previsión',value:Number(p.evaluation.expected_dispatch)},{label:'Despachado',value:Number(p.evaluation.observed.sold)}]} /><pre>{JSON.stringify(p.evaluation,null,2)}</pre></> : <p>Pendiente o no evaluable. No se presupone un resultado positivo.</p>}</details>
      </article>)}<button className="chip-btn" disabled={busy || !permissions.includes('read')} onClick={() => void action(() => automationRequest('/evaluate','POST'))}>Revisar resultados vencidos</button>
      <p>MAE: media del error absoluto en unidades. WAPE: error absoluto total dividido por unidades observadas; no disponible si el denominador es cero. Sesgo: media de previsión menos observado. Son métricas de despachos, no de demanda no observada.</p>
    </section>
  </div>;
}
