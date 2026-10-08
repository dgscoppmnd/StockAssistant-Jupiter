import sys
import unittest
from pathlib import Path
from unittest.mock import patch
from agent_service import AgentService

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from executive_service import ExecutiveService


class ExecutiveRoutingTests(unittest.TestCase):
    def _service(self):
        service = ExecutiveService(connection=None)
        service._record_decision = lambda *_args: 7  # type: ignore[method-assign]
        return service

    def test_stock_question_routes_to_read_only_stock_agent(self):
        service = self._service()
        service.inventory.stock_alerts = lambda: {"agent": "stock", "alerts": []}  # type: ignore[method-assign]
        result = service.execute("Necesito conocer el stock de la bodega")
        self.assertEqual(result["routed_agent"], "stock")
        self.assertIn("no crea pedidos", result["execution_policy"])

    def test_purchase_question_without_product_only_returns_alerts(self):
        service = self._service()
        service.inventory.stock_alerts = lambda: {"agent": "stock", "alerts": []}  # type: ignore[method-assign]
        result = service.execute("Que debo comprar para reponer")
        self.assertEqual(result["routed_agent"], "purchasing")
        self.assertEqual(result["result"]["agent"], "stock")

    def test_client_question_routes_and_passes_client_id(self):
        service = self._service()
        received = {}

        def client_support(question, client_id):
            received["question"] = question
            received["client_id"] = client_id
            return {
                "agent": "clients",
                "client_id": client_id,
                "answer": "Datos del cliente",
            }

        service.inventory.client_support = client_support

        result = service.execute(
            "Consulta la cuenta del cliente",
            client_id=42,
        )

        self.assertEqual(result["routed_agent"], "clients")
        self.assertEqual(received["client_id"], 42)
        self.assertEqual(result["result"]["agent"], "clients")

    def test_unknown_explicit_agent_is_rejected(self):
        with self.assertRaises(ValueError):
            self._service().execute("hola", agent="desconocido")

class ClientAgentServiceTests(unittest.TestCase):
    def test_client_support_reads_client_and_passes_data_to_prompt(self):
        service = AgentService(connection=None)
        query_data = {}

        def fake_one(query, params=()):
            query_data["query"] = query
            query_data["params"] = params
            return {
                "pk_client": 42,
                "client_code": "CLI-042",
                "name": "Cliente de prueba",
                "fk_type_client": 1,
            }

        service._one = fake_one

        with patch(
            "agent_service.client_agent",
            return_value="Respuesta basada en el registro",
        ) as client_agent_mock:
            result = service.client_support("Consulta este cliente", client_id=42)

        self.assertIn("FROM public.clients", query_data["query"])
        self.assertEqual(query_data["params"], (42,))
        self.assertEqual(result["answer"], "Respuesta basada en el registro")
        self.assertIn("CLI-042", client_agent_mock.call_args.args[0])

    def test_client_support_without_id_does_not_call_model(self):
        service = AgentService(connection=None)

        with patch("agent_service.client_agent") as client_agent_mock:
            result = service.client_support("Consulta un cliente")

        self.assertIn("identificador", result["answer"])
        client_agent_mock.assert_not_called()

if __name__ == "__main__":
    unittest.main()
