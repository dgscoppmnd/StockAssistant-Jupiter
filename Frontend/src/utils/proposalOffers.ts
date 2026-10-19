import type {ProductOption} from '../types';

export type OfferProposal={id:number;run_id:number;product_id:number;warehouse_id:number;product_name:string;warehouse_name:string;action:string;status:string};
export type OfferLine={key:string;runId:number;productId:number;warehouseId:number;productName:string;warehouseName:string;action:string;proposalId?:number;status?:string};
export type OfferDraft={product_id:number;supplier_id:string;unit_price:string;valid_until:string;reference:string;productOption?:ProductOption};
export const offerKey=(runId:number,productId:number,warehouseId:number)=>`${runId}:${productId}:${warehouseId}`;
export const emptyOffer=(productId:number):OfferDraft=>({product_id:productId,supplier_id:'',unit_price:'',valid_until:'',reference:''});

export function recommendedOfferLines(proposals:OfferProposal[],selectedRunId:number | null,events:{phase:string;detail:Record<string,unknown>}[]):OfferLine[]{
  const rows=new Map<string,OfferLine>();
  if(selectedRunId!==null){
    const decision=[...events].reverse().find(e=>e.phase==='decision'&&Array.isArray(e.detail.choices));
    for(const value of (decision?.detail.choices as unknown[] | undefined)??[]){
      if(!value||typeof value!=='object')continue;
      const choice=value as {product_id:number;warehouse_id:number;action:string};
      if(!Number.isSafeInteger(choice.product_id)||choice.product_id<=0||!Number.isSafeInteger(choice.warehouse_id)||choice.warehouse_id<=0||typeof choice.action!=='string')continue;
      const key=offerKey(selectedRunId,choice.product_id,choice.warehouse_id);
      rows.set(key,{key,runId:selectedRunId,productId:choice.product_id,warehouseId:choice.warehouse_id,
        productName:`Producto #${choice.product_id}`,warehouseName:`Almacén #${choice.warehouse_id}`,action:choice.action});
    }
  }
  for(const proposal of proposals){
    if(selectedRunId!==null&&proposal.run_id!==selectedRunId)continue;
    if(selectedRunId===null&&(proposal.action!=='replenish'||!['pending_approval','approved'].includes(proposal.status)))continue;
    const key=offerKey(proposal.run_id,proposal.product_id,proposal.warehouse_id);
    rows.set(key,{key,runId:proposal.run_id,productId:proposal.product_id,warehouseId:proposal.warehouse_id,
      productName:proposal.product_name,warehouseName:proposal.warehouse_name,action:proposal.action,
      proposalId:proposal.id,status:proposal.status});
  }
  return [...rows.values()];
}

export function offerError(productId:number,draft:OfferDraft | undefined,now=Date.now()):string{
  if(!draft)return 'Completa la oferta de este producto antes de ejecutar la compra.';
  if(draft.product_id!==productId)return `Selecciona el producto recomendado #${productId}; esta propuesta no permite cambiar de producto.`;
  if(!/^\d+$/.test(draft.supplier_id)||!Number.isSafeInteger(Number(draft.supplier_id))||Number(draft.supplier_id)<=0)return 'Selecciona un proveedor para este producto.';
  if(!/^\d+(\.\d{1,4})?$/.test(draft.unit_price)||Number(draft.unit_price)<=0||Number(draft.unit_price)>100000000)return 'Indica un precio válido, mayor que cero y con hasta cuatro decimales.';
  const until=new Date(draft.valid_until).getTime();
  if(!Number.isFinite(until)||until<=now)return 'Indica una fecha de validez futura para esta oferta.';
  if(draft.reference.trim().length<3||draft.reference.length>500)return 'La referencia de la oferta debe tener entre 3 y 500 caracteres.';
  return '';
}

export function quoteForProposal(proposal:OfferProposal,drafts:Record<string,OfferDraft>,now=Date.now()){
  const draft=drafts[offerKey(proposal.run_id,proposal.product_id,proposal.warehouse_id)];
  const error=offerError(proposal.product_id,draft,now);
  if(error)throw new Error(error);
  return {supplier_id:Number(draft.supplier_id),unit_price:draft.unit_price,currency_code:'EUR',
    valid_until:new Date(draft.valid_until).toISOString(),reference:draft.reference.trim()};
}
