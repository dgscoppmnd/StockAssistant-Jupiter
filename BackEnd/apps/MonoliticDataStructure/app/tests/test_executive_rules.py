import sys
import unittest
from pathlib import Path

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

    def test_unknown_explicit_agent_is_rejected(self):
        with self.assertRaises(ValueError):
            self._service().execute("hola", agent="desconocido")


if __name__ == "__main__":
    unittest.main()
