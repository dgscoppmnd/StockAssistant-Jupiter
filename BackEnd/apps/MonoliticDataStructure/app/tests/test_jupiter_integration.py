"""Run against a disposable database initialized with docker/init-scripts/init.sql.

Set JUPITER_TEST_DB to a database ending in _test. Uses only local HTTP/SQL.
"""
import os
from pathlib import Path
import subprocess
import sys
import time
import unittest
from uuid import uuid4

import requests


@unittest.skipUnless(os.getenv("JUPITER_TEST_DB", "").endswith("_test"), "Requires disposable JUPITER_TEST_DB")
class JupiterIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        env = dict(os.environ, DB_NAME=os.environ["JUPITER_TEST_DB"],
                   POSTGRES_DB_NAME=os.environ["JUPITER_TEST_DB"],
                   AUTOMATION_WORKER_ENABLED="false")
        cls.log = open("/tmp/jupiter-integration-api.log", "w+")
        cls.process = subprocess.Popen(
            [sys.executable, "-m", "uvicorn", "src.api.main:app", "--host", "127.0.0.1", "--port", "18001"],
            cwd="/app", env=env, stdout=cls.log, stderr=cls.log)
        cls.addClassCleanup(cls.shutdown)
        cls.base = "http://127.0.0.1:18001"
        for _ in range(60):
            try:
                if requests.get(cls.base + "/health", timeout=1).ok:
                    break
            except requests.RequestException:
                pass
            time.sleep(0.25)
        else:
            cls.log.seek(0)
            raise AssertionError(cls.log.read())
        response = requests.post(cls.base + "/api/auth/password", json={
            "email": "admin@stockassistant.app", "password": "Jupiter!2026Stock"}, timeout=10)
        response.raise_for_status()
        cls.headers = {"Authorization": "Bearer " + response.json()["access_token"]}

    @classmethod
    def shutdown(cls):
        cls.process.terminate()
        cls.process.wait(timeout=10)
        cls.log.close()

    def call(self, method, path, payload=None, expected=200):
        response = requests.request(method, self.base + path, headers=self.headers, json=payload, timeout=15)
        self.assertEqual(response.status_code, expected, response.text)
        return response.json() if response.content else None

    def test_original_and_new_read_routes(self):
        for path in ["/api/v1/products/", "/api/v1/inventory/", "/api/v1/suppliers/",
                     "/api/inventory/dashboard", "/api/inventory/executive-dashboard?period_days=30",
                     "/api/executive/automations", "/api/executive/automations/runs",
                     "/api/executive/purchase-proposals", "/api/executive/decisions"]:
            self.call("GET", path)
        for resource in ("units", "currencies", "warehouses", "suppliers", "unit-conversions", "knowledge-documents"):
            self.call("GET", "/api/master-data/" + resource)
        paths = requests.get(self.base + "/openapi.json", timeout=10).json()["paths"]
        self.assertFalse(any(word in path.lower() for path in paths for word in ("n8n", "tasks", "worksheet")))
        response = requests.get(self.base + "/api/master-data/units", timeout=10)
        self.assertIn(response.status_code, (401, 403))

    def test_master_crud_and_reference_protection(self):
        unit = self.call("POST", "/api/master-data/units", {"values": {"code": uuid4().hex[:12], "name": "Test unit"}}, 201)
        self.call("PUT", f'/api/master-data/units/{unit["id"]}', {"values": {"name": "Updated"}})
        self.call("DELETE", f'/api/master-data/units/{unit["id"]}', expected=204)
        self.call("GET", "/api/master-data/unknown", expected=404)
        self.call("POST", "/api/master-data/unit-conversions", {"values": {"from_unit_id": 1, "to_unit_id": 2, "factor": 0}}, 400)

    def test_inventory_executive_and_automation_end_to_end(self):
        suffix = uuid4().hex[:8]
        product = self.call("POST", "/api/products/", {"name_product": "Integration " + suffix}, 201)
        product_id = product["pk_product"]
        warehouse = self.call("POST", "/api/master-data/warehouses", {"values": {"code": suffix, "name": "Test warehouse"}}, 201)
        self.call("PUT", "/api/inventory/products/config", {"product_id": product_id, "base_unit_code": "unit", "reorder_point": 20, "reorder_quantity": 30})
        line = {"product_id": product_id, "quantity": 10, "unit_code": "unit", "unit_price": 2.5}
        self.call("POST", "/api/inventory/receipts/confirm", {"warehouse_id": warehouse["id"], "supplier_name": "Test supplier", "operation_key": suffix, "lines": [line]})
        result = self.call("POST", "/api/executive/query", {"question": "Estado del stock", "agent": "stock"})
        self.assertEqual(result["routed_agent"], "stock")
        self.assertTrue(result["decision_id"])
        dashboard = self.call("GET", "/api/inventory/executive-dashboard?period_days=30")
        self.assertTrue(any(row["product_id"] == product_id for row in dashboard["priority_purchases"]))
        rules = self.call("GET", "/api/executive/automations")
        for rule in rules:
            result = self.call("POST", f'/api/executive/automations/{rule["id"]}/run')
            self.assertEqual(result["status"], "completed")
        proposals = self.call("GET", "/api/executive/purchase-proposals")
        self.assertTrue(any(row["product_id"] == product_id and row["status"] == "pending_approval" for row in proposals))
        self.call("DELETE", f'/api/master-data/warehouses/{warehouse["id"]}', expected=409)
