import os
import unittest
from unittest.mock import Mock, patch

from ai_service import AIProviderError, AIService, _extract_openai_text


class AIServiceTests(unittest.TestCase):
    def tearDown(self):
        for key in (
            "AI_PROVIDER",
            "OPENAI_API_KEY",
            "OLLAMA_TIMEOUT_SECONDS",
            "OLLAMA_THINK",
        ):
            os.environ.pop(key, None)
    def test_auto_falls_back_to_openai_when_ollama_is_down(self):
        os.environ["AI_PROVIDER"] = "auto"
        os.environ["OPENAI_API_KEY"] = "test-key"

        def fail_ollama(_prompt, _system):
            raise AIProviderError("down", provider="ollama", retryable=True)

        def ok_openai(_prompt, _system):
            return {"response": "cloud answer", "model": "gpt-test"}

        service = AIService(ollama_call=fail_ollama, openai_call=ok_openai)
        result = service.generate("hola")
        self.assertEqual(result.provider, "openai")
        self.assertTrue(result.used_fallback)

    def test_extract_openai_text_from_structured_response(self):
        response = {
            "output": [
                {"type": "reasoning", "content": []},
                {
                    "type": "message",
                    "content": [
                        {"type": "output_text", "text": "Primera parte."},
                        {"type": "output_text", "text": "Segunda parte."},
                    ],
                },
            ]
        }

        self.assertEqual(_extract_openai_text(response), "Primera parte.\nSegunda parte.")

    def test_auto_does_not_fallback_on_non_retryable_ollama_error(self):
        os.environ["AI_PROVIDER"] = "auto"
        os.environ["OPENAI_API_KEY"] = "test-key"

        def fail_ollama(_prompt, _system):
            raise AIProviderError("validation", provider="ollama", retryable=False)

        service = AIService(ollama_call=fail_ollama, openai_call=lambda *_: {"response": "unused", "model": "gpt-test"})
        with self.assertRaises(AIProviderError):
            service.generate("hola")

    def test_generate_for_provider_uses_openai_directly(self):
        os.environ["AI_PROVIDER"] = "openai"
        os.environ["OPENAI_API_KEY"] = "test-key"

        service = AIService(
            ollama_call=lambda *_: {"response": "unused", "model": "qwen-test"},
            openai_call=lambda *_: {"response": "cloud answer", "model": "gpt-test"},
        )

        result = service.generate_for_provider("openai", "hola")
        self.assertEqual(result["provider"], "openai")
        self.assertEqual(result["response"], "cloud answer")

    def test_status_marks_openai_as_preferred_when_configured_mode_is_openai(self):
        os.environ["AI_PROVIDER"] = "openai"
        os.environ["OPENAI_API_KEY"] = "test-key"

        service = AIService(
            ollama_call=lambda *_: {"response": "local answer", "model": "qwen-test"},
            openai_call=lambda *_: {"response": "cloud answer", "model": "gpt-test"},
        )

        status = service.status()
        self.assertEqual(status["preferred_provider"], "openai")
        self.assertEqual(status["fallback_provider"], "ollama")
        self.assertTrue(status["providers"]["openai"]["available"])


    def test_ollama_uses_operational_defaults(self):
        service = AIService()

        self.assertEqual(service.ollama_timeout, 60.0)
        self.assertFalse(service.ollama_think)

    def test_ollama_settings_can_be_overridden(self):
        os.environ["OLLAMA_TIMEOUT_SECONDS"] = "120"
        os.environ["OLLAMA_THINK"] = "true"

        service = AIService()

        self.assertEqual(service.ollama_timeout, 120.0)
        self.assertTrue(service.ollama_think)

    @patch("ai_service.requests.post")
    def test_ollama_request_sends_think_and_timeout(self, mock_post):
        response = Mock(status_code=200)
        response.json.return_value = {
            "response": "respuesta de prueba",
            "model": "qwen3:14b",
            "done": True,
        }
        mock_post.return_value = response

        service = AIService()
        service._call_ollama("hola", None)

        request_options = mock_post.call_args.kwargs
        self.assertFalse(request_options["json"]["think"])
        self.assertEqual(request_options["timeout"], 60.0)

if __name__ == "__main__":
    unittest.main()
