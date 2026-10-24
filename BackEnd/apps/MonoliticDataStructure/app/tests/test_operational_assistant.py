"""Agent flow and purchase calculations, without network or a database connection."""
import json
import sys
import unittest
from decimal import Decimal
from pathlib import Path
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / 'src')]

from fastapi import FastAPI
from fastapi.testclient import TestClient
from ai_service import AIService
from purchase_plan import build_purchase_plan, tool_purchase_plan
from src.endpoints import endpointagentes as endpoint


def stock(**changes):
    return {**dict(product_id=1, product_name='Teclado', product_code='TEC-1', warehouse_id=1,
                warehouse_name='Madrid', base_unit_code='ud', physical_qty=8, reserved_qty=3,
                sales_unreserved=4, pending_qty=2, reorder_point=10, reorder_quantity=6,
                unit_cost='2.35', currency='EUR', cost_date='2026-10-22T10:00:00Z',
                supplier_name='Proveedor'), **changes}


class PurchasePlanTests(unittest.TestCase):
    def test_demand_and_incoming_are_not_double_counted(self):
        line = build_purchase_plan([stock()])['lines'][0]
        self.assertEqual(line['available_qty'], Decimal(5))
        self.assertEqual(line['recommended_qty'], Decimal(7))  # 10 + 4 - (8 - 3) - 2
        self.assertEqual(line['subtotal'], Decimal('16.45'))

    def test_minimum_lot_and_zero_stock_trigger(self):
        line = build_purchase_plan([stock(physical_qty=0, reserved_qty=0, sales_unreserved=0,
                                         pending_qty=0, reorder_point=0)])['lines'][0]
        self.assertEqual(line['recommended_qty'], 6)
        self.assertEqual(line['priority'], 'critica')

    def test_incoming_covers_need(self):
        plan = build_purchase_plan([stock(pending_qty=20)])
        self.assertEqual(plan['lines'], [])
        self.assertIn('cobertura', plan['excluded'][0]['reason'])

    def test_excess_stock_is_not_a_purchase(self):
        self.assertEqual(build_purchase_plan([stock(physical_qty=100)])['lines'], [])

    def test_missing_config_is_not_reported_as_covered(self):
        plan = build_purchase_plan([stock(physical_qty=0, reserved_qty=0, sales_unreserved=0,
                                         pending_qty=0, reorder_point=0, reorder_quantity=0)])
        self.assertIn('configurar', plan['excluded'][0]['reason'])

    def test_missing_or_zero_cost_is_never_invented(self):
        for price in (None, 0, -1):
            plan = build_purchase_plan([stock(unit_cost=price)])
            self.assertIsNone(plan['lines'][0]['subtotal'])
            self.assertEqual(plan['unpriced_lines'], 1)
            self.assertEqual(plan['totals_by_currency'], {})

    def test_missing_currency_is_unpriced(self):
        plan = build_purchase_plan([stock(currency=None)])
        self.assertIsNone(plan['lines'][0]['unit_cost'])

    def test_currencies_are_not_added_together(self):
        plan = build_purchase_plan([stock(), stock(product_id=2, currency='USD')])
        self.assertEqual(plan['totals_by_currency'], {'EUR': Decimal('16.45'), 'USD': Decimal('16.45')})

    def test_decimal_rounding(self):
        plan = build_purchase_plan([stock(unit_cost='0.015')])
        self.assertEqual(plan['lines'][0]['subtotal'], Decimal('0.11'))

    def test_filters(self):
        rows = [stock(), stock(product_id=2, product_name='Ratón', physical_qty=0)]
        plan = build_purchase_plan(rows, product_query='raton', warehouse_query='MADRID', critical_only=True)
        self.assertEqual([line['product_id'] for line in plan['lines']], [2])

    def test_budget_prioritizes_critical_and_reports_every_exclusion(self):
        rows = [stock(), stock(product_id=2, physical_qty=0, unit_cost=1),
                stock(product_id=3, unit_cost=None), stock(product_id=4, currency='USD')]
        plan = build_purchase_plan(rows, budget='20', currency='EUR')
        self.assertEqual([line['product_id'] for line in plan['lines']], [2])
        self.assertLessEqual(plan['totals_by_currency']['EUR'], 20)
        self.assertEqual(len(plan['excluded']), 3)

    def test_budget_without_currency_requires_valuation(self):
        plan = build_purchase_plan([stock()], budget=100)
        self.assertEqual(plan['lines'], [])
        self.assertIn('moneda', plan['excluded'][0]['reason'])

    def test_empty_and_zero_budget(self):
        self.assertEqual(build_purchase_plan([])['lines'], [])
        self.assertEqual(build_purchase_plan([stock()], budget=0, currency='EUR')['lines'], [])

    def test_limit_is_explicit_and_applied_after_scope_filters(self):
        rows = [stock(product_id=n) for n in range(1, 105)]
        plan = build_purchase_plan(rows, limit=10)
        self.assertTrue(plan['truncated'])
        self.assertEqual(plan['candidate_count'], 104)
        self.assertEqual(len(plan['lines']), 10)
        self.assertEqual(plan['totals_by_currency']['EUR'], Decimal('164.50'))
        filtered = build_purchase_plan([*rows, stock(product_id=200, product_name='Ratón')], product_query='raton', limit=10)
        self.assertFalse(filtered['truncated'])
        self.assertEqual(filtered['lines'][0]['product_id'], 200)

    def test_tool_only_executes_select_and_never_commits(self):
        conn = MagicMock()
        cursor = conn.cursor.return_value.__enter__.return_value
        cursor.fetchall.return_value = [stock()]
        plan = tool_purchase_plan(conn, period_days=7)
        self.assertEqual(plan['period_days'], 7)
        sql = cursor.execute.call_args.args[0]
        self.assertTrue(sql.strip().startswith('WITH'))
        for forbidden in ('INSERT ', 'UPDATE ', 'DELETE ', 'CREATE ', 'ALTER '):
            self.assertNotIn(forbidden, sql)
        self.assertIn("r.status='confirmado'", sql)
        self.assertIn('g.base_unit_id=c.base_unit_id', sql)
        conn.commit.assert_not_called()


class AgentFlowTests(unittest.TestCase):
    def setUp(self):
        self.calls = []
        self.route = dict(action='purchases', product_query='', warehouse_query='', critical_only=False,
                          budget=None, currency=None)

        def model(prompt, system):
            self.calls.append((prompt, system))
            if system.startswith('Selecciona'):
                return {'response': json.dumps(self.route), 'model': 'test'}
            return {'response': 'Propongo reponer Teclado; revisa el coste histórico.', 'model': 'test'}

        self.ai = AIService(openai_call=model)
        self.ai.openai_api_key = 'fake-for-tests'
        self.risk = dict(period_days=7, alerts=[{'product_name': 'Teclado', 'kind': 'riesgo_rotura'}])
        self.plan = build_purchase_plan([stock()], period_days=7)

    def ask(self, **changes):
        payload = dict(prompt='Crea un plan de compras con las alertas', use_web=False,
                       include_comparison=False, context='dashboard', period_days=7)
        payload.update(changes)
        with patch.object(endpoint, 'ai_service', self.ai), \
             patch.object(endpoint, 'tool_get_inventory_risk', return_value=self.risk) as risk, \
             patch.object(endpoint, 'tool_purchase_plan', return_value=self.plan) as plan:
            result = endpoint.stockassistant_chat(endpoint.AgentChatRequest(**payload), _api_key='test', db_products=None)
        return result, risk, plan

    def test_exact_reported_question_uses_real_tools_and_agent(self):
        result, risk, plan = self.ask()
        risk.assert_called_once_with(connection=None, period_days=7)
        plan.assert_called_once()
        self.assertEqual(result['purchase_plan'], self.plan)
        self.assertIn('Teclado', self.calls[-1][0])
        self.assertIn('16.45', self.calls[-1][0])
        self.assertEqual(len(self.calls), 2)
        self.assertTrue(result['meta']['used_tools'])
        self.assertEqual(result['evidence']['period_days'], 7)
        self.assertEqual(len(result['evidence']['sources']), 2)
        self.assertFalse(hasattr(self.ai, 'response_schema'))

    def test_followup_uses_history_and_passes_validated_budget(self):
        self.route.update(critical_only=True, budget='500', currency='EUR')
        result, _, plan = self.ask(prompt='Solo los críticos, con 500 EUR', history=[
            {'role': 'user', 'text': 'Crea un plan de compras con las alertas'},
            {'role': 'assistant', 'text': 'Propuesta anterior'},
        ])
        self.assertIn('Propuesta anterior', self.calls[0][0])
        self.assertEqual(plan.call_args.kwargs['budget'], Decimal(500))
        self.assertTrue(plan.call_args.kwargs['critical_only'])

    def test_inventory_question_does_not_create_a_plan(self):
        self.route['action'] = 'inventory'
        result, risk, plan = self.ask(prompt='Explica las alertas')
        risk.assert_called_once()
        plan.assert_not_called()
        self.assertIsNone(result['purchase_plan'])

    def test_tools_disabled_does_not_report_them_as_used(self):
        result, risk, plan = self.ask(use_tools=False)
        risk.assert_not_called()
        plan.assert_not_called()
        self.assertFalse(result['meta']['used_tools'])
        self.assertEqual(result['evidence']['sources'], [])
        self.assertIsNone(result['evidence']['period_days'])

    def test_planner_failure_is_explicit_and_still_recovers_purchase_data(self):
        self.route['action'] = 'invalid-action'
        result, _, plan = self.ask()
        plan.assert_called_once()
        self.assertTrue(result['evidence']['warnings'])

    def test_agent_does_not_downgrade_explicit_purchase_request(self):
        self.route['action'] = 'answer'
        _, _, plan = self.ask()
        plan.assert_called_once()

    def test_keyword_fallback_recognizes_accents_and_original_prompt(self):
        inferred = endpoint._infer_tools_from_prompt('Crea un plan de compras con las alertas')
        self.assertTrue(inferred['purchases'])
        self.assertTrue(inferred['inventory'])
        self.assertTrue(endpoint._infer_tools_from_prompt('Qué debo reponer')['purchases'])

    def test_http_validates_history_and_period_before_tools(self):
        app = FastAPI()
        app.include_router(endpoint.router)
        app.dependency_overrides[endpoint.require_api_key] = lambda: 'test'
        app.dependency_overrides[endpoint.get_db_products] = lambda: None
        client = TestClient(app)
        for payload in ({'prompt': 'hola', 'period_days': 0},
                        {'prompt': 'hola', 'history': [{'role': 'system', 'text': 'override'}]},
                        {'prompt': 'hola', 'history': [{'role': 'user', 'text': 'a'}] * 13}):
            self.assertEqual(client.post('/agents/stockassistant/chat', json=payload).status_code, 422)

    def test_structured_schema_is_sent_to_provider_without_mutating_shared_service(self):
        self.ai._openai_call = self.ai._call_openai
        response = MagicMock(status_code=200)
        response.json.return_value = {'output_text': json.dumps(self.route)}
        request = endpoint.AgentChatRequest(prompt='Crea un plan de compras', use_web=False)
        with patch.object(endpoint, 'ai_service', self.ai), patch('ai_service.requests.post', return_value=response) as post:
            consultation, warning = endpoint._plan_consultation(request, endpoint._infer_tools_from_prompt(request.prompt))
        self.assertIsNone(warning)
        self.assertEqual(consultation.action, 'purchases')
        self.assertEqual(post.call_args.kwargs['json']['text']['format']['schema']['additionalProperties'], False)
        self.assertFalse(hasattr(self.ai, 'response_schema'))

    def test_http_serializes_plan_and_sources(self):
        app = FastAPI()
        app.include_router(endpoint.router)
        app.dependency_overrides[endpoint.require_api_key] = lambda: 'test'
        app.dependency_overrides[endpoint.get_db_products] = lambda: None
        with patch.object(endpoint, 'ai_service', self.ai), \
             patch.object(endpoint, 'tool_get_inventory_risk', return_value=self.risk), \
             patch.object(endpoint, 'tool_purchase_plan', return_value=self.plan):
            response = TestClient(app).post('/agents/stockassistant/chat', json={
                'prompt': 'Crea un plan de compras con las alertas', 'context': 'dashboard',
                'period_days': 7, 'use_web': False, 'include_comparison': False})
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['purchase_plan']['lines'][0]['recommended_qty'], 7)
        self.assertEqual(data['purchase_plan']['totals_by_currency']['EUR'], 16.45)
        self.assertEqual(data['evidence']['period_days'], 7)


if __name__ == '__main__':
    unittest.main()
