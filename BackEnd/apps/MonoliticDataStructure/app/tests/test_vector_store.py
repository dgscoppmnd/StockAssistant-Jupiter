"""Run with RUN_VECTOR_INTEGRATION=1 against a reachable Qdrant server.

Uses real embeddings and deletes only its own temporary collection.
"""
import csv
import os
from pathlib import Path
import tempfile
import unittest
from uuid import uuid4


@unittest.skipUnless(os.getenv("RUN_VECTOR_INTEGRATION") == "1", "Requires Qdrant and embedding model")
class VectorStoreIntegrationTests(unittest.TestCase):
    def test_index_search_and_empty_collection(self):
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        from src.api.config import settings
        from src.api.routes.products import router
        from src.vector_store.product_indexer import get_client, index_products

        original_collection = settings.QDRANT_COLLECTION
        settings.QDRANT_COLLECTION = "validation_" + uuid4().hex
        client = get_client()
        try:
            app = FastAPI()
            app.include_router(router, prefix="/products")
            with TestClient(app) as api, tempfile.TemporaryDirectory() as directory:
                response = api.get("/products/semantic-search", params={"q": "ordenador"})
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.json()["items"], [])
                rows = [
                    dict(product_id="TEST-LAPTOP", product_name="Ordenador portatil",
                         description="Ordenador portatil con pantalla y teclado para trabajar",
                         product_category="Electronics", brand="Test", sku="TEST1"),
                    dict(product_id="TEST-COFFEE", product_name="Cafe en grano",
                         description="Cafe arabica tostado para preparar una bebida caliente",
                         product_category="Food", brand="Test", sku="TEST2"),
                ]
                path = Path(directory) / "products.csv"
                with path.open("w", newline="", encoding="utf-8") as file:
                    writer = csv.DictWriter(file, fieldnames=rows[0].keys())
                    writer.writeheader()
                    writer.writerows(rows)
                self.assertEqual(index_products(path, 1), 2)
                self.assertEqual(index_products(path, 1), 2)
                self.assertEqual(client.count(settings.QDRANT_COLLECTION, exact=True).count, 2)
                response = api.get("/products/semantic-search", params={"q": "ordenador para trabajar", "limit": 1})
                self.assertEqual(response.status_code, 200)
                self.assertEqual(len(response.json()["items"]), 1)
                self.assertEqual(response.json()["items"][0]["product_id"], "TEST-LAPTOP")
                response = api.get("/products/semantic-search", params={"q": "bebida caliente", "category": "Food"})
                self.assertEqual(response.status_code, 200)
                self.assertEqual([item["product_id"] for item in response.json()["items"]], ["TEST-COFFEE"])
                self.assertEqual(api.get("/products/semantic-search", params={"q": "x"}).status_code, 422)
        finally:
            try:
                if client.collection_exists(settings.QDRANT_COLLECTION):
                    client.delete_collection(settings.QDRANT_COLLECTION)
            finally:
                client.close()
                settings.QDRANT_COLLECTION = original_collection
