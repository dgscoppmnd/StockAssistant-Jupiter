"""Regresiones de paginación y consultas de imágenes del catálogo."""
import json
import sys
import unittest
from decimal import Decimal
from pathlib import Path
from time import perf_counter
from unittest.mock import MagicMock, patch

if __file__ != "<stdin>":
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from fastapi import FastAPI
from fastapi.testclient import TestClient
from DataBaseManagement.dbConectionPostgres import db_context, get_db_products
from DataBaseManagement.dbManagementProducts import get_products_page
from DataBaseManagement.dbservicesProducts import ProductServicesManager
from endpoints.endpointsProducts import router


class ProductsPaginationTests(unittest.TestCase):
    def connection(self, total=100000, rows=None):
        db = MagicMock()
        cursor = db.cursor.return_value.__enter__.return_value
        cursor.fetchone.return_value = {"total": total}
        cursor.fetchall.return_value = rows or []
        return db, cursor

    def test_only_two_queries_and_a_bounded_page(self):
        db, cursor = self.connection(rows=[{"pk_product": 26, "default_image_url": None}])
        with patch("DataBaseManagement.dbservicesProducts.get_default_product_image_by_product_id") as image_query:
            result = ProductServicesManager(db).get_Products_page(2, 25)
        self.assertEqual(result["total"], 100000)
        self.assertEqual(result["page"], 2)
        self.assertEqual(len(result["items"]), 1)
        self.assertEqual(cursor.execute.call_count, 2)
        self.assertEqual(cursor.execute.call_args.args[1], (25, 25))
        self.assertIn("LIMIT %s OFFSET %s", cursor.execute.call_args.args[0])
        image_query.assert_not_called()

    def test_last_page_is_clamped_after_deletion(self):
        db, cursor = self.connection(total=20)
        result = get_products_page(3, 10, db)
        self.assertEqual(result["page"], 2)
        self.assertEqual(cursor.execute.call_args.args[1], (10, 10))

    def test_empty_catalogue(self):
        db, cursor = self.connection(total=0)
        self.assertEqual(get_products_page(5, 10, db), {"items": [], "page": 1, "page_size": 10, "total": 0})

    def test_joined_images_and_money_keep_their_values(self):
        manager = ProductServicesManager()
        with patch("DataBaseManagement.dbservicesProducts.get_default_product_image_by_product_id") as query:
            for url in (None, "/api/media/products/test.png"):
                product = manager._serialize_Product({"pk_product": 1, "price": Decimal("12.34"), "default_image_url": url})
                self.assertEqual(product["price"], 12.34)
                self.assertEqual(product["default_image_url"], url)
            query.assert_not_called()

    def test_single_product_still_looks_up_its_image(self):
        with patch("DataBaseManagement.dbservicesProducts.get_default_product_image_by_product_id", return_value={"public_url": "image.png"}) as query:
            product = ProductServicesManager()._serialize_Product({"pk_product": 1})
            self.assertEqual(product["default_image_url"], "image.png")
            query.assert_called_once()

    def test_legacy_list_also_avoids_per_product_queries(self):
        db, cursor = self.connection(rows=[{"pk_product": n, "default_image_url": None} for n in range(50)])
        with patch("DataBaseManagement.dbservicesProducts.get_default_product_image_by_product_id") as query:
            self.assertEqual(len(ProductServicesManager(db).get_all_Products()), 50)
            query.assert_not_called()
        self.assertEqual(cursor.execute.call_count, 1)

    def test_api_route_and_invalid_pagination(self):
        app = FastAPI()
        app.include_router(router)
        db, _ = self.connection(total=0)
        app.dependency_overrides[get_db_products] = lambda: db
        with TestClient(app) as client:
            response = client.get("/products/page?page=1&page_size=25")
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json(), {"items": [], "total": 0, "page": 1, "page_size": 25})
            for query in ("page=0", "page=-1", "page_size=0", "page_size=101", "page=abc"):
                self.assertEqual(client.get("/products/page?" + query).status_code, 422)
            self.assertEqual(client.get("/products/").status_code, 200)


def benchmark_read_only():
    """Medición sobre el catálogo existente; no modifica registros."""
    with db_context() as db:
        manager = ProductServicesManager(db)
        samples = []
        for page, size in ((1, 10), (2, 25), (1, 50), (1000000, 10)):
            start = perf_counter()
            result = manager.get_Products_page(page, size)
            elapsed = (perf_counter() - start) * 1000
            assert len(result["items"]) <= size
            ids = [row["pk_product"] for row in result["items"]]
            assert ids == sorted(set(ids))
            samples.append({"page": result["page"], "page_size": size, "catalogue_total": result["total"],
                            "returned": len(ids), "milliseconds": round(elapsed, 2),
                            "json_bytes": len(json.dumps(result, default=str).encode())})
        print("READ_ONLY_BENCHMARK " + json.dumps(samples))


if __name__ == "__main__":
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(ProductsPaginationTests)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    if not result.wasSuccessful():
        sys.exit(1)
    if "--benchmark" in sys.argv:
        benchmark_read_only()
