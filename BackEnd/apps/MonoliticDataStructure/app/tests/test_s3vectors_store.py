import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from vector_store.s3vectors_store import S3VectorsStore, truncate_metadata


class S3VectorsStoreTests(unittest.TestCase):
    def setUp(self):
        self.client = MagicMock()
        self.store = S3VectorsStore("documents", bucket="bucket", client=self.client)

    def test_put_splits_batches_of_500(self):
        items = [{"key": str(i), "vector": [0.1, 0.2], "metadata": {"chunk_id": str(i)}} for i in range(1001)]

        self.assertEqual(self.store.put(items), 1001)

        sizes = [len(c.kwargs["vectors"]) for c in self.client.put_vectors.call_args_list]
        self.assertEqual(sizes, [500, 500, 1])
        first = self.client.put_vectors.call_args_list[0].kwargs["vectors"][0]
        self.assertEqual(first["data"], {"float32": [0.1, 0.2]})
        self.assertEqual(first["metadata"], {"chunk_id": "0"})

    def test_query_converts_distance_to_score_and_clamps_top_k(self):
        self.client.query_vectors.return_value = {
            "vectors": [{"key": "a", "distance": 0.25, "metadata": {"x": 1}}]
        }

        hits = self.store.query([1.0, 0.0], 500, {"chunk_id": {"$in": ["a"]}})

        params = self.client.query_vectors.call_args.kwargs
        self.assertEqual(params["topK"], 100)
        self.assertEqual(params["filter"], {"chunk_id": {"$in": ["a"]}})
        self.assertAlmostEqual(hits[0]["score"], 0.75)

    def test_delete_and_truncate(self):
        self.store.delete(["a", "b"])
        self.assertEqual(self.client.delete_vectors.call_args.kwargs["keys"], ["a", "b"])
        self.assertEqual(truncate_metadata({"d": "x" * 500, "n": None}, {"d": 10}), {"d": "x" * 10})


if __name__ == "__main__":
    unittest.main()
