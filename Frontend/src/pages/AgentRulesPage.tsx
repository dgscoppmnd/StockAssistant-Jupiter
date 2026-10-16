import { FormEvent, useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { automationRequest, updateAutomationRule } from '../api';
import type { Rule } from './AgentControlPage';

type Condition = {field: string; operator: string; value: string};
type Config = {
  kind: string; objective: string; objective_metric:string;objective_target:string | null; mode: string; simulation: boolean; interval_minutes: number; timezone: string;
  window_start_hour: number; window_end_hour: number; product_ids: number[]; warehouse_ids: number[];
  target_days: string; safety_qty: string; minimum_order: string; order_multiple: string; lead_days: string | null;
  stagnant_days: number; maximum_coverage_days: string; origin_min_days: string; minimum_margin_percent: string;
  per_action_budget: string; daily_budget: string; allowed_actions: string[]; expires_hours: number; cooldown_hours: number;
  review_days: number; max_entities: number; max_model_calls: number; max_tool_calls: number; max_seconds: number;
  allow_unmetered_paid_ai: boolean; conditions: {mode: string; items: Condition[]};
};
const initial: Config = {objective_metric:'confirmed_dispatch_qty',objective_target:null,kind:'stock_reorder_proposals', objective:'Reducir roturas manteniendo cobertura y capital', mode:'assisted', simulation:false,
  interval_minutes:1440,timezone:'Europe/Madrid',window_start_hour:0,window_end_hour:24,product_ids:[],warehouse_ids:[],target_days:'30',safety_qty:'0',minimum_order:'0',order_multiple:'1',lead_days:null,
  stagnant_days:90,maximum_coverage_days:'120',origin_min_days:'30',minimum_margin_percent:'20',per_action_budget:'0',daily_budget:'0',allowed_actions:[],expires_hours:24,cooldown_hours:24,
  review_days:30,max_entities:30,max_model_calls:2,max_tool_calls:4,max_seconds:120,allow_unmetered_paid_ai:false,conditions:{mode:'all',items:[]}};
const numbers: {key: keyof Config; label: string; min: number; max: number; decimal?: boolean}[] = [
  {key:'interval_minutes',label:'Frecuencia (minutos)',min:15,max:525600},{key:'window_start_hour',label:'Inicio de ventana (hora)',min:0,max:23},{key:'window_end_hour',label:'Fin de ventana (hora)',min:1,max:24},
  {key:'target_days',label:'Cobertura objetivo (días)',min:1,max:365,decimal:true},{key:'safety_qty',label:'Stock de seguridad (unidades base)',min:0,max:1000000,decimal:true},
  {key:'minimum_order',label:'Compra mínima (unidades base)',min:0,max:1000000,decimal:true},{key:'order_multiple',label:'Múltiplo de compra (unidades base)',min:0.0001,max:1000000,decimal:true},
  {key:'stagnant_days',label:'Días sin ventas para revisión',min:7,max:730},{key:'maximum_coverage_days',label:'Cobertura excesiva (días)',min:1,max:730,decimal:true},
  {key:'origin_min_days',label:'Cobertura mínima del origen (días)',min:1,max:365,decimal:true},{key:'minimum_margin_percent',label:'Margen mínimo (%)',min:0,max:99.99,decimal:true},
  {key:'per_action_budget',label:'Presupuesto por acción (EUR)',min:0,max:100000000,decimal:true},{key:'daily_budget',label:'Presupuesto diario (EUR, UTC)',min:0,max:100000000,decimal:true},
  {key:'expires_hours',label:'Caducidad de propuestas (horas)',min:1,max:168},{key:'cooldown_hours',label:'Enfriamiento entre acciones (horas)',min:1,max:720},{key:'review_days',label:'Revisión del resultado (días)',min:1,max:365},
  {key:'max_entities',label:'Máximo de entidades por ciclo',min:1,max:100},{key:'max_model_calls',label:'Máximo de llamadas IA',min:0,max:3},{key:'max_tool_calls',label:'Máximo de herramientas',min:0,max:10},{key:'max_seconds',label:'Duración máxima de análisis (segundos)',min:10,max:240},
];

export default function AgentRulesPage() {
  const [rules,setRules] = useState<Rule[]>([]), [selected,setSelected] = useState<Rule | null>(null), [config,setConfig] = useState<Config>(initial);
  const [name,setName] = useState(''),[description,setDescription] = useState(''),[reason,setReason] = useState(''),[status,setStatus] = useState('Cargando reglas…'),[error,setError] = useState('');
  const [simulation,setSimulation] = useState<unknown>(null),[versions,setVersions] = useState<{version:number; author:string; reason:string; created_at:string; config:Config}[]>([]),[busy,setBusy] = useState(false);
  const [permissions,setPermissions] = useState<string[]>([]);
  const [productScope,setProductScope]=useState(''), [warehouseScope,setWarehouseScope]=useState('');
  const scopedConfig = () => {
    const parse=(text:string) => {if(!text.trim()) return []; const ids=text.split(',').map(x=>Number(x.trim())); if(ids.some(x=>!Number.isSafeInteger(x) || x<=0)) throw new Error('Indica identificadores positivos separados por comas'); return ids;};
    return {...config,product_ids:parse(productScope),warehouse_ids:parse(warehouseScope)};
  };
  const load = async () => {const [r,c] = await Promise.all([automationRequest<Rule[]>('/rules'),automationRequest<{permissions:string[]}>('/control')]);setRules(r);setPermissions(c.permissions);};
  useEffect(() => {void load().then(() => setStatus('Reglas sincronizadas')).catch(e => setError(String(e)));},[]);
  const edit = async (r: Rule | null) => {
    setProductScope(((r?.config?.product_ids as number[]) ?? []).join(','));setWarehouseScope(((r?.config?.warehouse_ids as number[]) ?? []).join(','));
    setSelected(r);setName(r?.name ?? '');setDescription(r?.description ?? '');setReason('');setSimulation(null);setError('');
    setConfig(r?.config ? {...initial,...r.config} as Config : {...initial,kind:r?.code ?? initial.kind});
    if(r) {try {setVersions(await automationRequest(`/rules/${r.id}/versions`));} catch(e) {setError(String(e));}} else setVersions([]);
  };
  const change = (patch: Partial<Config>) => {setConfig(c => ({...c,...patch}));setSimulation(null);};
  const perform = async (fn: () => Promise<unknown>) => {setBusy(true);setError('');try {await fn();}catch(e){setError(e instanceof Error ? e.message : String(e));}finally{setBusy(false);}};
  const save = (e: FormEvent) => {e.preventDefault();void perform(async () => {
    const result = await automationRequest<{id:number}>(selected ? `/rules/${selected.id}` : '/rules', selected ? 'PUT' : 'POST', {name,description,reason,expected_version:selected?.current_version ?? 0,config:scopedConfig()});
    await load();const r = await automationRequest<Rule[]>('/rules');await edit(r.find(x => x.id === result.id) ?? null);setStatus('Versión guardada y pausada. Propuestas pendientes anteriores invalidadas.');
  });};
  return <div className="grid agent-control"><section className="card"><p className="section-label">Configuración con versiones</p><h3>Editor de reglas</h3><p>Agente responsable: AutomationService. Guardar crea una versión pausada e invalida propuestas pendientes de versiones anteriores. Restaurar crea un nuevo borrador; el historial se conserva.</p><Link to="/agentes/control">Volver al centro de control</Link><p role="status" aria-live="polite">{status}</p>{error && <p className="error-line" role="alert">{error}</p>}</section>
    <section className="card"><h3>Reglas existentes</h3><button className="chip-btn" onClick={() => void edit(null)}>Nueva regla</button>{rules.map(r => <article className="agent-rule" key={r.id}><strong>{r.name} · v{r.current_version} · {r.is_active ? 'Activa' : 'Pausada'}</strong><p>{r.description}</p><button className="chip-btn" onClick={() => void edit(r)}>Editar</button><button className="chip-btn" disabled={busy || !permissions.includes('activate')} onClick={() => void perform(async () => {await updateAutomationRule(r.id,!r.is_active);await load();setStatus(r.is_active ? 'Regla desactivada' : 'Regla activada: habilita análisis, los permisos operativos se validan por separado');})}>{r.is_active ? 'Desactivar' : 'Activar versión'}</button></article>)}</section>
    <section className="card"><h3>{selected ? `Editar ${selected.name} · base v${selected.current_version}` : 'Crear regla'}</h3><form className="stack" onSubmit={save}>
      <label>Nombre<input required minLength={3} maxLength={160} value={name} onChange={e => setName(e.target.value)} /></label>
      <label>Descripción<textarea maxLength={2000} value={description} onChange={e => setDescription(e.target.value)} /></label>
      <label>Objetivo<textarea required minLength={3} maxLength={500} value={config.objective} onChange={e => change({objective:e.target.value})} /></label>
      <div className="agent-fields"><label>Tipo de regla<select value={config.kind} onChange={e => change({kind:e.target.value})}><option value="stock_reorder_proposals">Reposición</option><option value="stagnant_stock">Stock estancado</option><option value="daily_inventory_report">Informe diario</option><option value="risk_alerts">Riesgos</option></select></label>
        <label>Autonomía<select value={config.mode} onChange={e => change({mode:e.target.value,allowed_actions:[]})}><option value="observation">Observación</option><option value="assisted">Asistido</option><option value="limited_auto">Automático limitado</option></select></label>
        <label>Zona horaria<input required value={config.timezone} onChange={e => change({timezone:e.target.value})} /></label>
        <label>Productos (IDs separados por comas, vacío = todos)<input pattern="[0-9, ]*" value={productScope} onChange={e => {setProductScope(e.target.value);setSimulation(null);}} /></label>
        <label>Almacenes (IDs separados por comas, vacío = todos)<input pattern="[0-9, ]*" value={warehouseScope} onChange={e => {setWarehouseScope(e.target.value);setSimulation(null);}} /></label>
        <label>Métrica objetivo<input readOnly value="Unidades despachadas confirmadas en el horizonte de revisión" /></label><label>Objetivo mínimo de despachos (unidades base, vacío = no evaluable)<input type="number" min="0" max="1000000000" step="0.0001" value={config.objective_target ?? ""} onChange={e=>change({objective_target:e.target.value || null})} /></label>
        <label>Plazo estimado (días, vacío = desconocido)<input type="number" min="0" max="365" value={config.lead_days ?? ''} onChange={e => change({lead_days:e.target.value || null})} /></label>
        {numbers.map(n => <label key={n.key}>{n.label}<input required type="number" min={n.min} max={n.max} step={n.decimal ? '0.0001' : '1'} value={String(config[n.key])} onChange={e => change({[n.key]:n.decimal ? e.target.value : Number(e.target.value)})} /></label>)}
      </div>
      <label><input type="checkbox" checked={config.simulation} onChange={e => change({simulation:e.target.checked})} /> Ejecutar esta regla siempre en simulación (sin propuestas persistidas ni acciones)</label>
      <label><input type="checkbox" checked={config.allow_unmetered_paid_ai} onChange={e => change({allow_unmetered_paid_ai:e.target.checked})} /> Autorizar IA cuyo proveedor no facilita coste (requiere permiso de autorización)</label>
      {config.mode === 'limited_auto' && <fieldset><legend>Acciones expresamente autorizadas</legend><label><input type="checkbox" checked={config.allowed_actions.includes('suspend_reorder')} onChange={e => change({allowed_actions:e.target.checked ? ['suspend_reorder'] : []})} /> Suspender propuestas automáticas por producto y almacén</label><p>Comprar necesita oferta vigente confirmada. Trasladar necesita confirmación física; publicar campañas necesita integración y autorización específicas.</p></fieldset>}
      <fieldset><legend>Condiciones declarativas</legend><label>Grupo<select value={config.conditions.mode} onChange={e => change({conditions:{...config.conditions,mode:e.target.value}})}><option value="all">Todas</option><option value="any">Cualquiera</option></select></label>
        {config.conditions.items.map((c,i) => <div className="agent-fields" key={i}><label>Campo<select value={c.field} onChange={e => change({conditions:{...config.conditions,items:config.conditions.items.map((v,j)=> j === i ? {...v,field:e.target.value} : v)}})}>{[['available','Disponible (unidad base)'],['pending','Pendiente (unidad base)'],['sold_90','Despachos en 90 días (unidad base)'],['coverage_days','Cobertura (días)'],['days_without_sales','Días desde último despacho']].map(([v,l]) => <option value={v} key={v}>{l}</option>)}</select></label><label>Operador<select value={c.operator} onChange={e => change({conditions:{...config.conditions,items:config.conditions.items.map((v,j)=> j === i ? {...v,operator:e.target.value} : v)}})}>{['lt','lte','gt','gte','eq'].map(v => <option key={v}>{v}</option>)}</select></label><label>Umbral<input required type="number" min="0" step="0.0001" value={c.value} onChange={e => change({conditions:{...config.conditions,items:config.conditions.items.map((v,j)=> j === i ? {...v,value:e.target.value} : v)}})} /></label><button className="chip-btn" type="button" onClick={() => change({conditions:{...config.conditions,items:config.conditions.items.filter((_,j)=>j !== i)}})}>Quitar condición {i+1}</button></div>)}
        <button className="chip-btn" type="button" disabled={config.conditions.items.length >= 12} onClick={() => change({conditions:{...config.conditions,items:[...config.conditions.items,{field:'available',operator:'lt',value:'1'}]}})}>Añadir condición</button>
      </fieldset>
      <label>Motivo del cambio<input required minLength={3} maxLength={500} value={reason} onChange={e => setReason(e.target.value)} /></label>
      <div><button className="primary-btn" type="submit" disabled={busy || !permissions.includes('edit')}>Guardar nueva versión pausada</button>{' '}<button className="chip-btn" type="button" disabled={busy || !permissions.includes('edit')} onClick={() => void perform(async () => {setSimulation(await automationRequest('/simulate','POST',scopedConfig()));setStatus('Simulación completada, sin efectos operativos');})}>Validar y simular instantánea</button></div>
    </form></section>
    {simulation !== null && <section className="card"><h3>Simulación · datos reales</h3><p>No crea pedidos, movimientos, campañas ni reservas. La instantánea no garantiza resultados futuros.</p><pre>{JSON.stringify(simulation,null,2)}</pre></section>}
    <section className="card"><h3>Historial y restauración</h3>{!versions.length && <p>No hay versiones guardadas.</p>}{versions.map(v => <article className="agent-rule" key={v.version}><h4>Versión {v.version}</h4><p>{v.author} · {new Date(v.created_at).toLocaleString()} · {v.reason}</p><details><summary>Configuración y diferencias con el borrador</summary><pre>{JSON.stringify(Object.fromEntries(Object.entries(v.config).filter(([k,value]) => JSON.stringify(value) !== JSON.stringify(config[k as keyof Config])).map(([k,value]) => [k,{historico:value,borrador:config[k as keyof Config]}])),null,2)}</pre></details><button className="chip-btn" onClick={() => {change(v.config);setProductScope(v.config.product_ids.join(','));setWarehouseScope(v.config.warehouse_ids.join(','));setReason(`Restaurar configuración v${v.version}`);setStatus('Configuración histórica cargada. Guarda para crear una nueva versión.');}}>Restaurar como borrador</button></article>)}</section>
  </div>;
}
