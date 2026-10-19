from datetime import date, datetime, timedelta, timezone
from unittest.mock import patch
from commercial_agent_service import CommercialAgentService

def test_weekly_service_uses_full_history():
    end = date(2026, 10, 14)
    rows = [{"day": end-timedelta(days=240-i), "sold_qty": 6 if (end-timedelta(days=240-i)).weekday()==5 else 4} for i in range(240) if (end-timedelta(days=240-i)).weekday() in (5,6)]
    service = CommercialAgentService(None)
    service._product = lambda product_id: {"name_product": "Semanal"}
    service._all = lambda query, params=(): rows if "540 days" in query else rows[-25:]
    ai = {"response": "Prueba", "provider": "test", "model": "test", "used_fallback": False}
    with patch("commercial_agent_service.generate_ai", return_value=ai), patch("commercial_agent_service.datetime") as clock:
        clock.now.return_value = datetime(2026,10,14,tzinfo=timezone.utc)
        result = service.sales_forecast(4)
    assert result["forecast_method"] == "weekly_repeat"
    assert result["forecast_validation"]["status"] == "rolling_comparison"
