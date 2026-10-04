import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from knowledge_vectors import EmbeddingProviderError, EmbeddingSpec, KnowledgeVectors, embed


class FakeResponse:
    def __init__(self, status_code, payload):
        self.status_code = status_code
        self.payload = payload

    def json(self):
        return self.payload


class KnowledgeVectorsTests(unittest.TestCase):
    def setUp(self):
        self.environment = patch.dict(
            os.environ,
            {
                "RAG_EMBEDDING_PROVIDER": "auto",
                "RAG_OLLAMA_EMBEDDING_MODEL": "embeddinggemma",
                "OPENAI_EMBEDDING_MODEL": "text-embedding-3-small",
                "OPENAI_API_KEY": "test-key",
            },
            clear=False,
        )
        self.environment.start()
        self.addCleanup(self.environment.stop)

    @patch("knowledge_vectors.requests.post")
    def test_auto_falls_back_to_openai_embeddings_when_ollama_is_down(self, post):
        post.side_effect = [
            requests.ConnectionError("down"),
            FakeResponse(200, {"data": [{"index": 0, "embedding": [0.1, 0.2]}]}),
        ]

        vectors, spec = embed(["Manual de producto"])

        self.assertEqual(vectors, [[0.1, 0.2]])
        self.assertEqual(spec, EmbeddingSpec("openai", "text-embedding-3-small"))
        self.assertEqual(post.call_args_list[1].args[0], "https://api.openai.com/v1/embeddings")

    @patch("knowledge_vectors.requests.post")
    def test_auto_does_not_fallback_when_ollama_rejects_the_request(self, post):
        post.return_value = FakeResponse(400, {})

        with self.assertRaises(EmbeddingProviderError):
            embed(["Manual de producto"])

        self.assertEqual(post.call_count, 1)

    def test_qdrant_collection_depends_on_provider_and_model(self):
        local = KnowledgeVectors(EmbeddingSpec("ollama", "embeddinggemma"))
        cloud = KnowledgeVectors(EmbeddingSpec("openai", "text-embedding-3-small"))

        self.assertNotEqual(local.collection, cloud.collection)


if __name__ == "__main__":
    unittest.main()
