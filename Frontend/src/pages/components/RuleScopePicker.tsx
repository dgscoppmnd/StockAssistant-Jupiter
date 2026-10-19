import {useEffect,useId,useRef,useState} from 'react';
import ComboboxPopup from './ComboboxPopup';
import {parseScopeIds,toggleScopeId} from '../../utils/ruleScope';

export type ScopeOption={id:number;code:string | null;name:string};
export type ScopePage={items:ScopeOption[];next_cursor:number | null};
type Props={label:string;hint:string;value:string;onChange:(value:string)=>void;disabled?:boolean;
  loadOptions:(query:string,cursor:number,signal:AbortSignal)=>Promise<ScopePage>;
  hydrateOptions:(ids:number[])=>Promise<ScopeOption[]>;initialOptions:ScopeOption[];minQueryLength?:number};

export default function RuleScopePicker({label,hint,value,onChange,disabled=false,loadOptions,hydrateOptions,initialOptions,minQueryLength=3}:Props){
  const id=useId(),input=useRef<HTMLInputElement>(null),root=useRef<HTMLDivElement>(null),panel=useRef<HTMLDivElement>(null);
  const known=useRef(new Map<number,ScopeOption>());
  const [open,setOpen]=useState(false),[query,setQuery]=useState(''),[cursors,setCursors]=useState([0]);
  const [page,setPage]=useState<ScopePage>({items:[],next_cursor:null}),[loading,setLoading]=useState(false);
  const [error,setError]=useState(''),[onlySelected,setOnlySelected]=useState(false),[retry,setRetry]=useState(0);
  const [,refresh]=useState(0);
  let ids:number[]=[];
  try{ids=parseScopeIds(value);}catch{/* Keep invalid manual input visible until corrected. */}
  const selected=new Set(ids),cursor=cursors[cursors.length-1],expanded=open&&!disabled;
  const shortQuery=query.trim().length>0&&query.trim().length<minQueryLength;
  useEffect(()=>{initialOptions.forEach(option=>known.current.set(option.id,option));refresh(v=>v+1);},[initialOptions]);
  useEffect(()=>{
    if(!expanded)return;
    let cancelled=false;
    const missing=ids.filter(selectedId=>!known.current.has(selectedId));
    if(missing.length)void hydrateOptions(missing).then(options=>{
      if(!cancelled){options.forEach(option=>known.current.set(option.id,option));refresh(v=>v+1);}
    }).catch(()=>{if(!cancelled)setError('No se pudieron cargar los nombres de los seleccionados. Los IDs se conservan.');});
    return()=>{cancelled=true;};
  },[expanded,value,hydrateOptions,retry]);
  useEffect(()=>{
    if(!expanded||shortQuery||onlySelected){setLoading(false);return;}
    const controller=new AbortController();setLoading(true);setError('');setPage({items:[],next_cursor:null});
    const timer=setTimeout(()=>{void loadOptions(query.trim(),cursor,controller.signal).then(data=>{
      if(!controller.signal.aborted){setPage(data);data.items.forEach(option=>known.current.set(option.id,option));}
    }).catch(e=>{if(!controller.signal.aborted)setError(e instanceof Error?e.message:'No se pudo cargar la lista');})
      .finally(()=>{if(!controller.signal.aborted)setLoading(false);});},query.trim()?300:0);
    return()=>{clearTimeout(timer);controller.abort();};
  },[expanded,query,cursor,shortQuery,onlySelected,loadOptions,retry]);
  useEffect(()=>{
    if(!expanded)return;
    const outside=(event:Event)=>{if(!root.current?.contains(event.target as Node)&&!panel.current?.contains(event.target as Node))setOpen(false);};
    const escape=(event:KeyboardEvent)=>{if(event.key==='Escape'){event.preventDefault();setOpen(false);input.current?.focus();}};
    document.addEventListener('pointerdown',outside);document.addEventListener('focusin',outside);document.addEventListener('keydown',escape);
    return()=>{document.removeEventListener('pointerdown',outside);document.removeEventListener('focusin',outside);document.removeEventListener('keydown',escape);};
  },[expanded]);
  const options=onlySelected?ids.map(selectedId=>known.current.get(selectedId)??{id:selectedId,code:null,name:`ID #${selectedId}`})
    .filter(option=>`${option.id} ${option.code??''} ${option.name}`.toLocaleLowerCase().includes(query.toLocaleLowerCase())):shortQuery?[]:page.items;
  return <div ref={root} className="rule-scope-picker">
    <label htmlFor={id}>{label}</label><div className="inventory-picker-input">
      <input ref={input} id={id} value={value} pattern="[0-9, ]*" disabled={disabled} placeholder={hint}
        aria-describedby={`${id}-hint`} onChange={event=>onChange(event.target.value)} />
      <button type="button" className="chip-btn" disabled={disabled} aria-expanded={expanded} aria-controls={expanded?`${id}-panel`:undefined}
        aria-haspopup="dialog" onClick={()=>setOpen(v=>!v)}>Seleccionar ▾</button>
    </div><small id={`${id}-hint`}>{hint}. Seleccionados: {ids.length}. La lista muestra código, nombre e ID.</small>
    {expanded&&<ComboboxPopup anchor={input} interactive><div ref={panel} id={`${id}-panel`} role="dialog" aria-label={`Seleccionar ${label}`} className="rule-scope-panel">
      <label htmlFor={`${id}-search`}>Buscar por código, nombre o ID</label>
      <input autoFocus type="search" id={`${id}-search`} value={query} maxLength={200} onChange={event=>{setQuery(event.target.value);setCursors([0]);}} />
      <button type="button" className="chip-btn" aria-pressed={onlySelected} onClick={()=>{setOnlySelected(v=>!v);setQuery('');setCursors([0]);}}>{onlySelected?'Ver catálogo':`Ver seleccionados (${ids.length})`}</button>
      <div role="group" aria-label={`Opciones de ${label}`} className="rule-scope-options">{options.map(option=><label key={option.id}>
        <input type="checkbox" checked={selected.has(option.id)} onChange={()=>{try{onChange(toggleScopeId(value,option.id));setError('');}catch(e){setError(String(e));}}} />
        <span>{option.code??'Sin código'} · {option.name} <small>ID {option.id}</small></span>
      </label>)}</div>
      <p role="status">{shortQuery&&!onlySelected?`Escribe al menos ${minQueryLength} caracteres.`:loading?'Buscando…':`${options.length} resultados · ${ids.length} seleccionados`}</p>
      {error&&<p role="alert">{error} <button type="button" className="chip-btn" onClick={()=>setRetry(v=>v+1)}>Reintentar</button></p>}
      <div className="rule-scope-actions">
        {!onlySelected&&<>
          <button type="button" className="chip-btn rule-scope-icon" aria-label="Página anterior" title="Página anterior" disabled={loading||cursors.length===1} onClick={()=>setCursors(v=>v.slice(0,-1))}>
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true"><path d="m14 6-6 6 6 6" /></svg>
          </button>
          <button type="button" className="chip-btn rule-scope-icon" aria-label="Página siguiente" title="Página siguiente" disabled={loading||page.next_cursor===null} onClick={()=>{if(page.next_cursor!==null)setCursors(v=>[...v,page.next_cursor!]);}}>
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true"><path d="m10 6 6 6-6 6" /></svg>
          </button>
        </>}
        <button type="button" className="chip-btn rule-scope-icon rule-scope-close" aria-label="Cerrar selección" title="Cerrar selección" onClick={()=>{setOpen(false);input.current?.focus();}}>
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true"><path d="m6 6 12 12M18 6 6 18" /></svg>
        </button>
      </div>
    </div></ComboboxPopup>}
  </div>;
}
