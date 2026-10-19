import {offerError,type OfferDraft,type OfferLine} from './proposalOffers';
import type {InventoryLinePayload} from '../types';

export type StockOrderDraftGroup={key:string;warehouse_id:number;warehouse_name:string;supplier_id:number;
  supplier_name:string;supplier_code:string | null;valid_until:string;purchase_order_number:string;
  notes:string;operation_key:string;confirmed:boolean;lines:(InventoryLinePayload&{proposal_id?:number | null})[]};
export type StockOrderDraft={id:number;groups:StockOrderDraftGroup[]};

export function stockDraftPayload(rows:OfferLine[],offers:Record<string,OfferDraft>){
  if(!rows.length)throw new Error('Selecciona una recomendación con productos para convertir.');
  return {lines:rows.map(row=>{
    const offer=offers[row.key];
    const error=offerError(row.productId,offer,Date.now(),false);
    if(error)throw new Error(`${row.productName}: ${error}`);
    return {run_id:row.runId,source_product_id:row.productId,product_id:offer.product_id,warehouse_id:row.warehouseId,
      quote:{supplier_id:Number(offer.supplier_id),unit_price:offer.unit_price,currency_code:'EUR',
        valid_until:new Date(offer.valid_until).toISOString(),reference:offer.reference.trim()}};
  })};
}

export function stockDraftLines(draft?:StockOrderDraftGroup){
  return draft?.lines.map((line,index)=>({id:index+1,product_id:line.product_id,quantity:Number(line.quantity),
    unit_code:line.unit_code,unit_price:Number(line.unit_price),currency_code:line.currency_code??'EUR',exchange_rate:Number(line.exchange_rate??1)}));
}
