import {useCallback,useEffect,useRef,useState,type FormEvent} from 'react';
import {fetchMasterRecords,fetchInventoryDashboard,stockOrdersRequest} from '../api';
import type {MasterRecord,InventoryWarehouse,InventoryStockItem} from '../types';
import InventoryCrudCard from './components/InventoryCrudCard';
import ProductCombobox from './components/ProductCombobox';
import SupplierCombobox from './components/SupplierCombobox';

type Line={product_id:number;quantity:number;unit_code:string;unit_price:number;product_name?:string;currency_code?:string};
type Order={id:number;supplier_id:number;supplier_name:string;warehouse_id:number;warehouse_name:string;
  purchase_order_number:string;notes:string;status:string;lines_count:number;total_eur:number;created_at:string;updated_at:string;editable:boolean;lines?:Line[]};
type Draft={supplier_id:number;warehouse_id:number;purchase_order_number:string;notes:string;lines:Line[];expected_updated_at?:string};
const emptyLine=():Line=>({product_id:0,quantity:1,unit_code:'unit',unit_price:0});
function Icon({kind}:{kind:'add'|'edit'|'delete'|'save'|'close'|'refresh'|'view'}){
  const paths={add:'M12 5v14M5 12h14',edit:'m15 5 4 4M4 20l4-1L20 7l-4-4L4 15v5Z',delete:'M3 6h18M9 6V3h6v3M6 6l1 15h10l1-15M10 10v7M14 10v7',save:'M5 3h12l4 4v14H3V3h2Zm2 0v6h10V3M7 21v-8h10v8',close:'m6 6 12 12M6 18 18 6',refresh:'M20 7v5h-5M4 17v-5h5M5 8a8 8 0 0 1 14-2l1 6M4 12l1 6a8 8 0 0 0 14-2',view:'M2 12s4-7 10-7 10 7 10 7-4 7-10 7S2 12 2 12Zm10-3a3 3 0 1 0 0 6 3 3 0 0 0 0-6'};
  return <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" aria-hidden="true"><path d={paths[kind]}/></svg>;
}
export default function StockOrdersPage(){
  const selectionRequest=useRef(0);
  const [orders,setOrders]=useState<Order[]>([]),[suppliers,setSuppliers]=useState<MasterRecord[]>([]),[warehouses,setWarehouses]=useState<InventoryWarehouse[]>([]);
  const [stock,setStock]=useState<InventoryStockItem[]>([]);
  const [busy,setBusy]=useState(false),[loading,setLoading]=useState(true),[error,setError]=useState(''),[message,setMessage]=useState(''),[query,setQuery]=useState('');
  const [draft,setDraft]=useState<Draft|null>(null),[selected,setSelected]=useState<Order|null>(null),[readOnly,setReadOnly]=useState(false);
  const load=useCallback(async()=>{
    setLoading(true);
    try{
      const [rows,providers,dashboard]=await Promise.all([stockOrdersRequest<Order[]>(),fetchMasterRecords('suppliers'),fetchInventoryDashboard()]);
      setOrders(rows);setSuppliers(providers);setWarehouses(dashboard.warehouses);setStock(dashboard.stock_snapshot);
    }catch(e){setError(e instanceof Error?e.message:String(e));}finally{setLoading(false);}
  },[]);
  useEffect(()=>{void load();},[load]);
  const start=()=>{setSelected(null);setReadOnly(false);setError('');setMessage('');setDraft({supplier_id:0,warehouse_id:warehouses.find(w=>w.is_active)?.id??0,purchase_order_number:'',notes:'',lines:[emptyLine()]});};
  const open=async(order:Order)=>{
    const requestId=++selectionRequest.current;
    setBusy(true);setError('');setMessage('');
    try{
      const detail=await stockOrdersRequest<Order>(`/${order.id}`);
      if(requestId!==selectionRequest.current)return;
      setSelected(order);setReadOnly(!order.editable);
      setDraft({supplier_id:detail.supplier_id,warehouse_id:detail.warehouse_id,purchase_order_number:detail.purchase_order_number,
        notes:detail.notes??'',expected_updated_at:detail.updated_at,lines:(detail.lines??[]).map(l=>({product_id:l.product_id,quantity:Number(l.quantity),unit_code:l.unit_code,unit_price:Number(l.unit_price),product_name:l.product_name,currency_code:l.currency_code}))});
    }catch(e){if(requestId===selectionRequest.current)setError(e instanceof Error?e.message:String(e));}finally{if(requestId===selectionRequest.current)setBusy(false);}
  };
  const save=async(event:FormEvent)=>{
    event.preventDefault();if(!draft||busy)return;
    setBusy(true);setError('');setMessage('');
    try{
      if(selected&&readOnly){
        await stockOrdersRequest(`/${selected.id}`,'PATCH',{purchase_order_number:draft.purchase_order_number,
          notes:draft.notes,expected_updated_at:draft.expected_updated_at});
      }else{
        await stockOrdersRequest(selected?`/${selected.id}`:'',selected?'PUT':'POST',{
          ...draft,lines:draft.lines.map(({product_name:_name,currency_code:_currency,...line})=>line)});
      }
      setDraft(null);setSelected(null);await load();setMessage('Pedido de stock guardado.');
    }catch(e){setError(e instanceof Error?e.message:String(e));}finally{setBusy(false);}
  };
  const remove=async(order:Order)=>{
    if(!window.confirm(`¿Borrar el pedido de stock ${order.purchase_order_number}?`))return;
    setBusy(true);setError('');setMessage('');
    try{await stockOrdersRequest(`/${order.id}?expected_updated_at=${encodeURIComponent(order.updated_at)}`,'DELETE');if(selected?.id===order.id)setDraft(null);await load();setMessage('Pedido eliminado.');}
    catch(e){setError(e instanceof Error?e.message:String(e));}finally{setBusy(false);}
  };
  const changeLine=(index:number,patch:Partial<Line>)=>setDraft(current=>current?{...current,lines:current.lines.map((line,i)=>i===index?{...line,...patch}:line)}:current);
  const filtered=orders.filter(o=>`${o.purchase_order_number} ${o.supplier_name} ${o.warehouse_name} ${o.status}`.toLocaleLowerCase().includes(query.toLocaleLowerCase()));
  const iconButton=(kind:Parameters<typeof Icon>[0]['kind'],label:string,onClick:()=>void,disabled=false)=><button type="button" className="chip-btn" title={label} aria-label={label} disabled={disabled} onClick={onClick}><Icon kind={kind}/></button>;
  return <div className="grid stock-orders-page">
    <section className="card"><div className="actions-row"><h2>Pedidos de stock</h2>
      {iconButton('add','Agregar pedido de stock',start,busy||loading)}
      {iconButton('refresh','Actualizar listado',()=>void load(),busy||loading)}</div>
      <p>Consulta los pedidos de reposición y gestiona sus borradores. Guardar un borrador no registra una entrada ni modifica el stock.</p>
      <label>Buscar pedido, proveedor, bodega o estado<input value={query} onChange={e=>setQuery(e.target.value)}/></label>
      {loading&&<p role="status">Cargando pedidos…</p>}
      {error&&<p className="error-line" role="alert">{error}</p>}{message&&<p role="status">{message}</p>}
    </section>
    <InventoryCrudCard sectionLabel="Reposición de inventario" title="Listado de pedidos de stock" description="Selecciona un pedido para cargar sus datos en el formulario de edición." table={{keyField:'id',data:filtered,onSelectRow:order=>void open(order),selectedKey:draft?selected?.id:undefined,noDataIndication:'No hay pedidos de stock para esta búsqueda.',totalLabel:'pedidos',columns:[
      {dataField:'purchase_order_number',text:'Pedido',sort:true},{dataField:'supplier_name',text:'Proveedor',sort:true},{dataField:'warehouse_name',text:'Bodega',sort:true},
      {dataField:'status',text:'Estado',sort:true},{dataField:'lines_count',text:'Productos'},
      {dataField:'total_eur',text:'Total (EUR)',formatter:(value:number)=>Number(value).toLocaleString('es-ES',{style:'currency',currency:'EUR'})},
      {dataField:'created_at',text:'Fecha',formatter:(value:string)=>new Date(value).toLocaleString('es-ES')},
      {dataField:'actions',text:'Acciones',formatter:(_:unknown,order:Order)=><div className="actions-row">
        {iconButton('edit',`Editar ${order.purchase_order_number}`,()=>void open(order),busy)}
        {iconButton('delete',order.editable?`Borrar ${order.purchase_order_number}`:'Solo se pueden borrar borradores sin entradas de stock',()=>void remove(order),busy||!order.editable)}
      </div>},
    ]}}/>
    {draft&&<InventoryCrudCard sectionLabel="Reposición de inventario" title={selected?'Editar pedido de stock':'Agregar pedido de stock'} onSubmit={save}
      headerAction={iconButton('close','Cerrar formulario',()=>setDraft(null),busy)} footer={<button type="submit" className="primary-btn" title="Guardar pedido" aria-label="Guardar pedido" disabled={busy}><Icon kind="save"/></button>}>
      {readOnly&&<p>Puedes editar el número y las notas. El proveedor, la bodega y las líneas están vinculados al inventario y se conservan.</p>}
      <div className="stock-order-meta">
        <SupplierCombobox suppliers={suppliers} selectedId={draft.supplier_id||null} creating={false} loading={loading} allowCreate={false} disabled={busy||readOnly} onSelect={s=>setDraft({...draft,supplier_id:s.id})} onCreate={()=>{}}/>
        <label>Bodega<select required disabled={busy||readOnly} value={draft.warehouse_id} onChange={e=>setDraft({...draft,warehouse_id:Number(e.target.value)})}><option value="">Seleccionar bodega</option>{warehouses.filter(w=>w.is_active||w.id===draft.warehouse_id).map(w=><option key={w.id} value={w.id}>{w.code} · {w.name}</option>)}</select></label>
        <label>Número de pedido<input required={readOnly} maxLength={80} disabled={busy} placeholder="Automático al guardar" value={draft.purchase_order_number} onChange={e=>setDraft({...draft,purchase_order_number:e.target.value})}/></label>
      </div>
      <div className="stock-order-lines">{draft.lines.map((line,index)=><div key={index} className="stock-order-line">
        <ProductCombobox disabled={busy||readOnly} selectedId={line.product_id} onSelect={p=>changeLine(index,{product_id:p.pk_product,unit_code:stock.find(s=>s.product_id===p.pk_product)?.base_unit_code??'unit'})}/>
        <label>Cantidad<input type="number" required min="0.0001" step="0.0001" disabled={busy||readOnly} value={line.quantity} onChange={e=>changeLine(index,{quantity:Number(e.target.value)})}/></label>
        <label>Unidad base<input required readOnly value={line.unit_code}/></label>
        <label>Precio por unidad base ({readOnly?line.currency_code??'EUR':'EUR'})<input type="number" required min="0" step="0.0001" disabled={busy||readOnly} value={line.unit_price} onChange={e=>changeLine(index,{unit_price:Number(e.target.value)})}/></label>
        {!readOnly&&iconButton('delete',`Eliminar línea ${index+1}`,()=>setDraft({...draft,lines:draft.lines.filter((_,i)=>i!==index)}),busy||draft.lines.length===1)}
      </div>)}</div>
      {!readOnly&&iconButton('add','Agregar línea de producto',()=>setDraft({...draft,lines:[...draft.lines,emptyLine()]}),busy||draft.lines.length>=100)}
      <div className="field-group">
        <label className="input-label" htmlFor="stock-order-editor-notes">Notas</label>
        <textarea id="stock-order-editor-notes" placeholder="Observaciones opcionales" rows={2} maxLength={500} disabled={busy} value={draft.notes} onChange={e=>setDraft({...draft,notes:e.target.value})}/>
      </div>
    </InventoryCrudCard>}

  </div>;
}
