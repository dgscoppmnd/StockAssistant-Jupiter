import { FormEvent, useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import { automationRequest, searchProductOptions, updateAutomationRule } from '../api';
import type { Rule } from './AgentControlPage';
import RuleScopePicker, {type ScopeOption,type ScopePage} from './components/RuleScopePicker';
import {parseScopeIds} from '../utils/ruleScope';

type ScopeDefaults={product_ids:number[];warehouse_ids:number[];products:ScopeOption[];
  warehouses:(ScopeOption&{is_active:boolean})[]};
const loadScopeProducts=async(query:string,cursor:number,signal:AbortSignal):Promise<ScopePage>=>{
  const page=await searchProductOptions(query,cursor,signal);
  return {items:page.items.map(p=>({id:p.pk_product,code:p.cdgo_producto_externo,name:p.name_product})),next_cursor:page.next_cursor};
};
const hydrateScopeProducts=(ids:number[])=>automationRequest<ScopeOption[]>(`/scope-products?ids=${ids.join(',')}`);
function RuleScopeSummary({rule,defaults}:{rule:Rule;defaults:ScopeDefaults}){
  const products=(rule.config?.product_ids as number[] | undefined)??[],warehouses=(rule.config?.warehouse_ids as number[] | undefined)??[];
  return <p className="muted">Productos: {products.length?products.join(', '):`Compras prioritarias (${defaults.product_ids.join(', ')||'sin referencias actuales'})`}
    {' · '}Almacenes: {warehouses.length?warehouses.join(', '):`Almacén activo con más existencias (${defaults.warehouse_ids.join(', ')||'no disponible'})`}</p>;
}

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
  review_days:30,max_entities:30,max_model_calls:1,max_tool_calls:0,max_seconds:120,allow_unmetered_paid_ai:false,conditions:{mode:'all',items:[]}};
const numbers: {key: keyof Config; label: string; min: number; max: number; decimal?: boolean}[] = [
  {key:'interval_minutes',label:'Frecuencia (minutos)',min:15,max:525600},{key:'window_start_hour',label:'Inicio de ventana (hora)',min:0,max:23},{key:'window_end_hour',label:'Fin de ventana (hora)',min:1,max:24},
  {key:'target_days',label:'Cobertura objetivo (días)',min:1,max:365,decimal:true},{key:'safety_qty',label:'Stock de seguridad (unidades base)',min:0,max:1000000,decimal:true},
  {key:'minimum_order',label:'Compra mínima (unidades base)',min:0,max:1000000,decimal:true},{key:'order_multiple',label:'Múltiplo de compra (unidades base)',min:0.0001,max:1000000,decimal:true},
  {key:'stagnant_days',label:'Días sin ventas para revisión',min:7,max:730},{key:'maximum_coverage_days',label:'Cobertura excesiva (días)',min:1,max:730,decimal:true},
  {key:'origin_min_days',label:'Cobertura mínima del origen (días)',min:1,max:365,decimal:true},{key:'minimum_margin_percent',label:'Margen mínimo (%)',min:0,max:99.99,decimal:true},
  {key:'per_action_budget',label:'Presupuesto por acción (EUR)',min:0,max:100000000,decimal:true},{key:'daily_budget',label:'Presupuesto diario (EUR, UTC)',min:0,max:100000000,decimal:true},
  {key:'expires_hours',label:'Caducidad de propuestas (horas)',min:1,max:168},{key:'cooldown_hours',label:'Enfriamiento entre acciones (horas)',min:1,max:720},{key:'review_days',label:'Revisión del resultado (días)',min:1,max:365},
  {key:'max_entities',label:'Máximo de entidades por ciclo',min:1,max:100},{key:'max_seconds',label:'Duración máxima de análisis (segundos)',min:10,max:240},
];

const ruleKinds: Record<string, string> = {stock_reorder_proposals:'Reposición',stagnant_stock:'Stock estancado',daily_inventory_report:'Informe diario',risk_alerts:'Riesgos'};

function RuleIcon({kind}: {kind:'rules' | 'plus' | 'back'}) {
  return <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
    {kind === 'rules' && <><path d="M4 6h16M4 12h16M4 18h16"/><circle cx="9" cy="6" r="2"/><circle cx="15" cy="12" r="2"/><circle cx="9" cy="18" r="2"/></>}
    {kind === 'plus' && <path d="M12 5v14M5 12h14"/>}
    {kind === 'back' && <path d="m10 5-7 7 7 7M3 12h18"/>}
  </svg>;
}

export default function AgentRulesPage() {
  const [rules,setRules] = useState<Rule[]>([]), [selected,setSelected] = useState<Rule | null>(null), [config,setConfig] = useState<Config>(initial);
  const [name,setName] = useState(''),[description,setDescription] = useState(''),[reason,setReason] = useState(''),[status,setStatus] = useState('Cargando reglas…'),[error,setError] = useState('');
  const [simulation,setSimulation] = useState<unknown>(null),[versions,setVersions] = useState<{version:number; author:string; reason:string; created_at:string; config:Config}[]>([]),[busy,setBusy] = useState(false);
  const [permissions,setPermissions] = useState<string[]>([]);
  const [objectives,setObjectives] = useState<Record<string,string[]>>({});
  const [defaults,setDefaults]=useState<ScopeDefaults>({product_ids:[],warehouse_ids:[],products:[],warehouses:[]});
  const warehouses=useMemo(()=>defaults.warehouses.map(w=>({...w,name:w.name+(w.is_active?'':' (inactivo)')})),[defaults.warehouses]);
  const loadWarehouses=useCallback(async(query:string,cursor:number):Promise<ScopePage>=>{
    const matches=warehouses.filter(w=>`${w.id} ${w.code??''} ${w.name}`.toLocaleLowerCase().includes(query.toLocaleLowerCase()));
    return {items:matches.slice(cursor,cursor+12),next_cursor:cursor+12<matches.length?cursor+12:null};
  },[warehouses]);
  const hydrateWarehouses=useCallback(async(ids:number[])=>warehouses.filter(w=>ids.includes(w.id)),[warehouses]);
  const [productScope,setProductScope]=useState(''), [warehouseScope,setWarehouseScope]=useState('');
  const [loading,setLoading] = useState(true);
  const editorRef = useRef<HTMLElement>(null);
  const scopedConfig = () => {
    return {...config,product_ids:parseScopeIds(productScope),warehouse_ids:parseScopeIds(warehouseScope)};
  };
  const load = async () => {const [r,c,o,d] = await Promise.all([automationRequest<Rule[]>('/rules'),automationRequest<{permissions:string[]}>('/control'),automationRequest<Record<string,string[]>>('/objectives'),automationRequest<ScopeDefaults>('/scope-defaults')]);setRules(r);setPermissions(c.permissions);setObjectives(o);setDefaults(d);return d;};
  useEffect(() => {void load().then(()=>{setStatus('Reglas sincronizadas');}).catch(e => {setError(String(e));setStatus('No se pudieron sincronizar las reglas');}).finally(() => setLoading(false));},[]);
  const edit = async (r: Rule | null) => {
    const products=(r?.config?.product_ids as number[] | undefined)??[],warehouseIds=(r?.config?.warehouse_ids as number[] | undefined)??[];
    setProductScope(products.join(','));setWarehouseScope(warehouseIds.join(','));
    setSelected(r);setName(r?.name ?? '');setDescription(r?.description ?? '');setReason('');setSimulation(null);setError('');
    const kind = r?.code ?? initial.kind;
    setConfig(r?.config ? {...initial,...r.config} as Config : {...initial,kind,objective:objectives[kind]?.[0] ?? initial.objective});
    if (window.matchMedia('(max-width: 1100px)').matches) editorRef.current?.scrollIntoView({behavior:window.matchMedia('(prefers-reduced-motion: reduce)').matches ? 'instant' : 'smooth',block:'start'});
    if(r) {try {setVersions(await automationRequest(`/rules/${r.id}/versions`));} catch(e) {setError(String(e));}} else setVersions([]);
  };
  const change = (patch: Partial<Config>) => {setConfig(c => ({...c,...patch}));setSimulation(null);};
  const perform = async (fn: () => Promise<unknown>) => {setBusy(true);setError('');try {await fn();}catch(e){setError(e instanceof Error ? e.message : String(e));}finally{setBusy(false);}};
  const save = (e: FormEvent) => {e.preventDefault();void perform(async () => {
    const result = await automationRequest<{id:number}>(selected ? `/rules/${selected.id}` : '/rules', selected ? 'PUT' : 'POST', {name,description,reason,expected_version:selected?.current_version ?? 0,config:scopedConfig()});
    await load();const r = await automationRequest<Rule[]>('/rules');await edit(r.find(x => x.id === result.id) ?? null);setStatus('Versión guardada y pausada. Propuestas pendientes anteriores invalidadas.');
  });};
  const numericFields = (keys: (keyof Config)[]) => numbers.filter(n => keys.includes(n.key)).map(n => <label key={n.key}>{n.label}<input required type="number" min={n.min} max={n.max} step={n.decimal ? '0.0001' : '1'} value={String(config[n.key])} onChange={e => change({[n.key]:n.decimal ? e.target.value : Number(e.target.value)})} /></label>);
  return <div className="agent-control rules-workspace">
    <section className="card rules-header">
      <div className="rules-header-top"><div><p className="section-label">Automatización · configuración</p><h3><RuleIcon kind="rules"/>Editor de reglas</h3><p className="rules-description">Define objetivos, ajusta límites y valida cada versión antes de activarla.</p></div><Link className="rules-back" to="/agentes/control"><RuleIcon kind="back"/>Centro de control</Link></div>
      <div className="rules-overview" aria-label="Resumen de reglas"><span><strong>{loading ? '—' : rules.length}</strong> reglas</span><span><i className="rules-dot rules-dot--active"/><strong>{loading ? '—' : rules.filter(r=>r.is_active).length}</strong> activas</span><span><i className="rules-dot"/><strong>{loading ? '—' : rules.filter(r=>!r.is_active).length}</strong> pausadas</span><span className="rules-sync" role="status" aria-live="polite">{busy ? 'Procesando cambios…' : status}</span></div>
      {error && <div className="rules-error" role="alert"><span>{error}</span><button className="chip-btn" disabled={busy} onClick={() => void perform(async()=>{await load();setStatus('Reglas sincronizadas');})}>Reintentar</button></div>}
    </section>
    <div className="rules-layout">
      <section className="card rules-library" aria-label="Reglas existentes" aria-busy={loading}>
        <div className="rules-section-title"><h3>Mis reglas <span className="rules-count">{rules.length}</span></h3><button className="chip-btn" disabled={busy} onClick={() => void edit(null)}><RuleIcon kind="plus"/>Nueva</button></div>
        {loading ? <p className="rules-empty" role="status">Cargando reglas…</p> : !rules.length ? <div className="rules-empty"><RuleIcon kind="rules"/><strong>{error ? 'Listado no disponible' : 'Tu primera automatización'}</strong><p>{error ? 'Reintenta la conexión para consultar tus reglas.' : 'Completa el editor para crear una regla con sus propios objetivos y límites.'}</p></div> : <div className="rules-list">{rules.map(r=><article className={`agent-rule rules-list-item${selected?.id === r.id ? ' is-selected' : ''}`} key={r.id}>
          <div className="rules-item-meta"><span className={`rules-badge${r.is_active ? ' rules-badge--active' : ''}`}><i className="rules-dot"/>{r.is_active ? 'Activa' : 'Pausada'}</span><span className="rules-version">v{r.current_version}</span></div>
          <h4>{r.name}</h4><p>{r.description || 'Sin descripción'}</p><span className="rules-kind">{ruleKinds[String(r.config?.kind ?? r.code)] ?? r.code}</span>
          <RuleScopeSummary rule={r} defaults={defaults} />
          <div className="rules-item-actions"><button className="chip-btn" disabled={busy} aria-pressed={selected?.id === r.id} onClick={() => void edit(r)}>{selected?.id === r.id ? 'Editando' : 'Editar regla'}</button><button className="rules-text-button" disabled={busy || !permissions.includes('activate')} onClick={() => void perform(async()=>{await updateAutomationRule(r.id,!r.is_active);await load();setStatus(r.is_active ? 'Regla desactivada' : 'Regla activada: habilita análisis, los permisos operativos se validan por separado');})}>{r.is_active ? 'Pausar' : 'Activar versión'}</button></div>
        </article>)}</div>}
      </section>
      <div className="rules-editor-column">
        <section className="card rules-editor" ref={editorRef}>
          <div className="rules-section-title"><div><p className="section-label">{selected ? `Edición · base v${selected.current_version}` : 'Nueva automatización'}</p><h3>{selected ? selected.name : 'Crear regla'}</h3></div><span className="rules-badge">Borrador</span></div>
          <p className="rules-save-note">Al guardar se crea una versión pausada y se invalidan las propuestas pendientes de versiones anteriores.</p>
          <form onSubmit={save}>
            <fieldset className="rules-form-section"><legend><span>01</span>Identidad y objetivo</legend><div className="agent-fields">
              <label className="rules-field-wide">Nombre<input required minLength={3} maxLength={160} placeholder="Ej. Reposición de productos esenciales" value={name} onChange={e=>setName(e.target.value)}/></label>
              <label>Tipo de regla<select value={config.kind} onChange={e=>change({kind:e.target.value,objective:objectives[e.target.value]?.[0] ?? '',...(['daily_inventory_report','risk_alerts'].includes(e.target.value) ? {mode:'observation',allowed_actions:[],conditions:{mode:'all',items:[]}} : {})})}>{Object.entries(ruleKinds).map(([value,label])=><option value={value} key={value}>{label}</option>)}</select></label>
              <label>Autonomía<select value={config.mode} onChange={e=>change({mode:e.target.value,allowed_actions:[]})}><option value="observation">Observación</option><option value="assisted">Asistido</option>{['stock_reorder_proposals','stagnant_stock'].includes(config.kind) && <option value="limited_auto">Automático limitado</option>}</select></label>
              <label className="rules-field-wide">Descripción<textarea rows={2} maxLength={2000} placeholder="Qué hace esta regla y cuándo resulta útil" value={description} onChange={e=>setDescription(e.target.value)}/></label>
              <label className="rules-field-wide">Objetivo<select required value={(objectives[config.kind] ?? []).includes(config.objective) ? config.objective : ''} onChange={e=>change({objective:e.target.value})}>
                <option value="" disabled>Selecciona un objetivo dentro del alcance de la regla</option>
                {(objectives[config.kind] ?? []).map(objective=><option key={objective} value={objective}>{objective}</option>)}
              </select><small>Los objetivos admitidos dependen del tipo de regla. Ajusta cobertura, condiciones y límites en sus campos.</small></label>
              {!!Object.keys(objectives).length && !(objectives[config.kind] ?? []).includes(config.objective) && <p role="alert">El objetivo anterior no pertenece al catálogo permitido. Selecciona uno válido antes de guardar o simular.</p>}
              <label className="rules-field-wide">Métrica objetivo<textarea rows={2} readOnly value="Unidades despachadas confirmadas en el horizonte de revisión"/></label>
              <label className="rules-field-wide">Objetivo mínimo de despachos (unidades base)<input type="number" min="0" max="1000000000" step="0.0001" placeholder="Sin objetivo mínimo" value={config.objective_target ?? ''} onChange={e=>change({objective_target:e.target.value || null})}/><small>Si lo dejas vacío, el objetivo no será evaluable.</small></label>
            </div></fieldset>
            <fieldset className="rules-form-section"><legend><span>02</span>Alcance y programación</legend><div className="agent-fields">
              <RuleScopePicker label="Productos (IDs separados por comas)" hint="Vacío = productos de Compras prioritarias" value={productScope} onChange={value=>{setProductScope(value);setSimulation(null);}}
                loadOptions={loadScopeProducts} hydrateOptions={hydrateScopeProducts} initialOptions={defaults.products} />
              <RuleScopePicker label="Almacenes (IDs separados por comas)" hint="Vacío = almacén activo con más existencias físicas totales (en empate, menor ID)" value={warehouseScope} onChange={value=>{setWarehouseScope(value);setSimulation(null);}}
                loadOptions={loadWarehouses} hydrateOptions={hydrateWarehouses} initialOptions={warehouses} minQueryLength={1} />
              <label>Zona horaria<input required value={config.timezone} onChange={e=>change({timezone:e.target.value})}/></label>
              {numericFields(['interval_minutes','window_start_hour','window_end_hour','expires_hours','cooldown_hours','review_days'])}
            </div></fieldset>
            <fieldset className="rules-form-section"><legend><span>03</span>Inventario y cobertura</legend><div className="agent-fields">
              {numericFields(['target_days','safety_qty','minimum_order','order_multiple','stagnant_days','maximum_coverage_days','origin_min_days','minimum_margin_percent'])}
              <label>Plazo estimado (días)<input type="number" min="0" max="365" placeholder="Desconocido" value={config.lead_days ?? ''} onChange={e=>change({lead_days:e.target.value || null})}/></label>
            </div></fieldset>
            <fieldset className="rules-form-section"><legend><span>04</span>Presupuesto y límites</legend><div className="agent-fields">{numericFields(['per_action_budget','daily_budget','max_entities','max_seconds'])}</div>
              <label className="rules-check"><input type="checkbox" checked={config.simulation} onChange={e=>change({simulation:e.target.checked})}/><span>Ejecutar siempre en simulación<small>Sin propuestas persistidas ni acciones operativas.</small></span></label>
              {['stock_reorder_proposals','stagnant_stock'].includes(config.kind) && <label className="rules-check"><input type="checkbox" checked={config.max_model_calls > 0} onChange={e=>change({max_model_calls:e.target.checked ? 1 : 0,max_tool_calls:0})}/><span>Permitir análisis con IA<small>Una única consulta con la evidencia disponible; puede terminar sin propuestas si faltan datos.</small></span></label>}
              <label className="rules-check"><input type="checkbox" checked={config.allow_unmetered_paid_ai} onChange={e=>change({allow_unmetered_paid_ai:e.target.checked})}/><span>Autorizar IA sin información de coste<small>Requiere permiso de autorización.</small></span></label>
              {config.mode === 'limited_auto' && <div className="rules-policy"><h4>Acciones expresamente autorizadas</h4><label className="rules-check"><input type="checkbox" checked={config.allowed_actions.includes('suspend_reorder')} onChange={e=>change({allowed_actions:e.target.checked ? ['suspend_reorder'] : []})}/><span>Suspender propuestas automáticas por producto y almacén</span></label><p>Comprar necesita oferta vigente confirmada. Trasladar necesita confirmación física; publicar campañas necesita integración y autorización específicas.</p></div>}
            </fieldset>
            {['stock_reorder_proposals','stagnant_stock'].includes(config.kind) && <fieldset className="rules-form-section"><legend><span>05</span>Condiciones declarativas</legend><label className="rules-condition-mode">Cumplimiento<select value={config.conditions.mode} onChange={e=>change({conditions:{...config.conditions,mode:e.target.value}})}><option value="all">Todas las condiciones</option><option value="any">Cualquiera de las condiciones</option></select></label>
              {!config.conditions.items.length && <p className="rules-hint">Sin condiciones adicionales. Se aplicarán los objetivos y límites de la regla.</p>}
              {config.conditions.items.map((c,i)=><div className="rules-condition" key={i}><span className="rules-condition-number">{String(i+1).padStart(2,'0')}</span><label>Campo<select value={c.field} onChange={e=>change({conditions:{...config.conditions,items:config.conditions.items.map((v,j)=>j===i ? {...v,field:e.target.value} : v)}})}>{[['available','Disponible (unidad base)'],['pending','Pendiente (unidad base)'],['sold_90','Despachos en 90 días (unidad base)'],['coverage_days','Cobertura (días)'],['days_without_sales','Días desde último despacho']].map(([v,l])=><option value={v} key={v}>{l}</option>)}</select></label><label>Operador<select value={c.operator} onChange={e=>change({conditions:{...config.conditions,items:config.conditions.items.map((v,j)=>j===i ? {...v,operator:e.target.value} : v)}})}>{[['lt','Menor que'],['lte','Menor o igual'],['gt','Mayor que'],['gte','Mayor o igual'],['eq','Igual a']].map(([v,l])=><option value={v} key={v}>{l}</option>)}</select></label><label>Umbral<input required type="number" min="0" step="0.0001" value={c.value} onChange={e=>change({conditions:{...config.conditions,items:config.conditions.items.map((v,j)=>j===i ? {...v,value:e.target.value} : v)}})}/></label><button className="rules-text-button" type="button" onClick={()=>change({conditions:{...config.conditions,items:config.conditions.items.filter((_,j)=>j!==i)}})}>Quitar condición {i+1}</button></div>)}
              <button className="chip-btn" type="button" disabled={config.conditions.items.length>=12} onClick={()=>change({conditions:{...config.conditions,items:[...config.conditions.items,{field:'available',operator:'lt',value:'1'}]}})}><RuleIcon kind="plus"/>Añadir condición</button>
            </fieldset>}
            {['daily_inventory_report','risk_alerts'].includes(config.kind) && <p className="rules-hint">Este informe se calcula sin IA y sin acciones automáticas. Se aplican los filtros de productos y almacenes; las condiciones de stock corresponden a reposición y stock estancado.</p>}
            <div className="rules-form-footer"><label>Motivo del cambio<input required minLength={3} maxLength={500} placeholder="Describe el motivo de esta versión" value={reason} onChange={e=>setReason(e.target.value)}/></label><div className="rules-footer-actions"><button className="chip-btn" type="button" disabled={busy || !permissions.includes('edit')} onClick={()=>void perform(async()=>{setSimulation(await automationRequest('/simulate','POST',scopedConfig()));setStatus('Simulación completada, sin efectos operativos');})}>Validar y simular</button><button className="primary-btn" type="submit" disabled={busy || !permissions.includes('edit')}>{busy ? 'Procesando…' : 'Guardar versión pausada'}</button></div>{!loading && !permissions.includes('edit') && <p className="rules-hint">Necesitas permiso de edición para guardar o simular reglas.</p>}</div>
          </form>
        </section>
        {simulation !== null && <section className="card rules-simulation"><p className="section-label">Resultado de validación</p><h3>Simulación · datos reales</h3><p className="rules-hint">No crea pedidos, movimientos, campañas ni reservas. La instantánea no garantiza resultados futuros.</p><pre>{JSON.stringify(simulation,null,2)}</pre></section>}
        <section className="card rules-history"><div className="rules-section-title"><h3>Historial de versiones</h3><span className="rules-count">{versions.length}</span></div><p className="rules-hint">Restaurar carga un borrador nuevo y conserva todo el historial.</p>{!versions.length && <div className="rules-empty"><p>{selected ? 'Esta regla todavía no tiene versiones guardadas.' : 'Selecciona una regla para consultar sus versiones.'}</p></div>}{versions.map(v=><article className="agent-rule rules-history-item" key={v.version}><div className="rules-history-heading"><h4>Versión {v.version}</h4><time dateTime={v.created_at}>{new Date(v.created_at).toLocaleString('es-ES')}</time></div><p>{v.reason}</p><span className="rules-hint">{v.author}</span><details><summary>Ver diferencias con el borrador</summary><pre>{JSON.stringify(Object.fromEntries(Object.entries(v.config).filter(([k,value])=>JSON.stringify(value)!==JSON.stringify(config[k as keyof Config])).map(([k,value])=>[k,{historico:value,borrador:config[k as keyof Config]}])),null,2)}</pre></details><button className="chip-btn" onClick={()=>{change(v.config);setProductScope(v.config.product_ids.join(','));setWarehouseScope(v.config.warehouse_ids.join(','));setReason(`Restaurar configuración v${v.version}`);setStatus('Configuración histórica cargada. Guarda para crear una nueva versión.');}}>Restaurar como borrador</button></article>)}</section>
      </div>
    </div>
  </div>;
}
