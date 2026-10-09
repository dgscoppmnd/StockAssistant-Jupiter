"""Three integration scenarios using a disposable PostgreSQL database."""
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from decimal import Decimal
import os
from pathlib import Path
import threading
import unittest
from uuid import uuid4

import psycopg2
from psycopg2 import sql
from fastapi import FastAPI
from fastapi.testclient import TestClient

from DataBaseManagement.dbConectionPostgres import get_db_products
from DataBaseManagement.schemasSales import InvoiceDraft, OrderDraft
from endpoints.endpointsSales import router
from endpoints.endpointsInventory import router as inventory_router
from inventory_service import InventoryError, InventoryService
from sales_schema import sales_schema_sql
from sales_service import SalesService
from security import create_session_token


class SalesIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.database = "jupiter_sales_test_" + uuid4().hex
        cls.connection_args = dict(
            host=os.environ["DB_HOST"],
            port=os.environ["DB_PORT"],
            user=os.environ["DB_USER"],
            password=os.environ["DB_PASSWORD"],
        )
        cls.admin = psycopg2.connect(dbname=os.environ["DB_NAME"], **cls.connection_args)
        cls.admin.autocommit = True
        with cls.admin.cursor() as cursor:
            cursor.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(cls.database)))
        try:
            connection = cls.connect()
            with connection:
                with connection.cursor() as cursor:
                    cursor.execute(
                        Path("/app/docker/init-scripts/init.sql").read_text(encoding="utf-8")
                    )
                    cursor.execute(sales_schema_sql())
            connection.close()
        except Exception:
            cls.tearDownClass()
            raise

    @classmethod
    def connect(cls):
        return psycopg2.connect(dbname=cls.database, **cls.connection_args)

    @classmethod
    def tearDownClass(cls):
        if not cls.database.startswith("jupiter_sales_test_"):
            raise RuntimeError("Refusing to drop a non-test database")
        with cls.admin.cursor() as cursor:
            cursor.execute(
                sql.SQL("DROP DATABASE {} WITH (FORCE)").format(sql.Identifier(cls.database))
            )
        cls.admin.close()

    def setUp(self):
        self.connection = self.connect()
        inventory = InventoryService(self.connection)
        self.user = inventory._fetchone(
            "SELECT id,email,sales_permissions FROM public.users ORDER BY id LIMIT 1"
        )
        self.sales = SalesService(self.connection, self.user)
        suffix = uuid4().hex
        with inventory.transaction():
            self.product = inventory._fetchone(
                "INSERT INTO public.productos(name_product,currency) VALUES (%s,'EUR') RETURNING pk_product",
                ("Producto " + suffix,),
            )["pk_product"]
            self.client = inventory._fetchone(
                "INSERT INTO public.clients(name) VALUES (%s) RETURNING pk_client",
                ("Cliente " + suffix,),
            )["pk_client"]
            self.warehouse = inventory._fetchone(
                "INSERT INTO public.inventory_warehouses(code,name) VALUES (%s,%s) RETURNING id",
                (suffix, "Bodega " + suffix),
            )["id"]
            self.address = inventory._fetchone(
                """
                INSERT INTO public.globlal_addresses(address_line_1,city,country_code)
                VALUES ('Calle prueba','Madrid','ES') RETURNING id
            """
            )["id"]
            self.association = inventory._fetchone(
                """
                INSERT INTO public.clients_addresses(client_id,global_address_id,address_type)
                VALUES (%s,%s,'Dirección principal') RETURNING id
            """,
                (self.client, self.address),
            )["id"]
            inventory._get_product_inventory_config(self.product)
            inventory._execute(
                "INSERT INTO public.inventory_stock_levels(product_id,warehouse_id,physical_qty) VALUES (%s,%s,20)",
                (self.product, self.warehouse),
            )
        app = FastAPI()
        app.include_router(router, prefix="/api")
        app.include_router(inventory_router, prefix="/api")

        def database():
            connection = self.connect()
            try:
                yield connection
            finally:
                connection.close()

        app.dependency_overrides[get_db_products] = database
        self.api = TestClient(app)
        self.headers = {
            "Authorization": "Bearer " + create_session_token({"user_id": self.user["id"]})
        }

    def tearDown(self):
        self.api.close()
        self.connection.close()

    def draft(self, qty=10):
        return OrderDraft(
            operation_key=str(uuid4()),
            client_id=self.client,
            warehouse_id=self.warehouse,
            address_association_id=self.association,
            currency_code="EUR",
            lines=[
                dict(
                    product_id=self.product,
                    quantity=qty,
                    unit_code="unit",
                    unit_price=10,
                    discount_percent=10,
                    tax_percent=21,
                )
            ],
        ).model_dump()

    def operation(self, line, qty):
        return {
            "operation_key": str(uuid4()),
            "lines": [{"line_id": line, "quantity": Decimal(str(qty))}],
            "reason": "Prueba",
        }

    def stock(self):
        row = self.sales._fetchone(
            "SELECT physical_qty,reserved_qty FROM public.inventory_stock_levels WHERE product_id=%s AND warehouse_id=%s",
            (self.product, self.warehouse),
        )
        return row["physical_qty"], row["reserved_qty"]

    def test_order_lifecycle_and_legacy_route_safety(self):
        draft = self.draft()
        order = self.sales.save_order(draft)["id"]
        self.assertEqual(self.stock(), (20, 0))
        self.assertEqual(self.sales.save_order(draft)["id"], order)
        other = self.sales.save_order(self.draft())["id"]
        self.sales.delete_order(other, {"operation_key": str(uuid4())})
        self.assertEqual(self.stock(), (20, 0))
        line = self.sales.detail("order", order)["lines"][0]["id"]
        reserve = self.operation(line, 6)
        self.sales.reserve_order(order, reserve)
        self.sales.reserve_order(order, reserve)
        self.assertEqual(self.stock(), (20, 6))
        with self.assertRaises(InventoryError):
            self.sales.reserve_order(
                order, {**reserve, "lines": [{"line_id": line, "quantity": 7}]}
            )
        dispatch = self.operation(line, 2)
        result = self.sales.dispatch_order(order, dispatch)
        self.assertEqual(self.sales.dispatch_order(order, dispatch), result)
        invoice = self.sales.detail("invoice", result["invoice_id"])
        self.assertEqual(invoice["total"], Decimal("21.78"))
        self.assertTrue(invoice["events"])
        self.assertEqual(self.stock(), (18, 4))
        with self.sales.transaction():
            self.sales._execute(
                "UPDATE public.productos SET name_product='Nuevo nombre',price=999 WHERE pk_product=%s",
                (self.product,),
            )
        self.assertEqual(
            self.sales.detail("invoice", invoice["id"])["lines"][0]["description_snapshot"],
            invoice["lines"][0]["description_snapshot"],
        )
        response = self.api.post(
            "/api/inventory/sales-orders/cancel",
            headers=self.headers,
            json={
                "sales_order_id": order,
                "warehouse_id": self.warehouse,
                "operation_key": str(uuid4()),
                "reason": "Cancelar pendientes",
                "user_name": "Impostor",
            },
        )
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(self.stock(), (18, 0))
        actor = self.sales._fetchone(
            "SELECT user_name FROM public.inventory_movements WHERE document_type='sales_order' AND document_id=%s ORDER BY id DESC LIMIT 1",
            (order,),
        )
        self.assertEqual(actor["user_name"], self.user["email"])
        self.sales.invoice_action(
            invoice["id"], {"operation_key": str(uuid4()), "reason": "Corrección"}, "void"
        )
        self.assertEqual(self.stock(), (18, 0))
        correction = self.sales._fetchone(
            "SELECT * FROM public.sales_invoices WHERE correction_of_id=%s", (invoice["id"],)
        )
        self.assertEqual(correction["total"], Decimal("-21.78"))
        returned = self.operation(line, 2)
        self.sales.return_order(order, returned)
        self.sales.return_order(order, returned)
        self.assertEqual(self.stock(), (20, 0))
        with self.assertRaises(InventoryError):
            self.sales.return_order(order, self.operation(line, 1))
        legacy = InventoryService(self.connection)
        reserved = legacy.reserve_stock(
            {
                "warehouse_id": self.warehouse,
                "customer_name": "Venta existente",
                "operation_key": str(uuid4()),
                "user_name": self.user["email"],
                "lines": [
                    {
                        "product_id": self.product,
                        "quantity": Decimal("1"),
                        "unit_code": "unit",
                        "unit_price": Decimal("9"),
                    }
                ],
            }
        )
        shipped = legacy.dispatch_sales_order(
            {
                "sales_order_id": reserved["document_id"],
                "warehouse_id": self.warehouse,
                "operation_key": str(uuid4()),
                "user_name": self.user["email"],
                "lines": [
                    {"product_id": self.product, "quantity": Decimal("1"), "unit_code": "unit"}
                ],
            }
        )
        frozen = self.sales.detail("invoice", shipped["invoice_id"])
        self.assertEqual(frozen["total"], Decimal("9"))
        self.assertEqual(frozen["customer_snapshot"]["name"], "Venta existente")
        self.assertTrue(frozen["lines"][0]["description_snapshot"])

    def test_concurrent_reservations_permissions_and_pagination(self):
        orders = [self.sales.save_order(self.draft(8))["id"] for _ in range(2)]
        lines = [self.sales.detail("order", order)["lines"][0]["id"] for order in orders]
        with self.sales.transaction():
            self.sales._execute(
                "UPDATE public.inventory_stock_levels SET physical_qty=10 WHERE product_id=%s AND warehouse_id=%s",
                (self.product, self.warehouse),
            )
        barrier = threading.Barrier(2)

        def reserve(index):
            connection = self.connect()
            try:
                service = SalesService(connection, self.user)
                barrier.wait(timeout=10)
                try:
                    service.reserve_order(orders[index], self.operation(lines[index], 8))
                    return "ok"
                except InventoryError:
                    return "rejected"
            finally:
                connection.close()

        with ThreadPoolExecutor(max_workers=2) as pool:
            outcomes = list(pool.map(reserve, range(2)))
        self.assertCountEqual(outcomes, ["ok", "rejected"])
        self.assertEqual(self.stock(), (10, 8))
        forbidden = SalesService(self.connection, {**self.user, "sales_permissions": ["read"]})
        with self.assertRaises(InventoryError):
            forbidden.save_order(self.draft())
        self.assertEqual(self.api.get("/api/sales/orders").status_code, 401)
        with self.sales.transaction():
            self.sales._execute(
                "UPDATE public.users SET sales_permissions=ARRAY['read'] WHERE id=%s",
                (self.user["id"],),
            )
        response = self.api.post(
            "/api/sales/orders",
            headers=self.headers,
            json=OrderDraft(**self.draft()).model_dump(mode="json"),
        )
        self.assertEqual(response.status_code, 403, response.text)
        with self.sales.transaction():
            self.sales._execute(
                "UPDATE public.users SET sales_permissions=%s WHERE id=%s",
                (self.user["sales_permissions"], self.user["id"]),
            )
        listed = self.api.get(
            "/api/sales/orders", headers=self.headers, params={"client_id": self.client, "size": 1}
        )
        self.assertEqual(listed.status_code, 200, listed.text)
        self.assertEqual(listed.json()["total"], 2)
        self.assertEqual(len(listed.json()["items"]), 1)
        payload = OrderDraft(**self.draft()).model_dump(mode="json")
        payload["user_name"] = "Impostor"
        self.assertEqual(
            self.api.post("/api/sales/orders", headers=self.headers, json=payload).status_code, 422
        )

    def test_invoice_drafts_issue_retry_and_immutable_documents(self):
        order = self.sales.save_order(self.draft(5))["id"]
        line = self.sales.detail("order", order)["lines"][0]["id"]
        # Fixture for an historical dispatch without an invoice; no service can
        # create another invoice over quantities already auto-invoiced.
        with self.sales.transaction():
            self.sales._execute(
                "UPDATE public.sales_order_lines SET dispatched_qty=3,pending_qty=2 WHERE id=%s",
                (line,),
            )
            self.sales._execute(
                "UPDATE public.inventory_stock_levels SET physical_qty=17 WHERE product_id=%s AND warehouse_id=%s",
                (self.product, self.warehouse),
            )
        payload = InvoiceDraft(
            operation_key=str(uuid4()),
            sales_order_id=order,
            invoice_date=date.today(),
            lines=[{"line_id": line, "quantity": 2}],
        ).model_dump()
        invoice = self.sales.save_invoice(payload)["id"]
        self.assertEqual(self.stock(), (17, 0))
        with self.assertRaises(InventoryError):
            self.sales.save_invoice({**payload, "operation_key": str(uuid4())})
        edited = {**payload, "operation_key": str(uuid4()), "reference": "Referencia editada"}
        self.sales.save_invoice(edited, invoice)
        issue = {"operation_key": str(uuid4())}
        self.sales.invoice_action(invoice, issue, "issue")
        self.sales.invoice_action(invoice, issue, "issue")
        self.assertEqual(self.stock(), (17, 0))
        self.assertEqual(self.sales.order_lines(order)[0]["invoiced_qty"], 2)
        with self.assertRaises(InventoryError):
            self.sales.save_invoice({**edited, "operation_key": str(uuid4())}, invoice)
        with self.assertRaises(InventoryError):
            self.sales.invoice_action(invoice, {"operation_key": str(uuid4())}, "delete")
        self.assertEqual(self.sales.detail("invoice", invoice)["reference"], "Referencia editada")
        remaining = self.sales.save_invoice(
            {**payload, "operation_key": str(uuid4()), "lines": [{"line_id": line, "quantity": 1}]}
        )["id"]
        self.sales.invoice_action(remaining, {"operation_key": str(uuid4())}, "delete")
        self.assertEqual(self.stock(), (17, 0))


if __name__ == "__main__":
    unittest.main(verbosity=2)
