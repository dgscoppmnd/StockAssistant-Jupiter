"""Regresiones de archivos vigentes, selección de proveedor y chat documental."""
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from fastapi import HTTPException

from ai_service import AIProviderError, AIService
from src.vector_store import knowledge_rag
from src.endpoints.endpointRag import QueryRequest, handle_rag_question


class RagPipelineTests(unittest.TestCase):
    @patch.object(knowledge_rag, "generate_ai")
    @patch.object(knowledge_rag, "retrieve_current", return_value=([], []))
    def test_no_evidence_does_not_call_llm(self, retrieve, generate):
        answer = knowledge_rag.answer_rag("¿Una pregunta sin evidencia?")
        self.assertEqual(answer["citations"], [])
        self.assertIsNone(answer["provider"])
        generate.assert_not_called()

    def test_prompt_uses_evidence_and_shared_provider(self):
        evidence = [dict(source="inventario.pdf", page=1, score=0.8, text="Hay 4860 unidades.")]
        with patch.object(
            knowledge_rag, "retrieve_current", return_value=(evidence, ["Pendiente"])
        ) as retrieve, patch.object(
            knowledge_rag,
            "generate_ai",
            return_value=dict(response="4860", provider="openai", model="m", used_fallback=True),
        ) as generate:
            answer = knowledge_rag.answer_rag("¿Cuántas unidades?", target_zone="auto")
        retrieve.assert_called_once_with("¿Cuántas unidades?", limit=3, zone=None)
        self.assertIn("Hay 4860 unidades.", generate.call_args.args[0])
        self.assertIn("p. 1", generate.call_args.args[0])
        self.assertEqual(answer["provider"], "openai")
        self.assertTrue(answer["used_fallback"])
        self.assertEqual(answer["ingestion_warnings"], ["Pendiente"])

    def test_provider_error_is_503(self):
        with patch(
            "src.endpoints.endpointRag.answer_rag",
            side_effect=AIProviderError("down", provider="openai", retryable=True),
        ):
            with self.assertRaises(HTTPException) as error:
                handle_rag_question(QueryRequest(question="¿Pregunta?"))
            self.assertEqual(error.exception.status_code, 503)

    def test_missing_ollama_model_can_use_openai(self):
        with patch.dict("os.environ", {"AI_PROVIDER": "auto", "OPENAI_API_KEY": "test"}):
            service = AIService(openai_call=lambda *_: {"response": "Respuesta", "model": "m"})
        with patch("ai_service.requests.post", return_value=SimpleNamespace(status_code=404)):
            response = service.generate("Pregunta")
        self.assertEqual(response.provider, "openai")
        self.assertTrue(response.used_fallback)


if __name__ == "__main__":
    unittest.main()
