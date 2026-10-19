"""Save recommendations as auditable manual inventory drafts before navigation."""
from datetime import datetime,timezone
from decimal import Decimal
import hashlib
import json


def save_stock_draft(svc, request, actor):
    from automation_service import document
    try:
        fingerprint=hashlib.sha256(json.dumps(request.model_dump(mode='json'),sort_keys=True).encode()).hexdigest()
        svc._write('SELECT pg_advisory_xact_lock(hashtextextended(%s,0))',('stock-draft:'+fingerprint,))
        existing=svc._one("SELECT id FROM public.automation_events WHERE phase='stock_order_draft' AND detail->>'fingerprint'=%s",(fingerprint,))
        if existing:
            svc.connection.commit()
            return {'id':existing['id']}
        groups,seen,sources={},set(),[]
        first_run=None
        for line in request.lines:
            key=(line.run_id,line.source_product_id,line.warehouse_id)
            entity=(line.product_id,line.warehouse_id)
            if entity in seen or line.product_id!=line.source_product_id:
                raise ValueError('Producto recomendado repetido o modificado; vuelve a preparar la recomendación')
            seen.add(entity)
            run=svc._one('SELECT * FROM public.automation_runs WHERE id=%s',(line.run_id,))
            if not run or run['status']!='completed':
                raise ValueError('Selecciona una recomendación de una ejecución completada')
            first_run=first_run or run
            decision=svc._one("SELECT detail FROM public.automation_events WHERE run_id=%s AND phase='decision' AND detail ? 'choices' ORDER BY id DESC LIMIT 1",(line.run_id,))
            choice=next((c for c in (decision or {}).get('detail',{}).get('choices',[])
                         if c.get('product_id')==line.product_id and c.get('warehouse_id')==line.warehouse_id),None)
            if not choice:
                raise ValueError('El producto no figura en la decisión registrada de la ejecución')
            analysis=svc._one("SELECT detail FROM public.automation_events WHERE run_id=%s AND phase='analysis' ORDER BY id DESC LIMIT 1",(line.run_id,))
            scenario=next((s for s in (analysis or {}).get('detail',{}).get('scenarios',[])
                           if s.get('product_id')==line.product_id and s.get('warehouse_id')==line.warehouse_id),None)
            alternative=next((a for a in (scenario or {}).get('alternatives',[]) if a.get('action')=='replenish'),None)
            if not alternative or Decimal(str(alternative.get('quantity',0)))<=0:
                raise ValueError('La recomendación no dispone de cantidad de reposición calculada para este producto')
            if line.quote.valid_until<=datetime.now(timezone.utc):
                raise ValueError('La oferta del proveedor ha caducado')
            supplier=svc._one('SELECT id,name,supplier_code FROM public.inventory_suppliers WHERE id=%s',(line.quote.supplier_id,))
            warehouse=svc._one('SELECT id,name FROM public.inventory_warehouses WHERE id=%s AND is_active',(line.warehouse_id,))
            if not supplier or not warehouse:
                raise ValueError('Proveedor o bodega no disponible')
            proposal=svc._one('''SELECT id,status FROM public.agent_action_proposals
                WHERE run_id=%s AND product_id=%s AND warehouse_id=%s AND action='replenish' ORDER BY id DESC LIMIT 1''',key)
            if proposal and proposal['status'] not in ('pending_approval','approved'):
                raise ValueError('Esta propuesta ya fue ejecutada, rechazada o invalidada')
            group_key=f'{line.warehouse_id}-{supplier["id"]}'
            group=groups.setdefault(group_key,{'key':group_key,'warehouse_id':line.warehouse_id,
                'warehouse_name':warehouse['name'],'supplier_id':supplier['id'],'supplier_name':supplier['name'],
                'supplier_code':supplier['supplier_code'],'valid_until':line.quote.valid_until.astimezone(timezone.utc).isoformat(),'lines':[]})
            group['valid_until']=min(group['valid_until'],line.quote.valid_until.astimezone(timezone.utc).isoformat())
            group['lines'].append({'product_id':line.product_id,'quantity':str(alternative['quantity']),
                'unit_code':scenario['unit'],'unit_price':str(line.quote.unit_price),'currency_code':'EUR','exchange_rate':1,
                'proposal_id':proposal['id'] if proposal else None,'reference':line.quote.reference,'run_id':line.run_id})
            sources.append({'run_id':line.run_id,'choice':choice,'scenario':scenario,'quote':line.quote.model_dump(mode='json')})
        detail={'fingerprint':fingerprint,'actor':actor,'recommendations':sources,'groups':list(groups.values())}
        event=svc._one('''INSERT INTO public.automation_events(run_id,rule_id,phase,detail)
            VALUES(%s,%s,'stock_order_draft',%s) RETURNING id''',(first_run['id'],first_run['rule_id'],document(detail)))
        svc.connection.commit()
        return {'id':event['id']}
    except Exception:
        svc.connection.rollback()
        raise


def load_stock_draft(svc,draft_id):
    event=svc._one("SELECT * FROM public.automation_events WHERE id=%s AND phase='stock_order_draft'",(draft_id,))
    if not event:
        raise ValueError('Borrador de recomendación no encontrado')
    groups=[]
    for saved in event['detail']['groups']:
        group=dict(saved)
        group['operation_key']=f'recommendation-stock-{draft_id}-{group["key"]}'
        group['purchase_order_number']=f'REC-{draft_id}-{group["key"]}'
        refs='; '.join(dict.fromkeys(line['reference'] for line in group['lines']))
        group['notes']=(f'Este pedido viene de una Revisar propuestas y resultados. Recomendación guardada #{draft_id}. '+refs)[:500]
        group['confirmed']=bool(svc._one('SELECT id FROM public.goods_receipts WHERE operation_key=%s',(group['operation_key'],)))
        groups.append(group)
    return {'id':draft_id,'groups':groups}


def confirm_stock_draft(svc,draft_id,group_key,payload,actor,can_approve):
    from automation_service import AtomicInventory,document
    try:
        svc._write('SELECT pg_advisory_xact_lock(hashtextextended(%s,0))',(f'stock-draft-confirm:{draft_id}:{group_key}',))
        svc._one('SELECT * FROM public.automation_control WHERE id=1 FOR UPDATE')
        draft=load_stock_draft(svc,draft_id)
        group=next((g for g in draft['groups'] if g['key']==group_key),None)
        if not group: raise ValueError('Grupo de bodega y proveedor no encontrado')
        data=payload.model_dump()
        if data['warehouse_id']!=group['warehouse_id'] or data['supplier_name']!=group['supplier_name']:
            raise ValueError('Conserva la bodega y el proveedor de la recomendación guardada')
        if sorted(l['product_id'] for l in data['lines'])!=sorted(l['product_id'] for l in group['lines']):
            raise ValueError('Conserva todas las líneas de productos de la recomendación guardada')
        if not group['confirmed']:
            if svc.stopped(): raise ValueError('Las operaciones están detenidas')
            if datetime.fromisoformat(group['valid_until'])<=datetime.now(timezone.utc): raise ValueError('La oferta ha caducado; actualízala en agentes/control')
            spent=svc._one('''SELECT COALESCE(SUM((action_result->>'cost')::numeric),0) AS spent
                FROM public.agent_action_proposals WHERE status='executed' AND action='replenish'
                AND updated_at>=(date_trunc('day',now() AT TIME ZONE 'UTC') AT TIME ZONE 'UTC')''')['spent']
            total=Decimal(0)
            policies=[]
            for line in group['lines']:
                actual=next(item for item in data['lines'] if item['product_id']==line['product_id'])
                if actual['currency_code']!='EUR' or actual['exchange_rate']!=1 or actual['unit_price']<=0:
                    raise ValueError('Se requiere una oferta en EUR con precio positivo y cambio 1')
                if actual['unit_code']!=line['unit_code'] or actual['quantity']>Decimal(line['quantity']):
                    raise ValueError('La unidad y la cantidad deben corresponder a la recomendación guardada')
                total+=actual['quantity']*actual['unit_price']
                if line['proposal_id']:
                    proposal=svc._one('SELECT * FROM public.agent_action_proposals WHERE id=%s FOR UPDATE',(line['proposal_id'],))
                    if proposal['status']=='pending_approval' and not can_approve:
                        raise PermissionError('Confirmar una propuesta pendiente requiere permiso approve')
                    if proposal['status'] not in ('pending_approval','approved'):
                        raise ValueError('La propuesta ya no está disponible para confirmar')
                    # Receiving an earlier warehouse in this same draft updates the global historical
                    # cost. Allow only that cost change; inventory, demand and policy stay validated.
                    received_same_product=any(g['confirmed'] and any(item['product_id']==line['product_id'] for item in g['lines']) for g in draft['groups'])
                    config,_=svc.revalidate(proposal,allow_historical_cost_change=received_same_product)
                    policies.append(config)
                    if actual['quantity']*actual['unit_price']>config.per_action_budget or Decimal(spent)+total>config.daily_budget:
                        raise ValueError('Presupuesto por operación o diario excedido')
            if any(Decimal(spent)+total>config.daily_budget for config in policies):
                raise ValueError('Presupuesto diario excedido')
        notes=data.get('notes') or group['notes']
        provenance='Este pedido viene de una Revisar propuestas y resultados.'
        if provenance not in notes: notes=provenance+' '+notes
        data.update(operation_key=group['operation_key'],user_name=actor,notes=notes[:500])
        class DraftInventory(AtomicInventory):
            def _get_or_create_supplier(self,name,supplier_code):
                supplier=self._fetchone('SELECT * FROM public.inventory_suppliers WHERE id=%s',(group['supplier_id'],))
                if not supplier: raise ValueError('El proveedor guardado ya no existe')
                return supplier
        result=DraftInventory(svc.connection).confirm_receipt(data)
        if not group['confirmed']:
            for line in group['lines']:
                if line['proposal_id']:
                    proposal=svc._one('SELECT * FROM public.agent_action_proposals WHERE id=%s',(line['proposal_id'],))
                    if proposal['status']=='pending_approval':
                        svc.event(proposal['run_id'],proposal['rule_id'],'approval',{'proposal_id':proposal['id'],
                                  'actor':actor,'reason':'Confirmación humana del pedido de stock guardado'})
                    actual=next(item for item in data['lines'] if item['product_id']==line['product_id'])
                    action_result={**result,'physical_receipt':True,'source':'manual_stock_draft',
                                   'cost':str(actual['quantity']*actual['unit_price'])}
                    receipt=svc._one('SELECT purchase_order_id FROM public.goods_receipts WHERE id=%s',(result['document_id'],))
                    action_result['purchase_order_id']=receipt['purchase_order_id']
                    svc._write("UPDATE public.agent_action_proposals SET status='executed',action_result=%s,approved_by=COALESCE(approved_by,%s),approved_at=COALESCE(approved_at,now()),updated_at=now() WHERE id=%s",
                        (document(action_result),actor,line['proposal_id']))
                    svc.event(proposal['run_id'],proposal['rule_id'],'execution',{'proposal_id':proposal['id'],
                              'actor':actor,'source':'manual_stock_draft','result':action_result})
            svc.event(None,None,'stock_order_draft_confirmed',{'draft_id':draft_id,'group_key':group_key,'actor':actor,'result':result})
        svc.connection.commit()
        return result
    except Exception:
        svc.connection.rollback()
        raise
