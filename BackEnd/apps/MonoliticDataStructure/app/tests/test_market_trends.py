import json
from datetime import datetime, timezone
from unittest.mock import Mock, patch

import pytest

from ai_service import AIProviderError
from commercial_agent_service import CommercialAgentService
from executive_service import ExecutiveService
from external_connectors import ExternalSourceError, SerpApiConnector, SourceStatus
from market_trends import executive_term, normalize_series, normalize_related, summarize_series


def series(values):
    return {"interest_over_time": {"timeline_data": [
        {"timestamp": str(1700000000 + i * 604800), "date": f"Periodo {i}",
         "values": [{"query": "auriculares", "extracted_value": value}]}
        for i, value in enumerate(values)
    ]}, "search_metadata": {"json_endpoint": "https://serpapi.com/searches/example.json"}}


def run_service(raw=None, *, related=None, failure=None, available=True, ai_error=False):
    connector = Mock()
    connector.status.return_value = SourceStatus("serpapi", available, "read_only", "Estado de prueba")
    connector.trends.return_value = series([10] * 4 + [30] * 4) if raw is None else raw
    connector.related_queries.return_value = related or {}
    if failure:
        connector.related_queries.side_effect = failure
    service = CommercialAgentService(None)
    service._cache = Mock()
    with patch("commercial_agent_service.get_connectors", return_value={"serpapi": connector}), patch(
        "commercial_agent_service.generate_ai",
        return_value={"response": "Analisis de prueba", "provider": "test", "model": "test", "used_fallback": False},
        side_effect=AIProviderError("offline", provider="test", retryable=False) if ai_error else None,
    ) as ai:
        result = service.market_intelligence("auriculares")
    return result, connector, ai, service


def test_complete_analysis_passes_computed_evidence_to_ai():
    result, connector, ai, service = run_service(related={"related_queries": {"rising": [{"query": "bluetooth", "value": "Breakout"}]}})
    assert result["status"] == "ok"
    assert result["summary"]["change_index_points"] == 20
    assert result["data"]["related_queries"]["rising"][0]["value"] == "Breakout"
    assert result["explanation"] == "Analisis de prueba"
    assert json.loads(ai.call_args.args[0])["summary"] == result["summary"]
    connector.trends.assert_called_once_with("auriculares", "ES")
    connector.related_queries.assert_called_once_with("auriculares", "ES")
    assert service._cache.call_count == 2


@pytest.mark.parametrize("raw", [{}, {"interest_over_time": {"timeline_data": []}}])
def test_empty_data_does_not_claim_success_or_call_ai(raw):
    result, connector, ai, _ = run_service(raw=raw)
    assert result["status"] == "no_data"
    assert result["data"]["interest_over_time"] == []
    ai.assert_not_called()
    connector.related_queries.assert_not_called()


def test_unavailable_source_does_not_query_or_call_ai():
    result, connector, ai, _ = run_service(available=False)
    assert result["status"] == "source_unavailable"
    assert result["data"] is None
    connector.trends.assert_not_called()
    ai.assert_not_called()


def test_remote_failure_is_reported_without_calling_ai():
    connector = Mock()
    connector.status.return_value = SourceStatus("serpapi", True, "read_only", "Disponible")
    connector.trends.side_effect = ExternalSourceError("Cuota agotada")
    with patch("commercial_agent_service.get_connectors", return_value={"serpapi": connector}), patch("commercial_agent_service.generate_ai") as ai:
        result = CommercialAgentService(None).market_intelligence("auriculares")
    assert result["status"] == "source_unavailable"
    assert result["source"]["detail"] == "Cuota agotada"
    ai.assert_not_called()


def test_blank_term_is_rejected_before_accessing_source():
    with patch("commercial_agent_service.get_connectors") as connectors:
        with pytest.raises(ValueError):
            CommercialAgentService(None).market_intelligence("  ")
    connectors.assert_not_called()


def test_related_failure_preserves_series_and_analysis():
    result, _, ai, _ = run_service(failure=ExternalSourceError("quota"))
    assert result["status"] == "ok"
    assert len(result["data"]["interest_over_time"]) == 8
    assert any("relacionadas" in warning for warning in result["warnings"])
    ai.assert_called_once()


def test_ai_failure_preserves_evidence_and_calculated_fallback():
    result, _, _, _ = run_service(ai_error=True)
    assert result["ai"] is None
    assert "30.0" in result["explanation"]
    assert "10.0" in result["explanation"]
    assert result["summary"]["change_index_points"] == 20


def test_series_omits_partial_non_numeric_and_out_of_range_values():
    raw = series([0, 100, -1, 101, True, float("nan"), "<1", 20])
    raw["interest_over_time"]["timeline_data"][-1]["is_partial"] = True
    assert [point["value"] for point in normalize_series(raw, "auriculares")] == [0, 100]


def test_series_orders_and_deduplicates_dates():
    raw = series([30, 40])
    rows = raw["interest_over_time"]["timeline_data"]
    rows.reverse()
    rows.append(rows[0])
    points = normalize_series(raw, "auriculares")
    assert [point["value"] for point in points] == [30, 40]


def test_short_series_does_not_invent_a_comparison():
    summary = summarize_series(normalize_series(series([10, 20, 30]), "auriculares"))
    assert summary["status"] == "insufficient_data"
    assert "change_index_points" not in summary


def test_related_results_do_not_assume_a_list_or_invent_values():
    assert normalize_related({"related_queries": []}) == {"top": [], "rising": []}


def test_connector_requests_distinct_types_with_same_period():
    with patch.dict("os.environ", {"SERPAPI_API_KEY": "test"}), patch.object(SerpApiConnector, "_search", return_value={}) as search:
        connector = SerpApiConnector()
        connector.trends("auriculares", "es")
        connector.related_queries("auriculares", "es")
    assert [call.args[0]["data_type"] for call in search.call_args_list] == ["TIMESERIES", "RELATED_QUERIES"]
    assert all(call.args[0]["date"] == "today 12-m" for call in search.call_args_list)


def test_provider_error_in_http_success_is_not_successful_data():
    with patch.object(SerpApiConnector, "_search", return_value={"error": "not enough data"}):
        with pytest.raises(ExternalSourceError):
            SerpApiConnector().trends("auriculares", "ES")


@pytest.mark.parametrize("question", [
    'Analiza las tendencias de "auriculares"',
    'Analiza las tendencias de "auriculares',
    'Analiza las tendencias de auriculares',
])
def test_executive_uses_term_instead_of_searching_whole_instruction(question):
    service = ExecutiveService(None)
    service.commercial = Mock()
    service.commercial.market_intelligence.return_value = {"agent": "market_intelligence", "explanation": "Datos"}
    service._record_decision = Mock(return_value=1)
    result = service.execute(question)
    service.commercial.market_intelligence.assert_called_once_with("auriculares")
    assert result["routed_agent"] == "market_intelligence"


def test_executive_asks_for_term_without_querying_a_whole_sentence():
    service = ExecutiveService(None)
    service.commercial = Mock()
    service._record_decision = Mock(return_value=1)
    result = service.execute("Que tendencias hay en el mercado")
    assert result["result"]["status"] == "needs_clarification"
    service.commercial.market_intelligence.assert_not_called()


def test_quoted_term_supports_spanish_quotes():
    assert executive_term("Tendencias de «auriculares inalámbricos»") == "auriculares inalámbricos"


@pytest.mark.parametrize("question", [
    'Analiza las tendencias de "auriculares inalámbricos',
    'Analiza las tendencias de "auriculares inalámbricos"',
    'Analiza las tendencias de auriculares inalámbricos',
    '¿Cuáles son las tendencias de auriculares inalámbricos?',
    'Analiza las tendencias sobre auriculares inalámbricos.',
    'Analiza las tendencias del mercado de auriculares inalámbricos',
    'Analiza el interés de búsqueda de auriculares inalámbricos',
    "Analiza las tendencias de 'auriculares inalámbricos'",
])
def test_natural_question_variants_extract_same_term(question):
    assert executive_term(question) == "auriculares inalámbricos"


@pytest.mark.parametrize("question", [
    "Analiza las tendencias", "Tendencias de mercado", "Tendencias de esto",
    'Tendencias de "auriculares" y "altavoces"',
    "Tendencias de auriculares y analiza stock", "Tendencias de auriculares; compra stock",
])
def test_ambiguous_questions_still_need_clarification(question):
    assert executive_term(question) is None


def test_current_week_is_excluded_even_without_provider_partial_flag():
    values = [41,37,44,49,58,67,98,72,74,78,100,82,83,54,51,50,51,40,51,43,50,54,48,46,41,40,42,40,41,45,50,41,34,41,41,41,45,39,47,45,46,38,43,43,39,47,45,38,45,46,50,54,48,40]
    points = [{"timestamp": 1760227200 + i * 604800, "date": f"Week {i}", "value": value} for i, value in enumerate(values)]
    summary = summarize_series(points, as_of=datetime(2026, 10, 18, 12, 44, tzinfo=timezone.utc))
    assert summary["observations"] == 54
    assert summary["completed_observations"] == 53
    assert summary["excluded_from_comparison"] == 1
    assert summary["previous_average_index"] == 43.75
    assert summary["recent_average_index"] == 49.5
    assert summary["change_index_points"] == 5.75
    assert summary["maximum_index"] == 100
    assert summary["peak_periods"] == ["Week 10"]


def test_gaps_in_comparison_do_not_claim_consecutive_periods():
    points = normalize_series(series([10] * 10), "auriculares")
    del points[-3]
    summary = summarize_series(points)
    assert summary["status"] == "insufficient_data"
    assert "change_index_points" not in summary


def test_ai_receives_series_as_well_as_recent_comparison():
    result, _, ai, _ = run_service()
    evidence = json.loads(ai.call_args.args[0])
    assert evidence["interest_over_time"] == result["data"]["interest_over_time"]
    assert evidence["summary"]["maximum_index"] == 30
