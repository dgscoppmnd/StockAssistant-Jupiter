from decimal import Decimal
from pathlib import Path
import sys
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from ai_service import AIProviderError
from commercial_agent_service import CommercialAgentService


def make_service():
    service = CommercialAgentService(connection=None)
    service._product = lambda product_id: {"name_product": "Televisor 42 pulgadas"}
    service._all = lambda query, params=(): [{"sold_qty": Decimal("1")}]
    return service


def test_sales_forecast_adds_ai_explanation_without_changing_forecast():
    ai_result = {
        "response": "La previsión es orientativa y se basa en un despacho confirmado.",
        "provider": "openai",
        "model": "gpt-test",
        "used_fallback": False,
    }

    with patch("commercial_agent_service.generate_ai", return_value=ai_result) as mock_ai:
        result = make_service().sales_forecast(1)

    assert result["forecast_qty"] == Decimal("30") / Decimal("90")
    assert result["evidence"]["confirmed_dispatch_qty"] == Decimal("1")
    assert result["explanation"] == ai_result["response"]
    assert result["ai"]["provider"] == "openai"
    mock_ai.assert_called_once()


def test_sales_forecast_keeps_calculation_when_ai_is_unavailable():
    with patch(
        "commercial_agent_service.generate_ai",
        side_effect=AIProviderError("Proveedor no disponible", provider="openai",retryable=True,),
    ):
        result = make_service().sales_forecast(1)

    assert result["forecast_qty"] == Decimal("30") / Decimal("90")
    assert result["evidence"]["confirmed_dispatch_qty"] == Decimal("1")
    assert "no está disponible" in result["explanation"]
    assert result["ai"] is None