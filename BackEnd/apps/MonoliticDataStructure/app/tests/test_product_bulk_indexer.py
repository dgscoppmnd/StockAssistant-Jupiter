import csv
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from vector_store import product_bulk_indexer as bulk


class ProductBulkIndexerTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        self.csv = self.root / "products.csv"
        self.checkpoint = self.root / "progress.json"
        with self.csv.open("w", encoding="utf-8", newline="") as output:
            writer = csv.DictWriter(output, fieldnames=sorted(bulk.FIELDS))
            writer.writeheader()
            for number in range(5):
                writer.writerow({
                    "product_id": f"PRD{number}",
                    "product_name": "Silla",
                    "description": "Metal",
                    "brand": "",
                    "sku": f"SKU{number}",
                    "product_category": "Home",
                })
        self.store = MagicMock()
        self.store.bucket = "test-bucket"
        self.store.index_name = "products"
        self.store.client.get_index.return_value = {"index": {
            "indexArn": "arn:test:index/products",
            "dimension": 1536,
            "distanceMetric": "cosine",
            "dataType": "float32",
        }}
        environment = patch.dict(os.environ, {
            "VECTOR_BACKEND": "s3vectors",
            "RAG_EMBEDDING_PROVIDER": "openai",
            "OPENAI_EMBEDDING_MODEL": "text-embedding-3-small",
            "OPENAI_API_KEY": "test-only",
        })
        environment.start()
        self.addCleanup(environment.stop)
        store_patch = patch.object(bulk, "S3VectorsStore", return_value=self.store)
        store_patch.start()
        self.addCleanup(store_patch.stop)
        embed_patch = patch.object(
            bulk, "encode_texts", side_effect=lambda texts: [[0.1] * 1536 for _ in texts]
        )
        self.embed = embed_patch.start()
        self.addCleanup(embed_patch.stop)

    def run_import(self, limit=3, batch_size=2):
        return bulk.run_import(
            self.csv, self.checkpoint, batch_size=batch_size, limit=limit
        )

    def test_limits_resume_and_completed_noop(self):
        self.assertEqual(self.run_import(), 3)
        self.assertEqual([len(call.args[0]) for call in self.store.put.call_args_list], [2, 1])
        self.assertEqual(self.run_import(), 5)
        self.assertEqual(self.run_import(), 5)
        self.assertEqual(self.embed.call_count, 3)
        self.assertEqual(self.store.put.call_count, 3)
        metadata = self.store.put.call_args_list[0].args[0][0]["metadata"]
        self.assertEqual(metadata["brand"], "")
        self.assertNotIn("nan", metadata.values())

    def test_failed_write_reuses_cached_embeddings(self):
        self.store.put.side_effect = [None, RuntimeError("write failed")]
        with self.assertRaisesRegex(RuntimeError, "write failed"):
            self.run_import(limit=4)
        state = json.loads(self.checkpoint.read_text(encoding="utf-8"))
        self.assertEqual(state["completed"], 2)
        self.assertEqual(len(state["pending"]), 2)
        self.store.put.side_effect = None
        self.assertEqual(self.run_import(limit=2), 4)
        self.assertEqual(self.embed.call_count, 2)
        self.assertFalse(self.checkpoint.with_name("progress.json.lock").exists())

    def test_auth_fails_before_embeddings(self):
        self.store.client.get_index.side_effect = RuntimeError("credentials")
        with self.assertRaisesRegex(RuntimeError, "credentials"):
            self.run_import()
        self.embed.assert_not_called()

    def test_rejects_incompatible_index_before_embeddings(self):
        self.store.client.get_index.return_value["index"]["dimension"] = 384
        with self.assertRaisesRegex(ValueError, "1536"):
            self.run_import()
        self.embed.assert_not_called()

    def test_rejects_changed_source_or_configuration(self):
        self.run_import(limit=1)
        with self.assertRaisesRegex(ValueError, "does not match"):
            self.run_import(batch_size=3)
        with self.csv.open("a", encoding="utf-8") as output:
            output.write(",,Extra,PRD6,Name,\n")
        with self.assertRaisesRegex(ValueError, "does not match"):
            self.run_import()

    def test_rejects_wrong_account_index_on_resume(self):
        self.run_import(limit=1)
        self.store.client.get_index.return_value["index"]["indexArn"] = "arn:other-account"
        with self.assertRaisesRegex(ValueError, "does not match"):
            self.run_import()

    def test_provider_failure_does_not_advance_progress(self):
        self.embed.side_effect = RuntimeError("quota")
        with self.assertRaisesRegex(RuntimeError, "quota"):
            self.run_import()
        self.assertEqual(json.loads(self.checkpoint.read_text())["completed"], 0)
        self.store.put.assert_not_called()

    def test_wrong_embedding_shape_is_not_written(self):
        self.embed.side_effect = lambda texts: [[1.0] for _ in texts]
        with self.assertRaisesRegex(ValueError, "dimension"):
            self.run_import()
        self.store.put.assert_not_called()

    def test_prevents_concurrent_run(self):
        lock = self.checkpoint.with_name("progress.json.lock")
        lock.write_text("another-process")
        with self.assertRaises(FileExistsError):
            self.run_import()
        self.assertTrue(lock.exists())
        self.embed.assert_not_called()

    def test_rejects_duplicate_ids_before_embeddings(self):
        with self.csv.open("a", encoding="utf-8") as output:
            output.write(",,Home,PRD0,Name,\n")
        with self.assertRaisesRegex(ValueError, "duplicate"):
            self.run_import()
        self.embed.assert_not_called()

    def test_cache_survives_failure_saving_confirmed_progress(self):
        original_save = bulk.save_checkpoint

        def fail_confirmation(path, state):
            if state["completed"]:
                raise OSError("disk full")
            original_save(path, state)

        with patch.object(bulk, "save_checkpoint", side_effect=fail_confirmation):
            with self.assertRaisesRegex(OSError, "disk full"):
                self.run_import(limit=2)
        self.assertEqual(self.run_import(limit=2), 2)
        self.assertEqual(self.embed.call_count, 1)
        self.assertEqual(self.store.put.call_count, 2)

    def test_rejects_invalid_numeric_embeddings(self):
        for value in (float("nan"), float("inf"), "0.1", True, 0):
            with self.subTest(value=value):
                self.embed.side_effect = lambda texts: [[value] * 1536 for _ in texts]
                with self.assertRaises(ValueError):
                    self.run_import()
        self.store.put.assert_not_called()

    def test_checkpoint_cannot_overwrite_csv(self):
        original = self.csv.read_bytes()
        with self.assertRaisesRegex(ValueError, "different files"):
            bulk.run_import(self.csv, self.csv, batch_size=2, limit=2)
        self.assertEqual(self.csv.read_bytes(), original)

    def test_pending_batch_must_fit_limit(self):
        self.store.put.side_effect = RuntimeError("write failed")
        with self.assertRaises(RuntimeError):
            self.run_import(limit=2)
        with self.assertRaisesRegex(ValueError, "cover the pending batch"):
            self.run_import(limit=1)
        self.assertEqual(self.embed.call_count, 1)


if __name__ == "__main__":
    unittest.main()
