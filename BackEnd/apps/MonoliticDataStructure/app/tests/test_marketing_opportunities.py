from datetime import datetime, timezone
from decimal import Decimal
import json
from unittest.mock import Mock, patch

import pytest

from ai_service import AIProviderError
from executive_service import ExecutiveService
from marketing_service import MarketingService, parse_campaigns, select_candidates


def candidate(product_id=1, recent=30, previous=15, stock=10, days=5):
    return {"product_id": product_id, "product_name": f"Producto {product_id}",
            "recent_qty": recent, "previous_qty": previous, "available_qty": stock,
            "recent_dispatch_days": days, "base_unit_code": "UN"}


def ai_payload(ids=(1,)):
    return json.dumps({"campaigns": [{"product_id": product_id,
        "objective": "Comprobar una campaña de visibilidad", "audience_hypothesis": "Personas interesadas en esta categoría",
        "channel": "web", "message": "Descubre el producto y consulta sus características.",
        "reason": "Hay crecimiento interno; validar la oportunidad antes de lanzar."} for product_id in ids]})


def service(rows=None, external_status="ok"):
    instance = MarketingService(None)
    instance.commercial._all = Mock(return_value=rows if rows is not None else [candidate()])
    instance.commercial.market_intelligence = Mock(return_value={
        "status": external_status, "source": {"name": "serpapi", "available": external_status == "ok"},
        "generated_at": "2026-10-19T12:00:00Z", "data": None,
        "summary": {"status": "descriptive_comparison", "change_index_points": 5} if external_status == "ok" else None,
    })
    return instance


def test_ranks_increase_deterministically_and_limits_to_three():
    rows = [candidate(1, 30, 20), candidate(2, 80, 20), candidate(3, 50, 20), candidate(4, 40, 20)]
    selected = select_candidates(rows)
    assert [row["product_id"] for row in selected] == [2, 3, 4]
    assert selected[0]["increase_percent"] == Decimal("300.00")
    assert [row["product_id"] for row in select_candidates(list(reversed(rows)), 2)] == [2, 3]


@pytest.mark.parametrize("row", [
    candidate(recent=2, previous=1), candidate(recent=10, previous=0),
    candidate(recent=9, previous=5), candidate(stock=0), candidate(stock=-2),
    candidate(days=2), candidate(recent=15, previous=15), candidate(recent=10, previous=20),
])
def test_rejects_tiny_baselines_no_growth_no_stock_and_isolated_dispatches(row):
    assert select_candidates([row]) == []


@pytest.mark.parametrize("limit", [0, 4, -1])
def test_selection_limit_is_bounded(limit):
    with pytest.raises(ValueError):
        select_candidates([candidate()], limit)


def test_no_candidates_does_not_query_external_source_or_ai():
    instance = service([])
    with patch("marketing_service.generate_ai") as ai:
        result = instance.opportunities()
    assert result["status"] == "no_candidates"
    assert result["opportunities"] == []
    ai.assert_not_called()
    instance.commercial.market_intelligence.assert_not_called()


def test_valid_proposal_binds_ai_output_to_real_product_and_does_not_recalculate():
    instance = service()
    with patch("marketing_service.generate_ai", return_value={"response": ai_payload(), "provider": "test", "model": "test", "used_fallback": False}) as ai:
        result = instance.opportunities()
    row = result["opportunities"][0]
    assert row["recent_qty"] == 30
    assert row["previous_qty"] == 15
    assert row["increase_percent"] == 100
    assert row["campaign_origin"] == "ai"
    assert row["state"] == "draft_requires_review"
    instance.commercial.market_intelligence.assert_called_once_with("Producto 1", "ES", include_ai=False)
    assert json.loads(ai.call_args.args[0])["candidates"][0]["external"]["status"] == "ok"


@pytest.mark.parametrize("external_status", ["no_data", "source_unavailable"])
def test_missing_external_evidence_is_preserved_in_prompt_and_response(external_status):
    instance = service(external_status=external_status)
    with patch("marketing_service.generate_ai", return_value={"response": ai_payload(), "provider": "test"}) as ai:
        result = instance.opportunities()
    assert result["opportunities"][0]["external"]["status"] == external_status
    assert json.loads(ai.call_args.args[0])["candidates"][0]["external"]["summary"] is None


def test_ai_failure_preserves_template_and_evidence():
    instance = service()
    with patch("marketing_service.generate_ai", side_effect=AIProviderError("offline", provider="test", retryable=False)):
        result = instance.opportunities()
    assert result["ai"] is None
    assert result["opportunities"][0]["campaign_origin"] == "template"
    assert result["opportunities"][0]["available_qty"] == 10
    assert "plantilla" in result["warnings"][-1]


@pytest.mark.parametrize("text", [
    "not json", '{"campaigns":[]}', ai_payload((999,)),
    ai_payload((1, 1)), ai_payload().replace('"web"', '"autopublish"'),
    ai_payload().replace('"product_id": 1', '"product_id": true'),
])
def test_invalid_or_invented_campaigns_are_rejected(text):
    with pytest.raises(ValueError):
        parse_campaigns(text, {1})


def test_invalid_ai_json_uses_template_instead_of_showing_raw_response():
    instance = service()
    with patch("marketing_service.generate_ai", return_value={"response": "```wrong```"}):
        result = instance.opportunities()
    assert result["opportunities"][0]["campaign_origin"] == "template"
    assert "wrong" not in result["explanation"]


@pytest.mark.parametrize("message", ["Aprovecha un 20% de descuento", "Envío gratis", "Oferta garantizada por 10 €"])
def test_message_cannot_invent_commercial_conditions(message):
    payload = json.loads(ai_payload())
    payload["campaigns"][0]["message"] = message
    with pytest.raises(ValueError):
        parse_campaigns(json.dumps(payload), {1})


@pytest.mark.parametrize("message", [
    "Descubre nuestros auriculares inalámbricos con la mejor calidad de sonido y comodidad, ¡perfectos para tu día a día!",
    "Auriculares premium para todos", "El producto perfecto", "Calidad superior",
])
def test_unverified_quality_claims_are_rejected(message):
    payload = json.loads(ai_payload())
    payload["campaigns"][0]["message"] = message
    with pytest.raises(ValueError, match="cualidades no verificadas"):
        parse_campaigns(json.dumps(payload), {1})


def test_one_corrective_attempt_can_recover_an_invalid_response():
    instance = service()
    with patch("marketing_service.generate_ai", side_effect=[
        {"response": "not json", "provider": "test", "model": "test"},
        {"response": ai_payload(), "provider": "test", "model": "test", "used_fallback": False},
    ]) as ai:
        result = instance.opportunities()
    assert ai.call_count == 2
    assert [attempt["status"] for attempt in result["ai_attempts"]] == ["rejected", "accepted"]
    assert result["opportunities"][0]["campaign_origin"] == "ai"
    second_prompt = json.loads(ai.call_args_list[1].args[0])
    assert "retry_instruction" in second_prompt
    assert second_prompt["candidates"][0]["product_id"] == 1


def test_two_rejections_stop_at_template_and_keep_reasons():
    instance = service()
    with patch("marketing_service.generate_ai", return_value={"response": "invalid"}) as ai:
        result = instance.opportunities()
    assert ai.call_count == 2
    assert len(result["ai_attempts"]) == 2
    assert all(attempt["status"] == "rejected" for attempt in result["ai_attempts"])
    assert result["opportunities"][0]["campaign_origin"] == "template"
    assert result["ai"] is None


def test_provider_error_is_identified_without_an_extra_marketing_retry():
    instance = service()
    with patch("marketing_service.generate_ai", side_effect=AIProviderError("offline", provider="openai", retryable=True)) as ai:
        result = instance.opportunities()
    assert ai.call_count == 1
    assert result["ai_attempts"] == [{"attempt": 1, "status": "provider_error", "provider": "openai", "retryable": True}]


def test_first_valid_response_does_not_trigger_a_second_request():
    instance = service()
    with patch("marketing_service.generate_ai", return_value={"response": ai_payload(), "provider": "test"}) as ai:
        result = instance.opportunities()
    ai.assert_called_once()
    assert result["ai_attempts"] == [{"attempt": 1, "status": "accepted"}]


def test_request_limits_and_country_are_validated():
    from DataBaseManagement.schemasAgents import MarketingOpportunitiesRequest
    from pydantic import ValidationError
    assert MarketingOpportunitiesRequest().limit == 3
    for payload in [{"limit": 4}, {"limit": 0}, {"country": "123"}, {"country": "ÑÑ"}]:
        with pytest.raises(ValidationError):
            MarketingOpportunitiesRequest(**payload)


def test_uses_completed_utc_days_and_one_shared_as_of():
    instance = service([])
    with patch("marketing_service.datetime") as clock:
        clock.now.return_value = datetime(2026, 10, 19, 14, 30, tzinfo=timezone.utc)
        result = instance.opportunities()
    assert instance.commercial._all.call_args.args[1] == (datetime(2026, 10, 19, tzinfo=timezone.utc),)
    assert result["selection"]["recent_start"] == "2026-09-19"
    assert result["selection"]["previous_start"] == "2026-08-20"
    assert result["selection"]["end_exclusive"] == "2026-10-19"


@pytest.mark.parametrize("question", ["Propón una campaña de marketing", "Busca productos para promocionar", "Sugiere una promoción para productos en tendencia"])
def test_executive_routes_marketing_before_generic_sales_or_trends(question):
    instance = ExecutiveService(None)
    instance.marketing = Mock()
    instance.marketing.opportunities.return_value = {"agent": "marketing", "explanation": "Propuestas"}
    instance._record_decision = Mock(return_value=1)
    result = instance.execute(question)
    assert result["routed_agent"] == "marketing"
    instance.marketing.opportunities.assert_called_once_with()


def test_marketing_reuses_trend_data_without_an_extra_ai_analysis():
    from commercial_agent_service import CommercialAgentService
    from external_connectors import SourceStatus
    raw = {"interest_over_time": {"timeline_data": [
        {"timestamp": 1700000000 + i * 604800, "date": f"Semana {i}",
         "values": [{"query": "Producto 1", "extracted_value": 50}]} for i in range(8)]}}
    connector = Mock()
    connector.status.return_value = SourceStatus("serpapi", True, "read_only", "Test")
    connector.trends.return_value = raw
    connector.related_queries.return_value = {}
    commercial = CommercialAgentService(None)
    commercial._cache = Mock()
    with patch("commercial_agent_service.get_connectors", return_value={"serpapi": connector}), patch("commercial_agent_service.generate_ai") as ai:
        result = commercial.market_intelligence("Producto 1", include_ai=False)
    assert result["status"] == "ok"
    assert result["summary"]["status"] == "descriptive_comparison"
    ai.assert_not_called()


def test_more_than_three_inputs_never_trigger_more_than_three_market_queries():
    instance = service([candidate(i, recent=30+i) for i in range(1, 8)])
    with patch("marketing_service.generate_ai", side_effect=AIProviderError("offline", provider="test", retryable=False)):
        result = instance.opportunities()
    assert len(result["opportunities"]) == 3
    assert instance.commercial.market_intelligence.call_count == 3
