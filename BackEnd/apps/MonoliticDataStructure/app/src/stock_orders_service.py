"""Manual stock order drafts; received documents retain their inventory history."""
from datetime import date, datetime
from decimal import Decimal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field
from inventory_service import InventoryService, InventoryError


class StockOrderLine(BaseModel):
    model_config = ConfigDict(extra='forbid')
    product_id: int = Field(gt=0)
    quantity: Decimal = Field(gt=0, le=1000000000, decimal_places=4)
    unit_code: str = Field(min_length=1, max_length=20)
    unit_price: Decimal = Field(ge=0, le=100000000, decimal_places=4)


class StockOrderDraft(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)
    supplier_id: int = Field(gt=0)
    warehouse_id: int = Field(gt=0)
    purchase_order_number: str = Field(default='', max_length=80)
    notes: str = Field(default='', max_length=500)
    expected_updated_at: datetime | None = None
    lines: list[StockOrderLine] = Field(min_length=1, max_length=100)


class StockOrderMetadata(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)
    purchase_order_number: str = Field(min_length=1, max_length=80)
    notes: str = Field(default='', max_length=500)
    expected_updated_at: datetime


class StockOrdersService(InventoryService):
    def list_orders(self):
        return self._fetchall('''SELECT o.*,s.name AS supplier_name,s.supplier_code,w.name AS warehouse_name,
            COUNT(l.id) AS lines_count,COALESCE(SUM(l.requested_qty*l.unit_price*l.exchange_rate),0) AS total_eur,
            (o.status='borrador' AND NOT EXISTS(SELECT 1 FROM public.goods_receipts r WHERE r.purchase_order_id=o.id)
             AND NOT EXISTS(SELECT 1 FROM public.agent_action_proposals p WHERE p.action_result->>'purchase_order_id'=o.id::text)) AS editable
            FROM public.purchase_orders o JOIN public.inventory_suppliers s ON s.id=o.supplier_id
            JOIN public.inventory_warehouses w ON w.id=o.warehouse_id
            LEFT JOIN public.purchase_order_lines l ON l.purchase_order_id=o.id
            GROUP BY o.id,s.id,w.id ORDER BY o.created_at DESC,o.id DESC''')

    def detail(self,order_id):
        order=self._fetchone('SELECT * FROM public.purchase_orders WHERE id=%s',(order_id,))
        if not order: raise InventoryError('Pedido de stock no encontrado.',404)
        order['lines']=self._fetchall('''SELECT l.*,l.requested_qty AS quantity,u.code AS unit_code,p.name_product AS product_name
            FROM public.purchase_order_lines l JOIN public.inventory_units u ON u.id=l.base_unit_id
            JOIN public.productos p ON p.pk_product=l.product_id WHERE purchase_order_id=%s ORDER BY l.id''',(order_id,))
        return order

    def lock_editable(self,order_id,expected_updated_at):
        order=self._fetchone('SELECT * FROM public.purchase_orders WHERE id=%s FOR UPDATE',(order_id,))
        if not order: raise InventoryError('Pedido de stock no encontrado.',404)
        linked=self._fetchone('''SELECT 1 FROM public.goods_receipts WHERE purchase_order_id=%s
            UNION ALL SELECT 1 FROM public.agent_action_proposals WHERE action_result->>'purchase_order_id'=%s LIMIT 1''',(order_id,str(order_id)))
        if order['status']!='borrador' or linked:
            raise InventoryError('Solo puedes editar o borrar borradores sin entradas de stock ni ejecuciones vinculadas.',409)
        if expected_updated_at is None or expected_updated_at!=order['updated_at']:
            raise InventoryError('El pedido cambió. Recarga el listado antes de continuar.',409)
        return order

    def save(self,payload,actor,order_id=None):
        with self.transaction():
            if order_id is not None: self.lock_editable(order_id,payload.expected_updated_at)
            if not self._fetchone('SELECT id FROM public.inventory_suppliers WHERE id=%s',(payload.supplier_id,)):
                raise InventoryError('Selecciona un proveedor existente.')
            if not self._fetchone('SELECT id FROM public.inventory_warehouses WHERE id=%s AND is_active',(payload.warehouse_id,)):
                raise InventoryError('Selecciona una bodega activa.')
            if len({l.product_id for l in payload.lines})!=len(payload.lines):
                raise InventoryError('Cada producto debe figurar una sola vez en el pedido.')
            number=payload.purchase_order_number or f'PO-{uuid4().hex[:16]}'
            if order_id is None:
                order_id=self._fetchone('''INSERT INTO public.purchase_orders(supplier_id,warehouse_id,purchase_order_number,user_name,notes)
                    VALUES(%s,%s,%s,%s,%s) RETURNING id''',(payload.supplier_id,payload.warehouse_id,number,actor,payload.notes))['id']
            else:
                self._execute('''UPDATE public.purchase_orders SET supplier_id=%s,warehouse_id=%s,purchase_order_number=%s,
                    notes=%s,updated_at=clock_timestamp() WHERE id=%s''',(payload.supplier_id,payload.warehouse_id,number,payload.notes,order_id))
                self._execute('DELETE FROM public.purchase_order_lines WHERE purchase_order_id=%s',(order_id,))
            currency=self._get_or_create_currency('EUR')
            for line in payload.lines:
                self._get_product(line.product_id)
                config=self._get_product_inventory_config(line.product_id)
                if line.unit_code!=config['base_unit_code']:
                    raise InventoryError('Usa la unidad base del producto para indicar cantidad y precio.')
                self._execute('''INSERT INTO public.purchase_order_lines(purchase_order_id,product_id,requested_qty,base_unit_id,
                    currency_id,currency_code,unit_price,exchange_rate,exchange_rate_date)
                    VALUES(%s,%s,%s,%s,%s,'EUR',%s,1,%s)''',
                    (order_id,line.product_id,line.quantity,config['base_unit_id'],currency['id'],line.unit_price,date.today()))
            return self.detail(order_id)

    def delete(self,order_id,expected_updated_at):
        with self.transaction():
            self.lock_editable(order_id,expected_updated_at)
            self._execute('DELETE FROM public.purchase_orders WHERE id=%s',(order_id,))
            return {'deleted':True,'id':order_id}

    def edit_metadata(self,order_id,payload):
        with self.transaction():
            order=self._fetchone('SELECT * FROM public.purchase_orders WHERE id=%s FOR UPDATE',(order_id,))
            if not order: raise InventoryError('Pedido de stock no encontrado.',404)
            if order['updated_at']!=payload.expected_updated_at:
                raise InventoryError('El pedido cambió. Recarga el listado antes de continuar.',409)
            self._execute('''UPDATE public.purchase_orders SET purchase_order_number=%s,notes=%s,
                updated_at=clock_timestamp() WHERE id=%s''',(payload.purchase_order_number,payload.notes,order_id))
            return self.detail(order_id)
