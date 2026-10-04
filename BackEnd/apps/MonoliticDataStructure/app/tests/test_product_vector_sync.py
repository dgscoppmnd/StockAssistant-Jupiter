import unittest
from unittest.mock import MagicMock, patch

from src.api.config import settings
from src.vector_store.product_indexer import (
    delete_product_record,
    product_payload,
    product_point_key,
    product_text,
    stable_point_id,
    upsert_product_records,
)


def operational_product(**overrides):
    product = {
        "pk_product": 42,
        "cdgo_producto_externo": "PRD-42",
        "name_product": "Auriculares deportivos",
        "description_product": "Resistentes al agua para correr",
        "supplier": "Proveedor demo",
        "disabled": False,
    }
    product.update(overrides)
    return product


class ProductVectorSyncTests(unittest.TestCase):
    def test_operational_product_mapping_is_stable_and_searchable(self):
        product = operational_product()

        self.assertEqual(product_point_key(product), "operational:42")
        self.assertEqual(
            product_text(product),
            "Auriculares deportivos. Resistentes al agua para correr. "
            "Proveedor demo. PRD-42",
        )
        self.assertEqual(product_payload(product)["product_id"], "PRD-42")
        self.assertEqual(product_payload(product)["pk_product"], 42)

    def test_catalog_products_keep_the_legacy_point_identity(self):
        self.assertEqual(
            product_point_key({"product_id": "TEST-LAPTOP"}),
            "TEST-LAPTOP",
        )

    @patch("src.vector_store.product_indexer.encode_texts", return_value=[[0.1, 0.2]])
    def test_upsert_creates_collection_and_writes_operational_product(self, encode_texts):
        client = MagicMock()
        client.collection_exists.return_value = False

        count = upsert_product_records([operational_product()], client=client)

        self.assertEqual(count, 1)
        client.create_collection.assert_called_once()
        client.upsert.assert_called_once()
        point = client.upsert.call_args.kwargs["points"][0]
        self.assertEqual(point.id, stable_point_id("operational:42"))
        self.assertEqual(point.payload["product_name"], "Auriculares deportivos")
        self.assertEqual(client.upsert.call_args.kwargs["collection_name"], settings.QDRANT_COLLECTION)
        encode_texts.assert_called_once()

    def test_delete_removes_the_operational_product_point(self):
        client = MagicMock()
        client.collection_exists.return_value = True

        delete_product_record(42, client=client)

        selector = client.delete.call_args.kwargs["points_selector"]
        self.assertEqual(selector.points, [stable_point_id("operational:42")])


if __name__ == "__main__":
    unittest.main()
