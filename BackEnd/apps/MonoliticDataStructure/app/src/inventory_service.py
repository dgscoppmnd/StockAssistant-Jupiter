from __future__ import annotations

from contextlib import contextmanager
from datetime import date, datetime, timezone
from decimal import Decimal
import logging
from typing import Any
from uuid import uuid4

from psycopg2.extras import RealDictCursor

logger = logging.getLogger("api.inventory")


class InventoryError(Exception):
    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.status_code = status_code


class InventoryService:
    def __init__(self, connection: Any):
        self.connection = connection

    @contextmanager
    def transaction(self):
        try:
            yield
            self.connection.commit()
        except Exception:
            self.connection.rollback()
            raise

    def _fetchone(self, query: str, params: tuple[Any, ...] = ()) -> dict[str, Any] | None:
        with self.connection.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute(query, params)
            row = cursor.fetchone()
        return dict(row) if row else None

    def _fetchall(self, query: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
        with self.connection.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute(query, params)
            rows = cursor.fetchall()
        return [dict(row) for row in rows]

    def _execute(self, query: str, params: tuple[Any, ...] = ()) -> None:
        with self.connection.cursor() as cursor:
            cursor.execute(query, params)

    def _get_product(self, product_id: int) -> dict[str, Any]:
        row = self._fetchone(
            """
            SELECT pk_product, name_product, currency, fk_currency
            FROM public.productos
            WHERE pk_product = %s
            """,
            (product_id,),
        )
        if not row:
            raise InventoryError(f"Producto con ID {product_id} no encontrado", 404)
        return row

    def _get_or_create_currency(self, iso_code: str | None, fallback_label: str | None = None) -> dict[str, Any]:
        code = (iso_code or fallback_label or "EUR").strip().upper()
        row = self._fetchone("SELECT * FROM public.inventory_currencies WHERE iso_code = %s", (code,))
        if row:
            return row
        self._fetchone(
            """
            INSERT INTO public.inventory_currencies (iso_code, name)
            VALUES (%s, %s)
            ON CONFLICT (iso_code) DO UPDATE SET name = EXCLUDED.name
            RETURNING *
            """,
            (code, code),
        )
        return self._fetchone("SELECT * FROM public.inventory_currencies WHERE iso_code = %s", (code,)) or {}

    def _get_unit(self, code: str) -> dict[str, Any]:
        row = self._fetchone("SELECT * FROM public.inventory_units WHERE code = %s", (code.strip().lower(),))
        if not row:
            raise InventoryError(f"Unidad {code} no configurada", 400)
        return row

    def _get_product_inventory_config(self, product_id: int) -> dict[str, Any]:
        row = self._fetchone(
            """
            SELECT c.*, u.code AS base_unit_code
            FROM public.product_inventory_config c
            JOIN public.inventory_units u ON u.id = c.base_unit_id
            WHERE c.product_id = %s
            """,
            (product_id,),
        )
        if row:
            return row

        default_unit = self._get_unit("unit")
        created = self._fetchone(
            """
            INSERT INTO public.product_inventory_config (
                product_id, base_unit_id, reorder_point, reorder_quantity, allow_negative_stock
            )
            VALUES (%s, %s, 0, 0, FALSE)
            ON CONFLICT (product_id) DO NOTHING
            RETURNING *
            """,
            (product_id, default_unit["id"]),
        )
        if created:
            created["base_unit_code"] = default_unit["code"]
            return created
        return self._fetchone(
            """
            SELECT c.*, u.code AS base_unit_code
            FROM public.product_inventory_config c
            JOIN public.inventory_units u ON u.id = c.base_unit_id
            WHERE c.product_id = %s
            """,
            (product_id,),
        ) or {}

    def configure_product(self, product_id: int, base_unit_code: str, reorder_point: Decimal, reorder_quantity: Decimal, allow_negative_stock: bool) -> dict[str, Any]:
        self._get_product(product_id)
        unit = self._get_unit(base_unit_code)
        with self.transaction():
            row = self._fetchone(
                """
                INSERT INTO public.product_inventory_config (
                    product_id, base_unit_id, reorder_point, reorder_quantity, allow_negative_stock
                )
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (product_id) DO UPDATE SET
                    base_unit_id = EXCLUDED.base_unit_id,
                    reorder_point = EXCLUDED.reorder_point,
                    reorder_quantity = EXCLUDED.reorder_quantity,
                    allow_negative_stock = EXCLUDED.allow_negative_stock,
                    updated_at = CURRENT_TIMESTAMP
                RETURNING *
                """,
                (product_id, unit["id"], reorder_point, reorder_quantity, allow_negative_stock),
            )
        row = row or self._get_product_inventory_config(product_id)
        row["base_unit_code"] = unit["code"]
        return row

    def create_warehouse(self, code: str, name: str, description: str | None, is_active: bool) -> dict[str, Any]:
        with self.transaction():
            row = self._fetchone(
                """
                INSERT INTO public.inventory_warehouses (code, name, description, is_active)
                VALUES (%s, %s, %s, %s)
                RETURNING *
                """,
                (code.strip().upper(), name.strip(), description, is_active),
            )
        return row or {}

    def list_warehouses(self) -> list[dict[str, Any]]:
        return self._fetchall("SELECT * FROM public.inventory_warehouses ORDER BY name ASC")

    def _lock_stock(self, product_id: int, warehouse_id: int) -> dict[str, Any]:
        self._execute(
            """
            INSERT INTO public.inventory_stock_levels (product_id, warehouse_id, physical_qty, reserved_qty)
            VALUES (%s, %s, 0, 0)
            ON CONFLICT (product_id, warehouse_id) DO NOTHING
            """,
            (product_id, warehouse_id),
        )
        row = self._fetchone(
            """
            SELECT *
            FROM public.inventory_stock_levels
            WHERE product_id = %s AND warehouse_id = %s
            FOR UPDATE
            """,
            (product_id, warehouse_id),
        )
        if not row:
            raise InventoryError("No se pudo bloquear la existencia", 500)
        return row

    def _convert_to_base_qty(self, product_id: int, quantity: Decimal, unit_code: str) -> tuple[Decimal, dict[str, Any]]:
        config = self._get_product_inventory_config(product_id)
        input_unit = self._get_unit(unit_code)
        if input_unit["id"] == config["base_unit_id"]:
            return quantity, config

        conversion = self._fetchone(
            """
            SELECT factor
            FROM public.inventory_unit_conversions
            WHERE from_unit_id = %s
              AND to_unit_id = %s
              AND (product_id IS NULL OR product_id = %s)
            ORDER BY product_id NULLS LAST
            LIMIT 1
            """,
            (input_unit["id"], config["base_unit_id"], product_id),
        )
        if not conversion:
            raise InventoryError(
                f"No existe conversion de {input_unit['code']} a {config['base_unit_code']} para el producto {product_id}",
                400,
            )
        return quantity * Decimal(str(conversion["factor"])), config

    def _insert_movement(
        self,
        *,
        movement_type: str,
        product_id: int,
        warehouse_id: int | None,
        warehouse_destination_id: int | None,
        quantity: Decimal,
        quantity_signed: Decimal,
        base_unit_id: int,
        document_type: str,
        document_id: int,
        document_line_id: int | None,
        operation_key: str,
        reason: str,
        user_name: str,
    ) -> int:
        row = self._fetchone(
            """
            INSERT INTO public.inventory_movements (
                movement_type, product_id, warehouse_id, warehouse_destination_id, quantity,
                quantity_signed, base_unit_id, document_type, document_id, document_line_id,
                operation_key, reason, user_name
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id
            """,
            (
                movement_type,
                product_id,
                warehouse_id,
                warehouse_destination_id,
                quantity,
                quantity_signed,
                base_unit_id,
                document_type,
                document_id,
                document_line_id,
                operation_key,
                reason,
                user_name,
            ),
        )
        return int(row["id"]) if row else 0

    def _apply_physical_delta(self, product_id: int, warehouse_id: int, delta: Decimal, allow_negative: bool) -> None:
        stock = self._lock_stock(product_id, warehouse_id)
        next_qty = Decimal(str(stock["physical_qty"])) + delta
        reserved = Decimal(str(stock["reserved_qty"]))
        if not allow_negative and next_qty < 0:
            raise InventoryError(f"Stock insuficiente para el producto {product_id} en bodega {warehouse_id}", 409)
        if next_qty - reserved < 0 and not allow_negative:
            raise InventoryError(f"El stock disponible quedaria negativo para el producto {product_id}", 409)
        self._execute(
            """
            UPDATE public.inventory_stock_levels
            SET physical_qty = %s, updated_at = CURRENT_TIMESTAMP
            WHERE id = %s
            """,
            (next_qty, stock["id"]),
        )

    def _apply_reserved_delta(self, product_id: int, warehouse_id: int, delta: Decimal, allow_negative: bool) -> None:
        stock = self._lock_stock(product_id, warehouse_id)
        physical = Decimal(str(stock["physical_qty"]))
        next_reserved = Decimal(str(stock["reserved_qty"])) + delta
        if next_reserved < 0:
            raise InventoryError(f"La reserva del producto {product_id} no puede ser negativa", 409)
        if not allow_negative and physical - next_reserved < 0:
            raise InventoryError(f"Stock disponible insuficiente para reservar el producto {product_id}", 409)
        self._execute(
            """
            UPDATE public.inventory_stock_levels
            SET reserved_qty = %s, updated_at = CURRENT_TIMESTAMP
            WHERE id = %s
            """,
            (next_reserved, stock["id"]),
        )

    def _get_or_create_supplier(self, name: str, supplier_code: str | None) -> dict[str, Any]:
        normalized_name = name.strip()
        row = self._fetchone("SELECT * FROM public.inventory_suppliers WHERE name = %s", (normalized_name,))
        if row:
            return row
        row = self._fetchone(
            """
            INSERT INTO public.inventory_suppliers (supplier_code, name)
            VALUES (%s, %s)
            RETURNING *
            """,
            (supplier_code.strip().upper() if supplier_code else None, normalized_name),
        )
        return row or {}

    def list_stock(self) -> list[dict[str, Any]]:
        return self._fetchall(
            """
            SELECT
                s.product_id,
                p.name_product AS product_name,
                s.warehouse_id,
                w.code AS warehouse_code,
                w.name AS warehouse_name,
                s.physical_qty,
                s.reserved_qty,
                s.physical_qty - s.reserved_qty AS available_qty,
                u.code AS base_unit_code,
                c.reorder_point,
                c.reorder_quantity,
                p.currency
            FROM public.inventory_stock_levels s
            JOIN public.productos p ON p.pk_product = s.product_id
            JOIN public.inventory_warehouses w ON w.id = s.warehouse_id
            JOIN public.product_inventory_config c ON c.product_id = s.product_id
            JOIN public.inventory_units u ON u.id = c.base_unit_id
            ORDER BY p.name_product ASC, w.name ASC
            """
        )

    def list_movements(self, limit: int = 100) -> list[dict[str, Any]]:
        return self._fetchall(
            """
            SELECT
                m.id,
                m.movement_type,
                m.product_id,
                m.warehouse_id,
                m.warehouse_destination_id,
                m.quantity,
                m.quantity_signed,
                u.code AS base_unit_code,
                m.document_type,
                m.document_id,
                m.operation_key,
                m.reason,
                m.user_name,
                m.created_at
            FROM public.inventory_movements m
            JOIN public.inventory_units u ON u.id = m.base_unit_id
            ORDER BY m.id DESC
            LIMIT %s
            """,
            (limit,),
        )

    def get_dashboard(self) -> dict[str, Any]:
        summary = self._fetchone(
            """
            SELECT
                (SELECT COUNT(*) FROM public.productos) AS total_products,
                (SELECT COUNT(*) FROM public.inventory_warehouses) AS total_warehouses,
                COALESCE((SELECT SUM(physical_qty) FROM public.inventory_stock_levels), 0) AS total_stock_units,
                COALESCE((SELECT SUM(reserved_qty) FROM public.inventory_stock_levels), 0) AS total_reserved_units,
                COALESCE((SELECT SUM(physical_qty - reserved_qty) FROM public.inventory_stock_levels), 0) AS total_available_units,
                COALESCE((
                    SELECT COUNT(*)
                    FROM public.inventory_stock_levels s
                    JOIN public.product_inventory_config c ON c.product_id = s.product_id
                    WHERE (s.physical_qty - s.reserved_qty) <= c.reorder_point
                ), 0) AS low_stock_items
            """
        ) or {}
        summary["warehouses"] = self.list_warehouses()
        summary["recent_movements"] = self.list_movements(limit=12)
        summary["stock_snapshot"] = self.list_stock()
        return summary

    def confirm_receipt(self, payload: dict[str, Any]) -> dict[str, Any]:
        operation_key = payload.get("operation_key") or f"receipt-{uuid4().hex}"
        existing = self._fetchone("SELECT * FROM public.goods_receipts WHERE operation_key = %s", (operation_key,))
        if existing and existing["status"] == "confirmado":
            movement_ids = [row["id"] for row in self._fetchall("SELECT id FROM public.inventory_movements WHERE document_type = 'goods_receipt' AND document_id = %s ORDER BY id", (existing["id"],))]
            return {
                "status": "already_confirmed",
                "document_type": "goods_receipt",
                "document_id": existing["id"],
                "document_number": existing["receipt_number"],
                "operation_key": operation_key,
                "movement_ids": movement_ids,
            }

        supplier = self._get_or_create_supplier(payload["supplier_name"], payload.get("supplier_code"))
        warehouse = self._fetchone("SELECT * FROM public.inventory_warehouses WHERE id = %s", (payload["warehouse_id"],))
        if not warehouse:
            raise InventoryError("Bodega no encontrada", 404)

        movement_ids: list[int] = []
        with self.transaction():
            purchase_order = self._fetchone(
                """
                INSERT INTO public.purchase_orders (
                    supplier_id, warehouse_id, purchase_order_number, status, user_name, notes
                )
                VALUES (%s, %s, %s, 'recibida', %s, %s)
                RETURNING *
                """,
                (
                    supplier["id"],
                    warehouse["id"],
                    payload.get("purchase_order_number") or f"PO-{uuid4().hex[:8].upper()}",
                    payload["user_name"],
                    payload.get("notes"),
                ),
            )
            receipt = self._fetchone(
                """
                INSERT INTO public.goods_receipts (
                    purchase_order_id, supplier_id, warehouse_id, receipt_number, operation_key, status, user_name, notes
                )
                VALUES (%s, %s, %s, %s, %s, 'confirmado', %s, %s)
                ON CONFLICT (operation_key) DO UPDATE SET updated_at = CURRENT_TIMESTAMP
                RETURNING *
                """,
                (
                    purchase_order["id"],
                    supplier["id"],
                    warehouse["id"],
                    payload.get("receipt_number") or f"GR-{uuid4().hex[:8].upper()}",
                    operation_key,
                    payload["user_name"],
                    payload.get("notes"),
                ),
            )

            for line in payload["lines"]:
                product = self._get_product(line["product_id"])
                base_qty, config = self._convert_to_base_qty(line["product_id"], Decimal(str(line["quantity"])), line["unit_code"])
                currency = self._get_or_create_currency(line.get("currency_code"), product.get("currency"))
                po_line = self._fetchone(
                    """
                    INSERT INTO public.purchase_order_lines (
                        purchase_order_id, product_id, requested_qty, received_qty, canceled_qty, pending_qty,
                        base_unit_id, currency_id, currency_code, unit_price, exchange_rate, exchange_rate_date
                    )
                    VALUES (%s, %s, %s, %s, 0, 0, %s, %s, %s, %s, %s, %s)
                    RETURNING *
                    """,
                    (
                        purchase_order["id"],
                        product["pk_product"],
                        base_qty,
                        base_qty,
                        config["base_unit_id"],
                        currency["id"],
                        currency["iso_code"],
                        line.get("unit_price", 0),
                        line.get("exchange_rate", 1),
                        line.get("exchange_rate_date") or date.today(),
                    ),
                )
                receipt_line = self._fetchone(
                    """
                    INSERT INTO public.goods_receipt_lines (
                        receipt_id, purchase_order_line_id, product_id, received_qty, base_unit_id,
                        currency_id, currency_code, unit_price, exchange_rate, exchange_rate_date
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING *
                    """,
                    (
                        receipt["id"],
                        po_line["id"],
                        product["pk_product"],
                        base_qty,
                        config["base_unit_id"],
                        currency["id"],
                        currency["iso_code"],
                        line.get("unit_price", 0),
                        line.get("exchange_rate", 1),
                        line.get("exchange_rate_date") or date.today(),
                    ),
                )
                self._apply_physical_delta(product["pk_product"], warehouse["id"], base_qty, bool(config["allow_negative_stock"]))
                movement_ids.append(
                    self._insert_movement(
                        movement_type="receipt",
                        product_id=product["pk_product"],
                        warehouse_id=warehouse["id"],
                        warehouse_destination_id=None,
                        quantity=base_qty,
                        quantity_signed=base_qty,
                        base_unit_id=config["base_unit_id"],
                        document_type="goods_receipt",
                        document_id=receipt["id"],
                        document_line_id=receipt_line["id"],
                        operation_key=operation_key,
                        reason="recepcion",
                        user_name=payload["user_name"],
                    )
                )

        return {
            "status": "confirmed",
            "document_type": "goods_receipt",
            "document_id": receipt["id"],
            "document_number": receipt["receipt_number"],
            "operation_key": operation_key,
            "movement_ids": movement_ids,
        }

    def transfer_stock(self, payload: dict[str, Any]) -> dict[str, Any]:
        operation_key = payload.get("operation_key") or f"transfer-{uuid4().hex}"
        source = self._fetchone("SELECT * FROM public.inventory_warehouses WHERE id = %s", (payload["source_warehouse_id"],))
        destination = self._fetchone("SELECT * FROM public.inventory_warehouses WHERE id = %s", (payload["destination_warehouse_id"],))
        if not source or not destination:
            raise InventoryError("Bodega de origen o destino no encontrada", 404)
        if source["id"] == destination["id"]:
            raise InventoryError("La bodega de origen y destino deben ser distintas", 400)

        transfer = None
        movement_ids: list[int] = []
        with self.transaction():
            transfer = self._fetchone(
                """
                INSERT INTO public.inventory_transfers (
                    source_warehouse_id, destination_warehouse_id, transfer_number, operation_key, status, user_name, reason
                )
                VALUES (%s, %s, %s, %s, 'confirmado', %s, %s)
                RETURNING *
                """,
                (
                    source["id"],
                    destination["id"],
                    f"TR-{uuid4().hex[:8].upper()}",
                    operation_key,
                    payload["user_name"],
                    payload["reason"],
                ),
            )
            for line in payload["lines"]:
                self._get_product(line["product_id"])
                base_qty, config = self._convert_to_base_qty(line["product_id"], Decimal(str(line["quantity"])), line["unit_code"])
                self._apply_physical_delta(line["product_id"], source["id"], -base_qty, bool(config["allow_negative_stock"]))
                self._apply_physical_delta(line["product_id"], destination["id"], base_qty, bool(config["allow_negative_stock"]))
                transfer_line = self._fetchone(
                    """
                    INSERT INTO public.inventory_transfer_lines (
                        transfer_id, product_id, quantity, base_unit_id
                    )
                    VALUES (%s, %s, %s, %s)
                    RETURNING *
                    """,
                    (transfer["id"], line["product_id"], base_qty, config["base_unit_id"]),
                )
                movement_ids.append(
                    self._insert_movement(
                        movement_type="transfer_out",
                        product_id=line["product_id"],
                        warehouse_id=source["id"],
                        warehouse_destination_id=destination["id"],
                        quantity=base_qty,
                        quantity_signed=-base_qty,
                        base_unit_id=config["base_unit_id"],
                        document_type="inventory_transfer",
                        document_id=transfer["id"],
                        document_line_id=transfer_line["id"],
                        operation_key=operation_key,
                        reason=payload["reason"],
                        user_name=payload["user_name"],
                    )
                )
                movement_ids.append(
                    self._insert_movement(
                        movement_type="transfer_in",
                        product_id=line["product_id"],
                        warehouse_id=destination["id"],
                        warehouse_destination_id=source["id"],
                        quantity=base_qty,
                        quantity_signed=base_qty,
                        base_unit_id=config["base_unit_id"],
                        document_type="inventory_transfer",
                        document_id=transfer["id"],
                        document_line_id=transfer_line["id"],
                        operation_key=operation_key,
                        reason=payload["reason"],
                        user_name=payload["user_name"],
                    )
                )

        return {
            "status": "confirmed",
            "document_type": "inventory_transfer",
            "document_id": transfer["id"],
            "document_number": transfer["transfer_number"],
            "operation_key": operation_key,
            "movement_ids": movement_ids,
        }

    def reserve_stock(self, payload: dict[str, Any]) -> dict[str, Any]:
        operation_key = payload.get("operation_key") or f"reserve-{uuid4().hex}"
        warehouse = self._fetchone("SELECT * FROM public.inventory_warehouses WHERE id = %s", (payload["warehouse_id"],))
        if not warehouse:
            raise InventoryError("Bodega no encontrada", 404)
        order = None
        movement_ids: list[int] = []
        with self.transaction():
            order = self._fetchone(
                """
                INSERT INTO public.sales_orders (
                    customer_name, warehouse_id, sales_order_number, status, user_name, notes
                )
                VALUES (%s, %s, %s, 'confirmado', %s, %s)
                RETURNING *
                """,
                (
                    payload["customer_name"],
                    warehouse["id"],
                    payload.get("sales_order_number") or f"SO-{uuid4().hex[:8].upper()}",
                    payload["user_name"],
                    payload.get("notes"),
                ),
            )
            for line in payload["lines"]:
                product = self._get_product(line["product_id"])
                base_qty, config = self._convert_to_base_qty(line["product_id"], Decimal(str(line["quantity"])), line["unit_code"])
                currency = self._get_or_create_currency(line.get("currency_code"), product.get("currency"))
                self._apply_reserved_delta(line["product_id"], warehouse["id"], base_qty, bool(config["allow_negative_stock"]))
                order_line = self._fetchone(
                    """
                    INSERT INTO public.sales_order_lines (
                        sales_order_id, product_id, requested_qty, reserved_qty, dispatched_qty, invoiced_qty,
                        canceled_qty, returned_qty, pending_qty, base_unit_id, currency_id, currency_code,
                        unit_price, exchange_rate, exchange_rate_date
                    )
                    VALUES (%s, %s, %s, %s, 0, 0, 0, 0, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING *
                    """,
                    (
                        order["id"],
                        line["product_id"],
                        base_qty,
                        base_qty,
                        base_qty,
                        config["base_unit_id"],
                        currency["id"],
                        currency["iso_code"],
                        line.get("unit_price", 0),
                        line.get("exchange_rate", 1),
                        line.get("exchange_rate_date") or date.today(),
                    ),
                )
                reservation = self._fetchone(
                    """
                    INSERT INTO public.inventory_reservations (
                        sales_order_id, sales_order_line_id, product_id, warehouse_id, reserved_qty, released_qty, status, operation_key
                    )
                    VALUES (%s, %s, %s, %s, %s, 0, 'confirmado', %s)
                    RETURNING *
                    """,
                    (order["id"], order_line["id"], line["product_id"], warehouse["id"], base_qty, operation_key),
                )
                movement_ids.append(
                    self._insert_movement(
                        movement_type="reservation",
                        product_id=line["product_id"],
                        warehouse_id=warehouse["id"],
                        warehouse_destination_id=None,
                        quantity=base_qty,
                        quantity_signed=Decimal("0"),
                        base_unit_id=config["base_unit_id"],
                        document_type="sales_order",
                        document_id=order["id"],
                        document_line_id=reservation["id"],
                        operation_key=operation_key,
                        reason="reserva",
                        user_name=payload["user_name"],
                    )
                )

        return {
            "status": "confirmed",
            "document_type": "sales_order",
            "document_id": order["id"],
            "document_number": order["sales_order_number"],
            "operation_key": operation_key,
            "movement_ids": movement_ids,
        }

    def dispatch_sales_order(self, payload: dict[str, Any]) -> dict[str, Any]:
        operation_key = payload.get("operation_key") or f"dispatch-{uuid4().hex}"
        order = self._fetchone("SELECT * FROM public.sales_orders WHERE id = %s", (payload["sales_order_id"],))
        if not order:
            raise InventoryError("Pedido de venta no encontrado", 404)
        warehouse_id = payload["warehouse_id"]
        dispatch = None
        invoice = None
        movement_ids: list[int] = []
        with self.transaction():
            dispatch = self._fetchone(
                """
                INSERT INTO public.sales_dispatches (
                    sales_order_id, warehouse_id, dispatch_number, operation_key, status, user_name, notes
                )
                VALUES (%s, %s, %s, %s, 'confirmado', %s, %s)
                RETURNING *
                """,
                (
                    order["id"],
                    warehouse_id,
                    payload.get("dispatch_number") or f"SD-{uuid4().hex[:8].upper()}",
                    operation_key,
                    payload["user_name"],
                    payload.get("notes"),
                ),
            )
            invoice = self._fetchone(
                """
                INSERT INTO public.sales_invoices (
                    sales_order_id, invoice_number, status, user_name
                )
                VALUES (%s, %s, 'confirmado', %s)
                RETURNING *
                """,
                (
                    order["id"],
                    payload.get("invoice_number") or f"INV-{uuid4().hex[:8].upper()}",
                    payload["user_name"],
                ),
            )
            for line in payload["lines"]:
                order_line = self._fetchone(
                    """
                    SELECT *
                    FROM public.sales_order_lines
                    WHERE sales_order_id = %s AND product_id = %s
                    FOR UPDATE
                    """,
                    (order["id"], line["product_id"]),
                )
                if not order_line:
                    raise InventoryError(f"El producto {line['product_id']} no pertenece al pedido", 404)
                base_qty, config = self._convert_to_base_qty(line["product_id"], Decimal(str(line["quantity"])), line["unit_code"])
                reserved_qty = Decimal(str(order_line["reserved_qty"]))
                if reserved_qty < base_qty:
                    raise InventoryError(f"No hay reserva suficiente para el producto {line['product_id']}", 409)
                self._apply_reserved_delta(line["product_id"], warehouse_id, -base_qty, bool(config["allow_negative_stock"]))
                self._apply_physical_delta(line["product_id"], warehouse_id, -base_qty, bool(config["allow_negative_stock"]))
                next_dispatched = Decimal(str(order_line["dispatched_qty"])) + base_qty
                next_reserved = reserved_qty - base_qty
                next_pending = max(Decimal("0"), Decimal(str(order_line["requested_qty"])) - next_dispatched - Decimal(str(order_line["canceled_qty"])))
                self._execute(
                    """
                    UPDATE public.sales_order_lines
                    SET reserved_qty = %s,
                        dispatched_qty = %s,
                        invoiced_qty = %s,
                        pending_qty = %s,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = %s
                    """,
                    (next_reserved, next_dispatched, next_dispatched, next_pending, order_line["id"]),
                )
                dispatch_line = self._fetchone(
                    """
                    INSERT INTO public.sales_dispatch_lines (
                        dispatch_id, sales_order_line_id, product_id, dispatched_qty, base_unit_id
                    )
                    VALUES (%s, %s, %s, %s, %s)
                    RETURNING *
                    """,
                    (dispatch["id"], order_line["id"], line["product_id"], base_qty, config["base_unit_id"]),
                )
                self._fetchone(
                    """
                    INSERT INTO public.sales_invoice_lines (
                        invoice_id, sales_order_line_id, product_id, invoiced_qty, base_unit_id
                    )
                    VALUES (%s, %s, %s, %s, %s)
                    RETURNING id
                    """,
                    (invoice["id"], order_line["id"], line["product_id"], base_qty, config["base_unit_id"]),
                )
                movement_ids.append(
                    self._insert_movement(
                        movement_type="dispatch",
                        product_id=line["product_id"],
                        warehouse_id=warehouse_id,
                        warehouse_destination_id=None,
                        quantity=base_qty,
                        quantity_signed=-base_qty,
                        base_unit_id=config["base_unit_id"],
                        document_type="sales_dispatch",
                        document_id=dispatch["id"],
                        document_line_id=dispatch_line["id"],
                        operation_key=operation_key,
                        reason="despacho",
                        user_name=payload["user_name"],
                    )
                )
            self._execute("UPDATE public.sales_orders SET status = 'parcial', updated_at = CURRENT_TIMESTAMP WHERE id = %s", (order["id"],))

        return {
            "status": "confirmed",
            "document_type": "sales_dispatch",
            "document_id": dispatch["id"],
            "document_number": dispatch["dispatch_number"],
            "operation_key": operation_key,
            "movement_ids": movement_ids,
        }

    def cancel_sales_order(self, payload: dict[str, Any]) -> dict[str, Any]:
        operation_key = payload.get("operation_key") or f"cancel-{uuid4().hex}"
        order = self._fetchone("SELECT * FROM public.sales_orders WHERE id = %s", (payload["sales_order_id"],))
        if not order:
            raise InventoryError("Pedido de venta no encontrado", 404)
        lines = self._fetchall(
            """
            SELECT *
            FROM public.sales_order_lines
            WHERE sales_order_id = %s
            ORDER BY id
            """,
            (payload["sales_order_id"],),
        )
        movement_ids: list[int] = []
        with self.transaction():
            for line in lines:
                config = self._get_product_inventory_config(line["product_id"])
                reserved_qty = Decimal(str(line["reserved_qty"]))
                dispatched_qty = Decimal(str(line["dispatched_qty"]))
                returned_qty = Decimal(str(line["returned_qty"]))
                if reserved_qty > 0:
                    self._apply_reserved_delta(line["product_id"], payload["warehouse_id"], -reserved_qty, bool(config["allow_negative_stock"]))
                    movement_ids.append(
                        self._insert_movement(
                            movement_type="reservation_release",
                            product_id=line["product_id"],
                            warehouse_id=payload["warehouse_id"],
                            warehouse_destination_id=None,
                            quantity=reserved_qty,
                            quantity_signed=Decimal("0"),
                            base_unit_id=config["base_unit_id"],
                            document_type="sales_order_cancel",
                            document_id=order["id"],
                            document_line_id=line["id"],
                            operation_key=operation_key,
                            reason=payload["reason"],
                            user_name=payload["user_name"],
                        )
                    )
                restore_qty = dispatched_qty - returned_qty
                if restore_qty > 0:
                    self._apply_physical_delta(line["product_id"], payload["warehouse_id"], restore_qty, bool(config["allow_negative_stock"]))
                    movement_ids.append(
                        self._insert_movement(
                            movement_type="cancel_after_dispatch",
                            product_id=line["product_id"],
                            warehouse_id=payload["warehouse_id"],
                            warehouse_destination_id=None,
                            quantity=restore_qty,
                            quantity_signed=restore_qty,
                            base_unit_id=config["base_unit_id"],
                            document_type="sales_order_cancel",
                            document_id=order["id"],
                            document_line_id=line["id"],
                            operation_key=operation_key,
                            reason=payload["reason"],
                            user_name=payload["user_name"],
                        )
                    )
                requested = Decimal(str(line["requested_qty"]))
                self._execute(
                    """
                    UPDATE public.sales_order_lines
                    SET reserved_qty = 0,
                        canceled_qty = %s,
                        pending_qty = 0,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = %s
                    """,
                    (requested, line["id"]),
                )
            self._execute("UPDATE public.sales_orders SET status = 'cancelado', updated_at = CURRENT_TIMESTAMP WHERE id = %s", (order["id"],))

        return {
            "status": "confirmed",
            "document_type": "sales_order_cancel",
            "document_id": order["id"],
            "document_number": order["sales_order_number"],
            "operation_key": operation_key,
            "movement_ids": movement_ids,
        }

    def process_return(self, payload: dict[str, Any]) -> dict[str, Any]:
        operation_key = payload.get("operation_key") or f"return-{uuid4().hex}"
        order = self._fetchone("SELECT * FROM public.sales_orders WHERE id = %s", (payload["sales_order_id"],))
        if not order:
            raise InventoryError("Pedido de venta no encontrado", 404)
        movement_ids: list[int] = []
        sales_return = None
        with self.transaction():
            sales_return = self._fetchone(
                """
                INSERT INTO public.sales_returns (
                    sales_order_id, warehouse_id, return_number, credit_note_number, operation_key, status, user_name, reason
                )
                VALUES (%s, %s, %s, %s, %s, 'confirmado', %s, %s)
                RETURNING *
                """,
                (
                    order["id"],
                    payload["warehouse_id"],
                    payload.get("return_number") or f"RET-{uuid4().hex[:8].upper()}",
                    payload.get("credit_note_number") or f"CN-{uuid4().hex[:8].upper()}",
                    operation_key,
                    payload["user_name"],
                    payload["reason"],
                ),
            )
            for line in payload["lines"]:
                order_line = self._fetchone(
                    """
                    SELECT *
                    FROM public.sales_order_lines
                    WHERE sales_order_id = %s AND product_id = %s
                    FOR UPDATE
                    """,
                    (order["id"], line["product_id"]),
                )
                if not order_line:
                    raise InventoryError(f"El producto {line['product_id']} no pertenece al pedido", 404)
                base_qty, config = self._convert_to_base_qty(line["product_id"], Decimal(str(line["quantity"])), line["unit_code"])
                dispatchable = Decimal(str(order_line["dispatched_qty"])) - Decimal(str(order_line["returned_qty"]))
                if base_qty > dispatchable:
                    raise InventoryError(f"La devolucion supera lo despachado para el producto {line['product_id']}", 409)
                self._apply_physical_delta(line["product_id"], payload["warehouse_id"], base_qty, bool(config["allow_negative_stock"]))
                next_returned = Decimal(str(order_line["returned_qty"])) + base_qty
                self._execute(
                    """
                    UPDATE public.sales_order_lines
                    SET returned_qty = %s,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = %s
                    """,
                    (next_returned, order_line["id"]),
                )
                return_line = self._fetchone(
                    """
                    INSERT INTO public.sales_return_lines (
                        sales_return_id, sales_order_line_id, product_id, returned_qty, base_unit_id
                    )
                    VALUES (%s, %s, %s, %s, %s)
                    RETURNING *
                    """,
                    (sales_return["id"], order_line["id"], line["product_id"], base_qty, config["base_unit_id"]),
                )
                movement_ids.append(
                    self._insert_movement(
                        movement_type="return",
                        product_id=line["product_id"],
                        warehouse_id=payload["warehouse_id"],
                        warehouse_destination_id=None,
                        quantity=base_qty,
                        quantity_signed=base_qty,
                        base_unit_id=config["base_unit_id"],
                        document_type="sales_return",
                        document_id=sales_return["id"],
                        document_line_id=return_line["id"],
                        operation_key=operation_key,
                        reason=payload["reason"],
                        user_name=payload["user_name"],
                    )
                )
            self._execute("UPDATE public.sales_orders SET status = 'parcial', updated_at = CURRENT_TIMESTAMP WHERE id = %s", (order["id"],))

        return {
            "status": "confirmed",
            "document_type": "sales_return",
            "document_id": sales_return["id"],
            "document_number": sales_return["return_number"],
            "operation_key": operation_key,
            "movement_ids": movement_ids,
        }
