import {useEffect,useState} from 'react';
import {fetchMasterRecords} from '../../api';
import type {MasterRecord} from '../../types';
import {emptyOffer,offerError,type OfferDraft,type OfferLine} from '../../utils/proposalOffers';
import ProductCombobox from './ProductCombobox';

type Props={rows:OfferLine[];drafts:Record<string,OfferDraft>;busy:boolean;onChange:(key:string,draft:OfferDraft)=>void};
export default function PurchaseOfferLines({rows,drafts,busy,onChange}:Props){
  const [suppliers,setSuppliers]=useState<MasterRecord[]>([]),[error,setError]=useState(''),[loading,setLoading]=useState(false),[retry,setRetry]=useState(0);
  const hasRows=rows.length>0;
  useEffect(()=>{
    if(!hasRows)return;
    let cancelled=false;setLoading(true);setError('');
    void fetchMasterRecords('suppliers').then(data=>{if(!cancelled)setSuppliers(data);})
      .catch(e=>{if(!cancelled)setError(e instanceof Error?e.message:'No se pudieron cargar los proveedores');})
      .finally(()=>{if(!cancelled)setLoading(false);});
    return()=>{cancelled=true;};
  },[hasRows,retry]);
  return <details open className="purchase-offer-lines"><summary>Oferta de compra confirmada para la siguiente ejecución</summary>
    {!hasRows&&<p>Abre una traza con productos recomendados o revisa las propuestas de reposición pendientes.</p>}
    {error&&<p role="alert">{error} <button type="button" className="chip-btn" onClick={()=>setRetry(value=>value+1)}>Reintentar proveedores</button></p>}
    {rows.map(row=>{
      const draft=drafts[row.key]??emptyOffer(row.productId);
      const editable=row.action==='replenish'&&row.proposalId!==undefined&&['pending_approval','approved'].includes(row.status??'');
      const message=editable?offerError(row.productId,draft):row.action!=='replenish'
        ?'Esta recomendación no solicita una compra; no necesita oferta de proveedor.'
        :row.proposalId===undefined?'Esta recomendación no tiene una propuesta de compra persistida para ejecutar.'
        :'La propuesta ya no está pendiente de aprobación o ejecución.';
      const update=(patch:Partial<OfferDraft>)=>onChange(row.key,{...draft,...patch});
      return <fieldset key={row.key} className="purchase-offer-line" id={`offer-${row.key.split(':').join('-')}`}>
        <legend>{row.productName} · {row.warehouseName} · ejecución #{row.runId}</legend>
        <div className="agent-fields">
          <ProductCombobox label="Producto recomendado" selectedId={draft.product_id} selectedProduct={draft.productOption}
            disabled={busy} onSelect={product=>{
              if(product.pk_product===draft.product_id)update({productOption:product});
              else onChange(row.key,{...emptyOffer(product.pk_product),productOption:product});
            }} />
          <label>Proveedor<select disabled={busy} aria-busy={loading} value={draft.supplier_id} onChange={event=>update({supplier_id:event.target.value})}>
            <option value="">{loading?'Cargando proveedores…':'Seleccionar proveedor'}</option>
            {suppliers.map(supplier=><option key={supplier.id} value={supplier.id}>{String(supplier.supplier_code??'')} · {String(supplier.name??`Proveedor #${supplier.id}`)}</option>)}
          </select></label>
          <label>Precio por unidad base (EUR)<input type="number" disabled={busy} min="0.0001" max="100000000" step="0.0001" value={draft.unit_price} onChange={event=>update({unit_price:event.target.value})} /></label>
          <label>Oferta válida hasta<input type="datetime-local" disabled={busy} value={draft.valid_until} onChange={event=>update({valid_until:event.target.value})} /></label>
          <label>Referencia de oferta<input disabled={busy} minLength={3} maxLength={500} value={draft.reference} onChange={event=>update({reference:event.target.value})} /></label>
        </div>
        {message&&<p className="muted" role="status">{message}</p>}
      </fieldset>;
    })}
  </details>;
}
