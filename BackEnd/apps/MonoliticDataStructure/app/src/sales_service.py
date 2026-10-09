"""Operational sales sharing InventoryService's stock locks and movement ledger."""
from contextlib import contextmanager
from datetime import date
from decimal import Decimal, ROUND_HALF_UP
import hashlib
import json
from typing import Any
from uuid import uuid4

from psycopg2.extras import Json

from inventory_service import InventoryError, InventoryService


def money(value: Decimal) -> Decimal:
    if abs(value) >= Decimal("10000000000000000"):
        raise InventoryError("El importe excede la capacidad del documento.", 400)
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def line_amounts(quantity, price, discount=0, tax=0):
    net = money(Decimal(str(quantity)) * Decimal(str(price)) * (1 - Decimal(str(discount)) / 100))
    vat = money(net * Decimal(str(tax)) / 100)
    return net, vat, money(net + vat)


def snapshot(value):
    return Json(value, dumps=lambda data: json.dumps(data, default=str))


def capture_legacy_invoice(service, invoice_id):
    """Freeze the legacy dispatch invoice in the same transaction as its stock move."""
    service._execute(
        """
        UPDATE public.sales_invoice_lines il SET
          description_snapshot=p.name_product, unit_snapshot=u.code,
          unit_price=ol.unit_price, exchange_rate=ol.exchange_rate,
          exchange_rate_date=ol.exchange_rate_date,
          line_subtotal=ROUND(il.invoiced_qty*ol.unit_price,2),
          line_total=ROUND(il.invoiced_qty*ol.unit_price,2)
        FROM public.sales_order_lines ol, public.productos p, public.inventory_units u
        WHERE il.invoice_id=%s AND il.sales_order_line_id=ol.id
          AND il.product_id=p.pk_product AND il.base_unit_id=u.id
          AND il.description_snapshot IS NULL
    """,
        (invoice_id,),
    )
    service._execute(
        """
        UPDATE public.sales_invoices i SET
          customer_snapshot=jsonb_build_object('name',o.customer_name,'address',o.address_snapshot),
          currency_code=COALESCE((SELECT currency_code FROM public.sales_order_lines
                                 WHERE sales_order_id=o.id ORDER BY id LIMIT 1),o.currency_code),
          subtotal=(SELECT COALESCE(SUM(line_subtotal),0) FROM public.sales_invoice_lines WHERE invoice_id=i.id),
          tax_total=(SELECT COALESCE(SUM(line_tax),0) FROM public.sales_invoice_lines WHERE invoice_id=i.id),
          total=(SELECT COALESCE(SUM(line_total),0) FROM public.sales_invoice_lines WHERE invoice_id=i.id)
        FROM public.sales_orders o WHERE i.id=%s AND i.sales_order_id=o.id
          AND i.customer_snapshot='{}'::jsonb
    """,
        (invoice_id,),
    )


class SalesService(InventoryService):
    def __init__(self, connection: Any, user: dict):
        super().__init__(connection)
        self.user = user

    def permit(self, permission):
        if permission not in self.user.get("sales_permissions", []):
            raise InventoryError("No tienes permiso para esta operación de ventas.", 403)

    @contextmanager
    def operation(self, kind, doc_id, action, payload, permission):
        self.permit(permission)
        key = payload["operation_key"]
        digest = hashlib.sha256(
            json.dumps(
                {"type": kind, "id": doc_id, "action": action, "payload": payload},
                sort_keys=True,
                default=str,
            ).encode()
        ).hexdigest()
        with self.transaction():
            # Serialize retries even when the document does not exist yet.
            self._execute("SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))", (key,))
            event = self._fetchone(
                "SELECT * FROM public.sales_document_events WHERE operation_key = %s", (key,)
            )
            if event:
                if event["payload_hash"] != digest or event["user_id"] != self.user["id"]:
                    raise InventoryError(
                        "La clave de operación ya se utilizó con otros datos.", 409
                    )
                yield {"replay": True, "result": event["result"]}
                return
            state = {"replay": False, "result": None}
            yield state
            result = state["result"]
            self._execute(
                """
                INSERT INTO public.sales_document_events
                (document_type, document_id, action, operation_key, payload_hash,
                 user_id, user_name, result)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
            """,
                (
                    kind,
                    result["id"],
                    action,
                    key,
                    digest,
                    self.user["id"],
                    self.user["email"],
                    Json(result, dumps=lambda v: json.dumps(v, default=str)),
                ),
            )

    def order(self, order_id, lock=False):
        order = self._fetchone(
            "SELECT * FROM public.sales_orders WHERE id = %s" + (" FOR UPDATE" if lock else ""),
            (order_id,),
        )
        if not order:
            raise InventoryError("Pedido de venta no encontrado.", 404)
        return order

    def invoice(self, invoice_id, lock=False):
        invoice = self._fetchone(
            "SELECT * FROM public.sales_invoices WHERE id = %s" + (" FOR UPDATE" if lock else ""),
            (invoice_id,),
        )
        if not invoice:
            raise InventoryError("Factura no encontrada.", 404)
        return invoice

    def order_lines(self, order_id):
        return self._fetchall(
            """
            SELECT l.*, u.code AS unit_code
            FROM public.sales_order_lines l JOIN public.inventory_units u ON u.id=l.base_unit_id
            WHERE l.sales_order_id=%s ORDER BY l.product_id, l.id
        """,
            (order_id,),
        )

    def detail(self, kind, doc_id):
        self.permit("read")
        if kind == "order":
            data = self.order(doc_id)
            data["lines"] = self.order_lines(doc_id)
            for line in data["lines"]:
                line["line_subtotal"], line["line_tax"], line["line_total"] = line_amounts(
                    line["requested_qty"],
                    line["unit_price"],
                    line["discount_percent"],
                    line["tax_percent"],
                )
            data["invoices"] = self._fetchall(
                "SELECT id, invoice_number, status, total FROM public.sales_invoices WHERE sales_order_id=%s ORDER BY id",
                (doc_id,),
            )
            data["dispatches"] = self._fetchall(
                "SELECT id, dispatch_number, status, created_at FROM public.sales_dispatches WHERE sales_order_id=%s ORDER BY id",
                (doc_id,),
            )
            data["returns"] = self._fetchall(
                "SELECT id, return_number, reason, created_at FROM public.sales_returns WHERE sales_order_id=%s ORDER BY id",
                (doc_id,),
            )
        else:
            data = self.invoice(doc_id)
            data["lines"] = self._fetchall(
                "SELECT * FROM public.sales_invoice_lines WHERE invoice_id=%s ORDER BY id",
                (doc_id,),
            )
            data["order_number"] = self.order(data["sales_order_id"])["sales_order_number"]
        data["events"] = self._fetchall(
            """
            SELECT id, action, user_name, created_at FROM public.sales_document_events
            WHERE (document_type=%s AND document_id=%s)
               OR (%s='invoice' AND (result->>'invoice_id'=%s OR result->>'correction_id'=%s))
            ORDER BY id DESC
        """,
            (kind, doc_id, kind, str(doc_id), str(doc_id)),
        )
        return data

    def list_documents(self, kind, query):
        self.permit("read")
        table, number, day = (
            ("sales_orders", "sales_order_number", "order_date")
            if kind == "order"
            else ("sales_invoices", "invoice_number", "invoice_date")
        )
        join = "" if kind == "order" else "JOIN public.sales_orders o ON o.id=d.sales_order_id"
        customer = (
            "d.customer_name"
            if kind == "order"
            else "COALESCE(d.customer_snapshot->>'name', o.customer_name)"
        )
        client = "d.client_id" if kind == "order" else "o.client_id"
        clauses, params = ["TRUE"], []
        if query.get("q"):
            clauses.append(f"(d.{number} ILIKE %s OR {customer} ILIKE %s OR d.reference ILIKE %s)")
            params.extend(["%" + query["q"] + "%"] * 3)
        for field, expression in (("status", "d.status"), ("client_id", client)):
            if query.get(field) is not None and query[field] != "":
                clauses.append(expression + "=%s")
                params.append(query[field])
        for field, comparator in (("date_from", ">="), ("date_to", "<=")):
            if query.get(field):
                clauses.append(f"d.{day}{comparator}%s")
                params.append(query[field])
        where = " AND ".join(clauses)
        total = self._fetchone(
            f"SELECT COUNT(*) AS total FROM public.{table} d {join} WHERE {where}", tuple(params)
        )["total"]
        rows = self._fetchall(
            f"""
            SELECT d.*, d.{number} AS number, {customer} AS customer_name
            FROM public.{table} d {join} WHERE {where}
            ORDER BY d.{day} DESC, d.id DESC LIMIT %s OFFSET %s
        """,
            tuple(params) + (query["size"], (query["page"] - 1) * query["size"]),
        )
        return {"items": rows, "total": total, "page": query["page"], "size": query["size"]}

    def editable_order(self, order):
        if order["status"] != "borrador":
            raise InventoryError("Solo se pueden editar o eliminar pedidos borradores.", 409)
        row = self._fetchone(
            """
            SELECT EXISTS(SELECT 1 FROM public.inventory_reservations WHERE sales_order_id=%s)
                OR EXISTS(SELECT 1 FROM public.sales_dispatches WHERE sales_order_id=%s)
                OR EXISTS(SELECT 1 FROM public.sales_invoices WHERE sales_order_id=%s) AS used
        """,
            (order["id"],) * 3,
        )
        if row["used"]:
            raise InventoryError("El pedido tiene operaciones asociadas.", 409)

    def prepare_order(self, payload):
        client = self._fetchone(
            "SELECT pk_client, name FROM public.clients WHERE pk_client=%s", (payload["client_id"],)
        )
        if not client:
            raise InventoryError("Cliente no encontrado.", 404)
        warehouse = self._fetchone(
            "SELECT id FROM public.inventory_warehouses WHERE id=%s AND is_active",
            (payload["warehouse_id"],),
        )
        if not warehouse:
            raise InventoryError("Selecciona una bodega activa.", 400)
        currency = self._fetchone(
            "SELECT * FROM public.inventory_currencies WHERE iso_code=%s",
            (payload["currency_code"],),
        )
        if not currency:
            raise InventoryError("Moneda no configurada.", 400)
        address = {}
        if payload.get("address_association_id"):
            address = self._fetchone(
                """
                SELECT g.*, a.address_type FROM public.clients_addresses a
                JOIN public.globlal_addresses g ON g.id=a.global_address_id
                WHERE a.id=%s AND a.client_id=%s
            """,
                (payload["address_association_id"], client["pk_client"]),
            )
            if not address:
                raise InventoryError("La dirección no pertenece al cliente.", 400)
        prepared = []
        for line in sorted(payload["lines"], key=lambda l: l["product_id"]):
            product = self._get_product(line["product_id"])
            if self._fetchone(
                "SELECT disabled FROM public.productos WHERE pk_product=%s", (line["product_id"],)
            )["disabled"]:
                raise InventoryError("No se puede vender un producto desactivado.", 400)
            base, config = self._convert_to_base_qty(
                line["product_id"], Decimal(str(line["quantity"])), line["unit_code"]
            )
            if base != base.quantize(Decimal("0.0001")):
                raise InventoryError(
                    "La conversión excede la precisión de inventario (4 decimales)."
                )
            factor = base / Decimal(str(line["quantity"]))
            base_price = Decimal(str(line["unit_price"])) / factor
            if base_price != base_price.quantize(Decimal("0.0001")):
                raise InventoryError(
                    "El precio por unidad base debe admitir cuatro decimales; ajusta precio o unidad."
                )
            prepared.append(
                {
                    **line,
                    "requested_qty": base,
                    "unit_price": base_price,
                    "base_unit_id": config["base_unit_id"],
                    "description_snapshot": product["name_product"],
                }
            )
        return client, currency, address, prepared

    def totals(self, lines, quantity_field):
        values = [
            line_amounts(
                l[quantity_field], l["unit_price"], l["discount_percent"], l["tax_percent"]
            )
            for l in lines
        ]
        return tuple(sum((v[i] for v in values), Decimal("0")) for i in range(3))

    def save_order(self, payload, order_id=None):
        with self.operation(
            "order",
            order_id,
            "edit" if order_id else "create",
            payload,
            "edit" if order_id else "create",
        ) as op:
            if op["replay"]:
                return op["result"]
            if order_id:
                self.editable_order(self.order(order_id, True))
            client, currency, address, lines = self.prepare_order(payload)
            subtotal, vat, total = self.totals(lines, "requested_qty")
            values = (
                client["pk_client"],
                client["name"],
                payload["warehouse_id"],
                snapshot(address),
                payload["order_date"],
                payload.get("reference"),
                payload.get("notes"),
                currency["iso_code"],
                subtotal,
                vat,
                total,
                self.user["email"],
            )
            if order_id:
                self._execute(
                    """
                    UPDATE public.sales_orders SET client_id=%s, customer_name=%s, warehouse_id=%s,
                    address_snapshot=%s, order_date=%s, reference=%s, notes=%s, currency_code=%s,
                    subtotal=%s, tax_total=%s, total=%s, user_name=%s, updated_at=CURRENT_TIMESTAMP WHERE id=%s
                """,
                    values + (order_id,),
                )
                self._execute(
                    "DELETE FROM public.sales_order_lines WHERE sales_order_id=%s", (order_id,)
                )
            else:
                order_id = self._fetchone(
                    """
                    INSERT INTO public.sales_orders (client_id, customer_name, warehouse_id,
                    address_snapshot, order_date, reference, notes, currency_code, subtotal,
                    tax_total, total, user_name, sales_order_number)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id
                """,
                    values + ("SO-" + uuid4().hex.upper(),),
                )["id"]
            for line in lines:
                self._execute(
                    """
                    INSERT INTO public.sales_order_lines (sales_order_id, product_id, requested_qty,
                    pending_qty, base_unit_id, currency_id, currency_code, unit_price, exchange_rate,
                    exchange_rate_date, description_snapshot, discount_percent, tax_percent)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,1,%s,%s,%s,%s)
                """,
                    (
                        order_id,
                        line["product_id"],
                        line["requested_qty"],
                        line["requested_qty"],
                        line["base_unit_id"],
                        currency["id"],
                        currency["iso_code"],
                        line["unit_price"],
                        payload["order_date"],
                        line["description_snapshot"],
                        line["discount_percent"],
                        line["tax_percent"],
                    ),
                )
            op["result"] = {"id": order_id, "type": "order"}
        return op["result"]

    def delete_order(self, order_id, payload):
        with self.operation("order", order_id, "delete", payload, "delete") as op:
            if not op["replay"]:
                self.editable_order(self.order(order_id, True))
                self._execute("DELETE FROM public.sales_orders WHERE id=%s", (order_id,))
                op["result"] = {"id": order_id, "deleted": True}
        return op["result"]

    def selected_lines(self, order_id, selections):
        lines = {l["id"]: l for l in self.order_lines(order_id)}
        chosen = []
        for selected in selections:
            line = lines.get(selected["line_id"])
            if not line:
                raise InventoryError("La línea no pertenece al pedido.", 400)
            chosen.append((line, Decimal(str(selected["quantity"]))))
        return sorted(chosen, key=lambda item: item[0]["product_id"])

    def update_order_status(self, order_id):
        lines = self.order_lines(order_id)
        if all(l["pending_qty"] == 0 for l in lines):
            state = "cancelado" if all(l["dispatched_qty"] == 0 for l in lines) else "completado"
        elif any(l["dispatched_qty"] > 0 for l in lines):
            state = "parcial"
        else:
            state = "confirmado"
        self._execute(
            "UPDATE public.sales_orders SET status=%s, updated_at=CURRENT_TIMESTAMP WHERE id=%s",
            (state, order_id),
        )

    def movement(self, order, line, qty, action, payload, document_id=None, document_type=None):
        return self._insert_movement(
            movement_type=action,
            product_id=line["product_id"],
            warehouse_id=order["warehouse_id"],
            warehouse_destination_id=None,
            quantity=qty,
            quantity_signed=-qty
            if action == "dispatch"
            else qty
            if action == "sales_return"
            else Decimal("0"),
            base_unit_id=line["base_unit_id"],
            document_type=document_type or "sales_order",
            document_id=document_id or order["id"],
            document_line_id=line["id"],
            operation_key=payload["operation_key"],
            reason=payload.get("reason", action),
            user_name=self.user["email"],
        )

    def reserve_order(self, order_id, payload):
        with self.operation("order", order_id, "reserve", payload, "reserve") as op:
            if op["replay"]:
                return op["result"]
            order = self.order(order_id, True)
            if order["status"] not in ("borrador", "confirmado", "parcial"):
                raise InventoryError("El pedido no admite nuevas reservas.", 409)
            for line, qty in self.selected_lines(order_id, payload["lines"]):
                if qty > line["pending_qty"] - line["reserved_qty"]:
                    raise InventoryError(
                        "La reserva excede la cantidad pendiente sin reservar.", 409
                    )
                config = self._get_product_inventory_config(line["product_id"])
                self._apply_reserved_delta(
                    line["product_id"], order["warehouse_id"], qty, config["allow_negative_stock"]
                )
                self._execute(
                    "UPDATE public.sales_order_lines SET reserved_qty=reserved_qty+%s WHERE id=%s",
                    (qty, line["id"]),
                )
                self._execute(
                    """
                    INSERT INTO public.inventory_reservations
                    (sales_order_id,sales_order_line_id,product_id,warehouse_id,reserved_qty,status,operation_key)
                    VALUES (%s,%s,%s,%s,%s,'confirmado',%s)
                """,
                    (
                        order_id,
                        line["id"],
                        line["product_id"],
                        order["warehouse_id"],
                        qty,
                        payload["operation_key"],
                    ),
                )
                self.movement(order, line, qty, "reservation", payload)
            self.update_order_status(order_id)
            op["result"] = {"id": order_id, "type": "order"}
        return op["result"]

    def release_reservations(self, line_id, qty):
        remaining = qty
        for row in self._fetchall(
            """
            SELECT * FROM public.inventory_reservations WHERE sales_order_line_id=%s
            AND reserved_qty>released_qty ORDER BY id FOR UPDATE
        """,
            (line_id,),
        ):
            released = min(remaining, row["reserved_qty"] - row["released_qty"])
            self._execute(
                """
                UPDATE public.inventory_reservations SET released_qty=released_qty+%s,
                status=CASE WHEN released_qty+%s=reserved_qty THEN 'completado' ELSE 'parcial' END
                WHERE id=%s
            """,
                (released, released, row["id"]),
            )
            remaining -= released
            if remaining == 0:
                break
        if remaining:
            raise InventoryError("La trazabilidad de reservas es inconsistente.", 409)

    def dispatch_order(self, order_id, payload):
        self.permit("invoice")
        with self.operation("order", order_id, "dispatch", payload, "dispatch") as op:
            if op["replay"]:
                return op["result"]
            order = self.order(order_id, True)
            if order["status"] not in ("confirmado", "parcial"):
                raise InventoryError("Confirma y reserva el pedido antes de despachar.", 409)
            chosen = self.selected_lines(order_id, payload["lines"])
            dispatch_id = self._fetchone(
                """
                INSERT INTO public.sales_dispatches (sales_order_id,warehouse_id,dispatch_number,
                operation_key,status,user_name,notes) VALUES (%s,%s,%s,%s,'confirmado',%s,%s) RETURNING id
            """,
                (
                    order_id,
                    order["warehouse_id"],
                    "SD-" + uuid4().hex.upper(),
                    payload["operation_key"],
                    self.user["email"],
                    payload.get("reason"),
                ),
            )["id"]
            for line, qty in chosen:
                if qty > line["reserved_qty"] or qty > line["pending_qty"]:
                    raise InventoryError("El despacho excede la reserva o el pendiente.", 409)
                config = self._get_product_inventory_config(line["product_id"])
                self._apply_reserved_delta(
                    line["product_id"], order["warehouse_id"], -qty, config["allow_negative_stock"]
                )
                self._apply_physical_delta(
                    line["product_id"], order["warehouse_id"], -qty, config["allow_negative_stock"]
                )
                self.release_reservations(line["id"], qty)
                self._execute(
                    """
                    UPDATE public.sales_order_lines SET reserved_qty=reserved_qty-%s,
                    dispatched_qty=dispatched_qty+%s,pending_qty=pending_qty-%s WHERE id=%s
                """,
                    (qty, qty, qty, line["id"]),
                )
                self._execute(
                    """
                    INSERT INTO public.sales_dispatch_lines
                    (dispatch_id,sales_order_line_id,product_id,dispatched_qty,base_unit_id)
                    VALUES (%s,%s,%s,%s,%s)
                """,
                    (dispatch_id, line["id"], line["product_id"], qty, line["base_unit_id"]),
                )
                self.movement(order, line, qty, "dispatch", payload, dispatch_id, "sales_dispatch")
            invoice_id = self.insert_invoice(
                order, chosen, {"invoice_date": date.today()}, "confirmado"
            )
            self.update_order_status(order_id)
            op["result"] = {"id": order_id, "dispatch_id": dispatch_id, "invoice_id": invoice_id}
        return op["result"]

    def insert_invoice(self, order, chosen, payload, status="borrador"):
        invoice_id = self._fetchone(
            """
            INSERT INTO public.sales_invoices (sales_order_id,invoice_number,status,user_name,
            invoice_date,due_date,reference,notes,customer_snapshot,currency_code)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id
        """,
            (
                order["id"],
                "INV-" + uuid4().hex.upper(),
                status,
                self.user["email"],
                payload["invoice_date"],
                payload.get("due_date"),
                payload.get("reference"),
                payload.get("notes"),
                snapshot(
                    {
                        "client_id": order["client_id"],
                        "name": order["customer_name"],
                        "address": order["address_snapshot"],
                    }
                ),
                order["currency_code"],
            ),
        )["id"]
        self.write_invoice_lines(invoice_id, chosen, status == "confirmado")
        return invoice_id

    def write_invoice_lines(self, invoice_id, chosen, consume):
        subtotal = vat = total = Decimal("0")
        for line, qty in chosen:
            net, tax, gross = line_amounts(
                qty, line["unit_price"], line["discount_percent"], line["tax_percent"]
            )
            subtotal += net
            vat += tax
            total += gross
            self._execute(
                """
                INSERT INTO public.sales_invoice_lines (invoice_id,sales_order_line_id,product_id,
                invoiced_qty,base_unit_id,description_snapshot,unit_snapshot,unit_price,
                discount_percent,tax_percent,exchange_rate,exchange_rate_date,line_subtotal,line_tax,line_total)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            """,
                (
                    invoice_id,
                    line["id"],
                    line["product_id"],
                    qty,
                    line["base_unit_id"],
                    line.get("description_snapshot")
                    or self._get_product(line["product_id"])["name_product"],
                    line["unit_code"],
                    line["unit_price"],
                    line["discount_percent"],
                    line["tax_percent"],
                    line["exchange_rate"],
                    line["exchange_rate_date"],
                    net,
                    tax,
                    gross,
                ),
            )
            if consume:
                self._execute(
                    "UPDATE public.sales_order_lines SET invoiced_qty=invoiced_qty+%s WHERE id=%s",
                    (qty, line["id"]),
                )
        self._execute(
            "UPDATE public.sales_invoices SET subtotal=%s,tax_total=%s,total=%s WHERE id=%s",
            (subtotal, vat, total, invoice_id),
        )

    def available_invoice_lines(self, order_id, selections, exclude=None):
        chosen = self.selected_lines(order_id, selections)
        for line, qty in chosen:
            held = self._fetchone(
                """
                SELECT COALESCE(SUM(il.invoiced_qty),0) AS qty FROM public.sales_invoice_lines il
                JOIN public.sales_invoices i ON i.id=il.invoice_id
                WHERE il.sales_order_line_id=%s AND i.status='borrador'
                AND (%s::bigint IS NULL OR i.id<>%s)
            """,
                (line["id"], exclude, exclude),
            )["qty"]
            if qty > line["dispatched_qty"] - line["invoiced_qty"] - held:
                raise InventoryError(
                    "La factura excede lo despachado aún disponible para facturar.", 409
                )
        return chosen

    def save_invoice(self, payload, invoice_id=None):
        with self.operation(
            "invoice", invoice_id, "edit" if invoice_id else "create", payload, "invoice"
        ) as op:
            if op["replay"]:
                return op["result"]
            order = self.order(payload["sales_order_id"], True)
            if invoice_id:
                invoice = self.invoice(invoice_id, True)
                if invoice["status"] != "borrador" or invoice["sales_order_id"] != order["id"]:
                    raise InventoryError(
                        "Solo se edita una factura borrador del mismo pedido.", 409
                    )
            chosen = self.available_invoice_lines(order["id"], payload["lines"], invoice_id)
            if invoice_id:
                self._execute(
                    "DELETE FROM public.sales_invoice_lines WHERE invoice_id=%s", (invoice_id,)
                )
                self._execute(
                    """
                    UPDATE public.sales_invoices SET invoice_date=%s,due_date=%s,reference=%s,
                    notes=%s,updated_at=CURRENT_TIMESTAMP WHERE id=%s
                """,
                    (
                        payload["invoice_date"],
                        payload.get("due_date"),
                        payload.get("reference"),
                        payload.get("notes"),
                        invoice_id,
                    ),
                )
                self.write_invoice_lines(invoice_id, chosen, False)
            else:
                invoice_id = self.insert_invoice(order, chosen, payload)
            op["result"] = {"id": invoice_id, "type": "invoice"}
        return op["result"]

    def invoice_action(self, invoice_id, payload, action):
        with self.operation(
            "invoice", invoice_id, action, payload, "void" if action == "void" else "invoice"
        ) as op:
            if op["replay"]:
                return op["result"]
            original = self.invoice(invoice_id)
            self.order(original["sales_order_id"], True)
            invoice = self.invoice(invoice_id, True)
            if action in ("issue", "delete") and invoice["status"] != "borrador":
                raise InventoryError("La factura ya no es un borrador.", 409)
            if action == "void" and invoice["status"] != "confirmado":
                raise InventoryError("Solo se anulan facturas emitidas.", 409)
            if action == "delete":
                self._execute("DELETE FROM public.sales_invoices WHERE id=%s", (invoice_id,))
            elif action == "issue":
                lines = self._fetchall(
                    "SELECT * FROM public.sales_invoice_lines WHERE invoice_id=%s", (invoice_id,)
                )
                if not lines:
                    raise InventoryError("La factura no tiene líneas.")
                self.available_invoice_lines(
                    invoice["sales_order_id"],
                    [
                        {"line_id": l["sales_order_line_id"], "quantity": l["invoiced_qty"]}
                        for l in lines
                    ],
                    invoice_id,
                )
                for line in lines:
                    self._execute(
                        "UPDATE public.sales_order_lines SET invoiced_qty=invoiced_qty+%s WHERE id=%s",
                        (line["invoiced_qty"], line["sales_order_line_id"]),
                    )
                self._execute(
                    "UPDATE public.sales_invoices SET status='confirmado',updated_at=CURRENT_TIMESTAMP WHERE id=%s",
                    (invoice_id,),
                )
            else:
                # Keep the immutable invoice and its quantities for audit. Voiding is
                # a financial status change, never a return or a stock operation.
                self._execute(
                    "UPDATE public.sales_invoices SET status='cancelado',void_reason=%s,updated_at=CURRENT_TIMESTAMP WHERE id=%s",
                    (payload["reason"], invoice_id),
                )
                if invoice["correction_of_id"]:
                    raise InventoryError(
                        "Una rectificativa no admite otra anulación por este flujo.", 409
                    )
                correction = self._fetchone(
                    """
                    INSERT INTO public.sales_invoices
                    (sales_order_id,invoice_number,status,user_name,invoice_date,notes,
                     customer_snapshot,currency_code,subtotal,tax_total,total,correction_of_id)
                    SELECT sales_order_id,%s,'confirmado',%s,CURRENT_DATE,%s,
                           customer_snapshot,currency_code,-subtotal,-tax_total,-total,id
                    FROM public.sales_invoices WHERE id=%s RETURNING id
                """,
                    (
                        "CN-" + uuid4().hex.upper(),
                        self.user["email"],
                        payload["reason"],
                        invoice_id,
                    ),
                )["id"]
                self._execute(
                    """
                    INSERT INTO public.sales_invoice_lines
                    (invoice_id,sales_order_line_id,product_id,invoiced_qty,base_unit_id,
                     description_snapshot,unit_snapshot,unit_price,discount_percent,tax_percent,
                     exchange_rate,exchange_rate_date,line_subtotal,line_tax,line_total)
                    SELECT %s,sales_order_line_id,product_id,-invoiced_qty,base_unit_id,
                           description_snapshot,unit_snapshot,unit_price,discount_percent,tax_percent,
                           exchange_rate,exchange_rate_date,-line_subtotal,-line_tax,-line_total
                    FROM public.sales_invoice_lines WHERE invoice_id=%s
                """,
                    (correction, invoice_id),
                )
            op["result"] = {"id": invoice_id, "deleted": action == "delete"}
            if action == "void":
                op["result"]["correction_id"] = correction
        return op["result"]

    def cancel_order(self, order_id, payload):
        with self.operation("order", order_id, "cancel", payload, "edit") as op:
            if op["replay"]:
                return op["result"]
            order = self.order(order_id, True)
            if order["status"] not in ("confirmado", "parcial"):
                raise InventoryError("El pedido no tiene pendientes cancelables.", 409)
            for line in self.order_lines(order_id):
                qty = line["reserved_qty"]
                if qty:
                    config = self._get_product_inventory_config(line["product_id"])
                    self._apply_reserved_delta(
                        line["product_id"],
                        order["warehouse_id"],
                        -qty,
                        config["allow_negative_stock"],
                    )
                    self.release_reservations(line["id"], qty)
                    self.movement(order, line, qty, "reservation_release", payload)
                self._execute(
                    """
                    UPDATE public.sales_order_lines SET reserved_qty=0,canceled_qty=canceled_qty+pending_qty,
                    pending_qty=0 WHERE id=%s
                """,
                    (line["id"],),
                )
            self.update_order_status(order_id)
            op["result"] = {"id": order_id, "type": "order"}
        return op["result"]

    def return_order(self, order_id, payload):
        with self.operation("order", order_id, "return", payload, "return") as op:
            if op["replay"]:
                return op["result"]
            order = self.order(order_id, True)
            return_id = self._fetchone(
                """
                INSERT INTO public.sales_returns (sales_order_id,warehouse_id,return_number,
                credit_note_number,operation_key,status,user_name,reason)
                VALUES (%s,%s,%s,%s,%s,'confirmado',%s,%s) RETURNING id
            """,
                (
                    order_id,
                    order["warehouse_id"],
                    "RET-" + uuid4().hex.upper(),
                    "CN-" + uuid4().hex.upper(),
                    payload["operation_key"],
                    self.user["email"],
                    payload["reason"],
                ),
            )["id"]
            for line, qty in self.selected_lines(order_id, payload["lines"]):
                if qty > line["dispatched_qty"] - line["returned_qty"]:
                    raise InventoryError(
                        "La devolución supera la mercancía despachada sin devolver.", 409
                    )
                config = self._get_product_inventory_config(line["product_id"])
                self._apply_physical_delta(
                    line["product_id"], order["warehouse_id"], qty, config["allow_negative_stock"]
                )
                self._execute(
                    "UPDATE public.sales_order_lines SET returned_qty=returned_qty+%s WHERE id=%s",
                    (qty, line["id"]),
                )
                self._execute(
                    """
                    INSERT INTO public.sales_return_lines (sales_return_id,sales_order_line_id,product_id,returned_qty,base_unit_id)
                    VALUES (%s,%s,%s,%s,%s)
                """,
                    (return_id, line["id"], line["product_id"], qty, line["base_unit_id"]),
                )
                self.movement(order, line, qty, "sales_return", payload, return_id, "sales_return")
            op["result"] = {"id": order_id, "return_id": return_id}
        return op["result"]
