"""Read-only purchase evidence. Quantities and money are computed outside the LLM."""
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
import unicodedata

from inventory_service import InventoryService


def normalized(text):
    return ''.join(c for c in unicodedata.normalize('NFD', text.lower()) if not unicodedata.combining(c))


def dec(value):
    return Decimal(str(value or 0))


def build_purchase_plan(rows, *, period_days=30, product_query='', warehouse_query='', critical_only=False,
                        budget=None, currency=None, limit=100):
    """A reorder quantity is a minimum lot, not an amount to add to every shortage."""
    lines, excluded = [], []
    totals = {}
    budget = Decimal(str(budget)) if budget is not None else None
    currency = currency.strip().upper() if currency else None
    candidates = []
    for row in rows:
        if product_query and normalized(product_query) not in normalized(f"{row['product_name']} {row.get('product_code', '')}"):
            continue
        if warehouse_query and normalized(warehouse_query) not in normalized(row['warehouse_name']):
            continue
        available = dec(row['physical_qty']) - dec(row['reserved_qty'])
        demand = dec(row['sales_unreserved'])
        pending = dec(row['pending_qty'])
        point = dec(row['reorder_point'])
        effective = available - demand
        if effective > point:
            continue  # Excess stock must never generate a replenishment purchase.
        critical = effective <= 0
        if critical_only and not critical:
            continue
        candidates.append(row)
    candidates.sort(key=lambda r: (dec(r['physical_qty']) - dec(r['reserved_qty']) - dec(r['sales_unreserved']),
                                    r['product_id'], r['warehouse_id']))
    limit = max(1, min(limit, 100))
    for row in candidates[:limit]:
        available = dec(row['physical_qty']) - dec(row['reserved_qty'])
        demand, pending, point = dec(row['sales_unreserved']), dec(row['pending_qty']), dec(row['reorder_point'])
        effective = available - demand
        critical = effective <= 0
        shortage = max(Decimal(0), point + demand - available - pending)
        triggered = shortage > 0 or (pending == 0 and effective <= point)
        quantity = max(shortage, dec(row['reorder_quantity'])) if triggered else Decimal(0)
        line = {key: row.get(key) for key in ('product_id', 'product_name', 'product_code', 'warehouse_id', 'warehouse_name', 'base_unit_code')}
        line.update(available_qty=available, sales_unreserved=demand, pending_qty=pending,
                    reorder_point=point, recommended_qty=quantity, priority='critica' if critical else 'alta',
                    reason='Demanda sin reservar y stock disponible frente al punto de reposición; descontados pedidos en curso.')
        if not quantity:
            reason = 'Sin necesidad adicional: cobertura suficiente con los pedidos en curso y el stock disponible.'
            if triggered:
                reason = 'Falta configurar una cantidad de reposición o un stock objetivo positivo.'
            excluded.append({**line, 'reason': reason})
            continue
        price = dec(row['unit_cost']) if row.get('unit_cost') is not None else None
        code = (row.get('currency') or '').strip().upper() or None
        # Zero prices in the existing schema default to zero; they are not evidence of a free purchase.
        price = price if price is not None and price > 0 and code else None
        subtotal = (quantity * price).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP) if price is not None else None
        line.update(unit_cost=price, currency=code, subtotal=subtotal,
                    cost_source='Última recepción confirmada, precio registrado por unidad base' if price is not None else 'Coste no disponible',
                    cost_date=row.get('cost_date') if price is not None else None,
                    supplier_name=row.get('supplier_name') if price is not None else None)
        lines.append(line)
    lines.sort(key=lambda r: (r['priority'] != 'critica', r['available_qty'] - r['sales_unreserved'], r['product_id'], r['warehouse_id']))
    selected = []
    for line in lines:
        code, subtotal = line['currency'], line['subtotal']
        if budget is not None:
            if not currency or subtotal is None or code != currency:
                excluded.append({**line, 'reason': 'Pendiente de valorar en la moneda del presupuesto; no se incluye en el límite.'})
                continue
            if totals.get(code, Decimal(0)) + subtotal > budget:
                excluded.append({**line, 'reason': 'Supera el presupuesto restante; lote completo pendiente.'})
                continue
        selected.append(line)
        if subtotal is not None:
            totals[code] = totals.get(code, Decimal(0)) + subtotal
    return {
        'generated_at': datetime.now(timezone.utc).isoformat(), 'period_days': period_days,
        'lines': selected, 'excluded': excluded, 'totals_by_currency': totals,
        'unpriced_lines': sum(line['subtotal'] is None for line in selected),
        'budget': budget, 'budget_currency': currency,
        'candidate_count': len(candidates), 'limit': limit, 'truncated': len(candidates) > limit,
        'filters': {'product_query': product_query, 'warehouse_query': warehouse_query, 'critical_only': critical_only},
        'assumptions': [
            'Cantidad = máximo entre déficit hasta el punto de reposición y lote configurado. Al alcanzar el umbral sin pedidos en curso se propone el lote configurado.',
            'El disponible ya descuenta reservas; solo se añade demanda pendiente sin reservar.',
            'Se descuentan pedidos de compra pendientes confirmados; los borradores no son suministro comprometido.',
            'El período corresponde a los indicadores de actividad; el stock, la demanda y los pedidos son el estado actual.',
            'Los costes históricos son estimaciones, sin impuestos, transporte ni conversión de monedas; no son ofertas vigentes.',
            'Con presupuesto se seleccionan lotes completos por prioridad, sin exceder el límite; los no valorados quedan pendientes.',
        ],
        'status': 'draft', 'persistence': 'browser_only',
    }


def tool_purchase_plan(connection, *, period_days=30, **filters):
    # Aggregate demand and incoming supply separately to avoid multiplying quantities.
    rows = InventoryService(connection)._fetchall('''
        WITH demand AS (
            SELECT l.product_id,o.warehouse_id,SUM(GREATEST(l.pending_qty-l.reserved_qty,0)) AS qty
            FROM public.sales_order_lines l JOIN public.sales_orders o ON o.id=l.sales_order_id
            WHERE o.status IN ('borrador','confirmado','parcial') AND l.pending_qty>0
            GROUP BY l.product_id,o.warehouse_id
        ), incoming AS (
            SELECT l.product_id,o.warehouse_id,SUM(l.pending_qty) AS qty
            FROM public.purchase_order_lines l JOIN public.purchase_orders o ON o.id=l.purchase_order_id
            WHERE o.status NOT IN ('cancelado','cancelada','recibido','recibida','borrador') AND l.pending_qty>0
            GROUP BY l.product_id,o.warehouse_id
        ), entities AS (
            SELECT product_id,warehouse_id FROM public.inventory_stock_levels
            UNION SELECT product_id,warehouse_id FROM demand
        )
        SELECT e.product_id,e.warehouse_id,TRIM(p.name_product) AS product_name,
               p.cdgo_producto_externo AS product_code,w.name AS warehouse_name,u.code AS base_unit_code,
               COALESCE(s.physical_qty,0) AS physical_qty,COALESCE(s.reserved_qty,0) AS reserved_qty,
               c.reorder_point,c.reorder_quantity,COALESCE(d.qty,0) AS sales_unreserved,
               COALESCE(i.qty,0) AS pending_qty,cost.unit_cost,cost.currency,cost.cost_date,cost.supplier_name
        FROM entities e JOIN public.productos p ON p.pk_product=e.product_id
        JOIN public.inventory_warehouses w ON w.id=e.warehouse_id
        JOIN public.product_inventory_config c ON c.product_id=e.product_id
        JOIN public.inventory_units u ON u.id=c.base_unit_id
        LEFT JOIN public.inventory_stock_levels s ON s.product_id=e.product_id AND s.warehouse_id=e.warehouse_id
        LEFT JOIN demand d ON d.product_id=e.product_id AND d.warehouse_id=e.warehouse_id
        LEFT JOIN incoming i ON i.product_id=e.product_id AND i.warehouse_id=e.warehouse_id
        LEFT JOIN LATERAL (
            SELECT g.unit_price AS unit_cost,g.currency_code AS currency,r.created_at AS cost_date,
                   supplier.name AS supplier_name
            FROM public.goods_receipt_lines g JOIN public.goods_receipts r ON r.id=g.receipt_id
            JOIN public.inventory_suppliers supplier ON supplier.id=r.supplier_id
            WHERE g.product_id=e.product_id AND g.base_unit_id=c.base_unit_id
              AND r.status='confirmado' AND g.received_qty>0 AND g.unit_price>0
            ORDER BY r.created_at DESC,g.id DESC LIMIT 1
        ) cost ON TRUE
        WHERE COALESCE(s.physical_qty-s.reserved_qty,0)-COALESCE(d.qty,0)<=c.reorder_point
        ORDER BY e.product_id,e.warehouse_id
    ''')
    return build_purchase_plan(rows, period_days=period_days, **filters)
