"""Physical receipt of an existing automation purchase, using inventory invariants.

The legacy confirm_receipt creates its own purchase order, so it cannot be used
to receive an already issued order. This workflow reuses that order and its line.
"""
from decimal import Decimal


def receive_purchase(service, proposal_id, request, actor):
    from automation_service import AtomicInventory
    try:
        service._one('SELECT * FROM public.automation_control WHERE id=1 FOR UPDATE')
        if service.stopped():
            raise ValueError('Operaciones detenidas')
        p = service._one('SELECT * FROM public.agent_action_proposals WHERE id=%s FOR UPDATE', (proposal_id,))
        if not p or p['status'] != 'executed' or p['action'] != 'replenish':
            raise ValueError('No hay un pedido emitido para esta propuesta')
        if not request.physical_confirmed:
            raise ValueError('Debes confirmar la recepción física')
        order_id = p['action_result']['purchase_order_id']
        service._one('SELECT * FROM public.purchase_orders WHERE id=%s FOR UPDATE', (order_id,))
        existing = service._one('SELECT * FROM public.goods_receipts WHERE operation_key=%s', (request.operation_key,))
        if existing:
            lines = service._all('SELECT received_qty FROM public.goods_receipt_lines WHERE receipt_id=%s', (existing['id'],))
            if existing['purchase_order_id'] != order_id or len(lines) != 1 or lines[0]['received_qty'] != request.quantity:
                raise ValueError('Clave de operación utilizada con otros datos')
            service.connection.rollback()
            return {'receipt_id': existing['id'], 'status': 'already_confirmed'}
        line = service._one('SELECT * FROM public.purchase_order_lines WHERE purchase_order_id=%s FOR UPDATE', (order_id,))
        if not line or request.quantity > line['pending_qty']:
            raise ValueError('Cantidad superior a las unidades pendientes')
        inventory = AtomicInventory(service.connection)
        inventory._lock_stock(p['product_id'], p['warehouse_id'])
        receipt = service._one('''INSERT INTO public.goods_receipts(purchase_order_id,supplier_id,warehouse_id,
            receipt_number,operation_key,status,user_name,notes)
            SELECT id,supplier_id,warehouse_id,%s,%s,'confirmado',%s,%s FROM public.purchase_orders WHERE id=%s RETURNING id''',
            ('AGR-' + request.operation_key, request.operation_key, actor, request.reason, order_id))
        received = service._one('''INSERT INTO public.goods_receipt_lines(receipt_id,purchase_order_line_id,product_id,
            received_qty,base_unit_id,currency_id,currency_code,unit_price,exchange_rate,exchange_rate_date)
            SELECT %s,id,product_id,%s,base_unit_id,currency_id,currency_code,unit_price,exchange_rate,exchange_rate_date
            FROM public.purchase_order_lines WHERE id=%s RETURNING id''', (receipt['id'], request.quantity, line['id']))
        inventory._apply_physical_delta(p['product_id'],p['warehouse_id'],request.quantity,False)
        inventory._insert_movement(movement_type='receipt',product_id=p['product_id'],warehouse_id=p['warehouse_id'],
            warehouse_destination_id=None,quantity=request.quantity,quantity_signed=request.quantity,base_unit_id=line['base_unit_id'],
            document_type='goods_receipt',document_id=receipt['id'],document_line_id=received['id'],operation_key=request.operation_key,
            reason=request.reason,user_name=actor)
        remaining = line['pending_qty'] - request.quantity
        service._write('''UPDATE public.purchase_order_lines SET received_qty=received_qty+%s,pending_qty=pending_qty-%s,
            updated_at=now() WHERE id=%s''', (request.quantity, request.quantity, line['id']))
        service._write('UPDATE public.purchase_orders SET status=%s,updated_at=now() WHERE id=%s',
                       ('recibida' if remaining == Decimal(0) else 'parcial', order_id))
        service.event(p['run_id'],p['rule_id'],'physical_receipt',{'proposal_id':p['id'],'receipt_id':receipt['id'],
            'actor':actor,'quantity':request.quantity,'remaining':remaining,'reason':request.reason})
        service.connection.commit()
        return {'receipt_id':receipt['id'],'pending_quantity':remaining,'status':'confirmed'}
    except Exception:
        service.connection.rollback()
        raise
