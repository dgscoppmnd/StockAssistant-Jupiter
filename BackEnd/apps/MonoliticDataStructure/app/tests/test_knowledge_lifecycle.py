import unittest
from unittest.mock import MagicMock, patch

from knowledge_service import KnowledgeService, split_pages
from knowledge_vectors import EmbeddingProviderError, EmbeddingSpec, _validate_vectors
from knowledge_worker import cleanup_retired_vectors


class KnowledgeLifecycleTests(unittest.TestCase):
    def test_chunks_keep_pages_limit_overlap_and_all_content(self):
        text = "".join(chr(65 + n % 26) for n in range(2000))
        chunks = split_pages([(3, text), (4, "Final de la página cuatro")])
        first = [c for c in chunks if c["page"] == 3]
        self.assertTrue(all(len(c["content"]) <= 900 for c in chunks))
        reconstructed = first[0]["content"] + "".join(c["content"][120:] for c in first[1:])
        self.assertEqual(reconstructed, text)
        self.assertEqual(chunks[-1]["page"], 4)

    def test_rejects_invalid_vectors_instead_of_silently_dropping_chunks(self):
        for vectors in ([], [[1, 2]], [[1], [1, 2]], [[0, 0], [1, 2]], [[float("nan")], [1]]):
            with self.subTest(vectors=vectors), self.assertRaises(EmbeddingProviderError):
                _validate_vectors(vectors, 2, "local")

    def test_retired_document_is_excluded_after_qdrant_returns(self):
        service = KnowledgeService(MagicMock())
        row = dict(
            embedding_provider="local", embedding_model="multilingual", content="Política antigua"
        )
        with patch.object(service, "available_chunks", side_effect=[{"a": row}, {}]), patch(
            "knowledge_service.embed",
            return_value=([[1, 2]], EmbeddingSpec("local", "multilingual")),
        ), patch("knowledge_service.KnowledgeVectors") as store:
            store.return_value.search.return_value = [{"id": "a", "score": 0.9}]
            self.assertEqual(service.retrieve("Política"), [])

    def test_retired_vectors_are_removed_and_cleanup_acknowledged(self):
        connection = MagicMock()
        cursor = connection.cursor.return_value.__enter__.return_value
        cursor.fetchall.return_value = [("a", "local", "model")]
        with patch("knowledge_worker.KnowledgeVectors") as store:
            cleanup_retired_vectors(connection)
        store.return_value.delete.assert_called_once_with(["a"])
        self.assertIn(
            "DELETE FROM public.knowledge_vector_deletions", cursor.execute.call_args.args[0]
        )

    def test_failed_vector_cleanup_stays_pending(self):
        connection = MagicMock()
        cursor = connection.cursor.return_value.__enter__.return_value
        cursor.fetchall.return_value = [("a", "local", "model")]
        with patch("knowledge_worker.KnowledgeVectors") as store:
            store.return_value.delete.side_effect = RuntimeError("Qdrant down")
            with self.assertRaises(RuntimeError):
                cleanup_retired_vectors(connection)
        self.assertEqual(cursor.execute.call_count, 1)


if __name__ == "__main__":
    unittest.main()
