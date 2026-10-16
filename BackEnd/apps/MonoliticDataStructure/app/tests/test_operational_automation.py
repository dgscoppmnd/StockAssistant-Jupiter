"""Offline IA doubles; optional PostgreSQL tests create an isolated temporary DB.

RUN_AUTOMATION_DB_TESTS=1 enables the database suite. No business database is
modified. Uses unittest so it runs in the production container without pytest.
"""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from decimal import Decimal
import json
import os
from pathlib import Path
import unittest
from unittest.mock import patch
from uuid import uuid4
import psycopg2
from psycopg2 import sql

from automation_contracts import (RuleConfig, RuleDraft, ModelTurn, Conditions, Quote, PhysicalReceipt, replenishment, forecast_metrics)
from automation_service import AutomationService
from ai_service import AIProviderError


def sample(**kwargs):
    return dict(product_id=1, warehouse_id=1, physical_qty=Decimal(5), reserved_qty=Decimal(2), pending=Decimal(3),
                reorder_point=Decimal(10), reorder_quantity=Decimal(20), sold_90=Decimal(90), sales_days=10,
                last_sale=datetime.now(timezone.utc)-timedelta(days=1), historical_cost=None, unit='unit',
                **kwargs)


class ContractTests(unittest.TestCase):
    def test_reorder_accounts_for_reservations_pending_and_multiples(self):
        qty = replenishment(sample(), RuleConfig(target_days=30, minimum_order=10, order_multiple=5))
        self.assertEqual(qty, Decimal(25))

    def test_no_demand_anywhere_offers_wait_no_speculative_transfer(self):
        row = sample(); row.update(sold_90=0,last_sale=None)
        result = AutomationService.compare(row, [row], RuleConfig(kind='stagnant_stock'))
        self.assertTrue(result['relevant'])
        self.assertIsNone(result['coverage_days'])
        self.assertNotIn('transfer', [a['action'] for a in result['alternatives']])
        self.assertIsNone(next(a for a in result['alternatives'] if a['action']=='promotion')['minimum_price_reference'])

    def test_transfer_preserves_origin_coverage_and_requires_destination_dispatches(self):
        low = sample(); high = sample(); high.update(warehouse_id=2,physical_qty=100,reserved_qty=5)
        plan = AutomationService.compare(low,[low,high],RuleConfig())
        transfer = next(a for a in plan['alternatives'] if a['action']=='transfer')
        self.assertEqual(transfer['source_warehouse_id'],2)
        self.assertEqual(Decimal(transfer['quantity']),Decimal(24))
        self.assertFalse(transfer['executable'])

    def test_unknown_tool_and_invalid_model_entities_are_rejected(self):
        for payload in [dict(tools=[dict(name='sql',product_id=1,warehouse_id=1)]),
                        dict(choices=[dict(product_id=-1,warehouse_id=1,action='wait',reason='dato')]),
                        dict(choices=[dict(product_id='1',warehouse_id=1,action='wait',reason='dato')])]:
            with self.assertRaises(ValueError):
                ModelTurn.model_validate(dict(finish_reason='terminado',**payload))

    def test_server_permissions_cannot_be_replaced_by_ui_state(self):
        from endpoints.endpointsAutomation import permit
        from fastapi import HTTPException
        service = AutomationService(None); service.user = {'automation_permissions':['read']}
        permit(service,'read')
        for permission in ['edit','activate','approve','execute','authorize']:
            with self.assertRaises(HTTPException) as raised: permit(service,permission)
            self.assertEqual(raised.exception.status_code,403)

    def test_permissions_budgets_and_contradictions(self):
        for config in [dict(per_action_budget=10,daily_budget=1),dict(mode='assisted',allowed_actions=['replenish']),
                       dict(mode='limited_auto',allowed_actions=['transfer']),dict(order_multiple=0),dict(product_ids=[-1]),
                       dict(timezone='No/SuchZone'),dict(order_multiple='0.00001')]:
            with self.assertRaises(ValueError): RuleConfig(**config)
        with self.assertRaises(ValueError):
            Conditions(items=[dict(field='available',operator='gt',value=10),dict(field='available',operator='lte',value=10)])

    def test_zero_denominator_and_insufficient_evidence(self):
        self.assertIsNone(forecast_metrics([])['mae'])
        self.assertIsNone(forecast_metrics([(1,0)])['wape'])
        result = forecast_metrics([(2,1),(1,2)])
        self.assertEqual(result['mae'],1)
        self.assertEqual(result['bias'],0)

    def test_model_can_select_or_decline_actions_and_query_tools(self):
        service = AutomationService(None)
        row = sample()
        scenario = service.compare(row,[row],RuleConfig())
        responses = [dict(response=json.dumps(dict(tools=[dict(name='product_snapshot',product_id=1,warehouse_id=1)],finish_reason='Consultar historial'))),
                     dict(response=json.dumps(dict(choices=[dict(product_id=1,warehouse_id=1,action='wait',reason='Historial incompleto')],finish_reason='Sin valor suficiente')))]
        events = []
        with patch('automation_service.generate_ai',side_effect=responses):
            choices,_ = service.choose([scenario],RuleConfig(),lambda p,d: events.append(p))
        self.assertEqual(choices[0].action,'wait')
        self.assertIn('tools',events)


@unittest.skipUnless(os.getenv('RUN_AUTOMATION_DB_TESTS')=='1','Requires isolated PostgreSQL test database')
class DatabaseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dbname = 'automation_test_' + uuid4().hex[:12]
        cls.params = dict(host=os.getenv('POSTGRES_HOST','postgres'),port=os.getenv('POSTGRES_PORT','5432'),
                          user=os.getenv('POSTGRES_USER_NAME','admin'),password=os.getenv('POSTGRES_PASSWORD_VALUE','admin123'))
        cls.admin = psycopg2.connect(dbname='postgres',**cls.params); cls.admin.autocommit=True
        with cls.admin.cursor() as c: c.execute(sql.SQL('CREATE DATABASE {}').format(sql.Identifier(cls.dbname)))
        try:
            c = cls.connect()
            with c.cursor() as q:
                q.execute(Path(os.getenv('TEST_INIT_SQL','/app/docker/init-scripts/init.sql')).read_text(encoding='utf-8'))
            c.commit();c.close()
        except Exception:
            cls.tearDownClass();raise

    @classmethod
    def connect(cls):
        return psycopg2.connect(dbname=cls.dbname,**cls.params)

    @classmethod
    def tearDownClass(cls):
        # This name is generated here and cannot refer to a business database.
        assert cls.dbname.startswith('automation_test_') and len(cls.dbname)==28
        with cls.admin.cursor() as c: c.execute(sql.SQL('DROP DATABASE {} WITH (FORCE)').format(sql.Identifier(cls.dbname)))
        cls.admin.close()

    def setUp(self):
        self.c = self.connect(); self.s = AutomationService(self.c)
        with self.c.cursor() as c:
            c.execute('TRUNCATE public.productos,public.automation_rules,public.inventory_warehouses RESTART IDENTITY CASCADE')
            c.execute("UPDATE public.automation_control SET stopped=FALSE")
            c.execute("INSERT INTO public.productos(name_product) VALUES('Producto de prueba') RETURNING pk_product"); self.pid=c.fetchone()[0]
            c.execute("INSERT INTO public.inventory_warehouses(code,name) VALUES('A','Origen'),('B','Destino')")
            c.execute("INSERT INTO public.product_inventory_config(product_id,base_unit_id,reorder_point,reorder_quantity) SELECT %s,id,10,20 FROM public.inventory_units WHERE code='unit'",(self.pid,))
            c.execute("INSERT INTO public.inventory_stock_levels(product_id,warehouse_id,physical_qty,reserved_qty) VALUES(%s,1,5,2),(%s,2,100,5)",(self.pid,self.pid))
        self.c.commit()
        self.s.ensure_default_rules()
        self.rid = self.s._one("SELECT id FROM public.automation_rules WHERE code='stock_reorder_proposals'")['id']
        self.config = RuleConfig(per_action_budget=1000,daily_budget=2000)
        self.s.save_rule(RuleDraft(name='Regla prueba',reason='Prueba aislada',config=self.config), 'tester',self.rid,True)

    def tearDown(self):
        self.c.close()

    def ai(self,action='replenish'):
        return patch('automation_service.generate_ai',return_value=dict(response=json.dumps(dict(
            choices=[dict(product_id=self.pid,warehouse_id=1,action=action,reason='Comparación de alternativas verificadas')],finish_reason='Proponer acción')),
            provider='double',model='test',used_fallback=False))

    def propose(self):
        with self.ai(): self.s.run_rule(self.rid)
        return self.s.action_proposals()[0]

    def test_simulation_has_no_persistent_or_inventory_effects(self):
        before = self.s._all('SELECT * FROM public.inventory_stock_levels ORDER BY id')
        result = self.s.simulate(self.config)
        self.assertTrue(result['simulation'])
        self.assertEqual(before,self.s._all('SELECT * FROM public.inventory_stock_levels ORDER BY id'))
        self.assertEqual(self.s.action_proposals(),[])
        self.assertEqual(self.s.runs(),[])

    def test_two_process_claims_only_one_run(self):
        def claim():
            conn=self.connect()
            try: return bool(AutomationService(conn).claim(self.rid,'manual'))
            finally: conn.close()
        self.c.commit()
        with ThreadPoolExecutor(max_workers=2) as pool: results=list(pool.map(lambda _:claim(),range(2)))
        self.assertEqual(sum(results),1)
        self.assertEqual(len(self.s.runs()),1)

    def test_model_failure_preserves_deterministic_evidence_without_actions(self):
        with patch('automation_service.generate_ai',side_effect=AIProviderError('offline',provider='double',retryable=True)):
            result=self.s.run_rule(self.rid)
        self.assertEqual(result['status'],'degraded')
        self.assertIn('analysis',[e['phase'] for e in self.s.trace(result['run_id'])])
        self.assertFalse(self.s.action_proposals())

    def test_invalid_ai_response_is_degraded(self):
        with patch('automation_service.generate_ai',return_value={'response':'{"choices": [{"action":"hack"}]}'}):
            result=self.s.run_rule(self.rid)
        self.assertEqual(result['status'],'degraded')
        self.assertIn('schema_rejected',[e['phase'] for e in self.s.trace(result['run_id'])])

    def test_duplicate_proposal_unique_and_changed_rule_invalidates(self):
        p=self.propose()
        with self.ai(): self.s.run_rule(self.rid)
        self.assertEqual(len(self.s.action_proposals()),1)
        self.s.save_rule(RuleDraft(name='Regla nueva',reason='Cambiar umbral',expected_version=1,config=self.config),'tester',self.rid,True)
        self.assertEqual(self.s.action_proposals()[0]['status'],'obsolete')
        with self.assertRaises(ValueError): self.s.decide(p['id'],True,'Aprobación vieja','tester')

    def test_stale_approval_and_kill_switch(self):
        p=self.propose()
        self.s._write('UPDATE public.inventory_stock_levels SET reserved_qty=3 WHERE product_id=%s AND warehouse_id=1',(self.pid,));self.c.commit()
        with self.assertRaises(ValueError): self.s.decide(p['id'],True,'Datos cambiados','tester')
        self.s.stop(True,'tester')
        self.assertEqual(self.s.run_rule(self.rid)['status'],'skipped')

    def test_e2e_purchase_receipt_separated_and_idempotent_evaluation(self):
        before=self.s._all('SELECT physical_qty FROM public.inventory_stock_levels ORDER BY id')
        simulation=self.s.simulate(self.config)
        self.assertTrue(simulation['scenarios'])
        self.s.set_rule_active(self.rid,True,'operator')
        p=self.propose();self.s.decide(p['id'],True,'Oferta confirmada','approver')
        with self.assertRaises(ValueError): self.s.act(p['id'],'operator')
        supplier=self.s._one("INSERT INTO public.inventory_suppliers(name) VALUES(%s) ON CONFLICT(name) DO UPDATE SET name=EXCLUDED.name RETURNING id",('Proveedor test',));self.c.commit()
        quote=Quote(supplier_id=supplier['id'],unit_price=2,reference='Oferta vigente test',valid_until=datetime.now(timezone.utc)+timedelta(days=1))
        result=self.s.act(p['id'],'operator',quote=quote)
        self.assertFalse(result['physical_receipt'])
        self.assertEqual(result,self.s.act(p['id'],'operator',quote=quote))
        self.assertEqual(before,self.s._all('SELECT physical_qty FROM public.inventory_stock_levels ORDER BY id'))
        self.assertEqual(self.s._one('SELECT COUNT(*) AS n FROM public.purchase_orders')['n'],1)
        from automation_purchasing import receive_purchase
        receipt=PhysicalReceipt(operation_key='test-partial-receipt',physical_confirmed=True,quantity=1,reason='Recepción física test')
        receive_purchase(self.s,p['id'],receipt,'warehouse')
        self.assertEqual(receive_purchase(self.s,p['id'],receipt,'warehouse')['status'],'already_confirmed')
        self.assertEqual(self.s._one('SELECT COUNT(*) AS n FROM public.goods_receipts')['n'],1)
        self.assertEqual(self.s._one('SELECT COUNT(*) AS n FROM public.purchase_orders')['n'],1)
        self.assertEqual(self.s.action_proposals()[0]['purchase_pending_qty'],Decimal(p['plan']['action']['quantity'])-1)
        self.s._write("UPDATE public.agent_action_proposals SET review_at=now()-INTERVAL '1 second',updated_at=now()-INTERVAL '1 day' WHERE id=%s",(p['id'],));self.c.commit()
        self.assertEqual(self.s.evaluate_due(),1);self.assertEqual(self.s.evaluate_due(),0)
        self.assertIsNone(self.s.action_proposals()[0]['evaluation']['objective_met'])
        self.assertEqual(self.s.metrics()['executions'],1)
        self.assertEqual(self.s.metrics(self.rid,30,1,'test')['executions'],1)
        self.assertEqual(self.s.metrics(self.rid,30,1,'different-model')['executions'],0)
        phases=[e['phase'] for e in self.s.trace(p['run_id'])]
        for phase in ('analysis','decision','proposal','approval','execution','physical_receipt','evaluation'):
            self.assertIn(phase,phases)

    def test_no_database_transaction_is_held_during_model_call(self):
        from psycopg2.extensions import TRANSACTION_STATUS_IDLE
        checked=[]
        def respond(*args,**kwargs):
            checked.append(self.c.get_transaction_status())
            return {'response':json.dumps({'choices':[],'finish_reason':'Sin acción útil'})}
        with patch('automation_service.generate_ai',side_effect=respond): self.s.run_rule(self.rid)
        self.assertEqual(checked,[TRANSACTION_STATUS_IDLE])
        self.assertFalse(self.s.action_proposals())

    def test_observation_cannot_create_or_execute_actions(self):
        config=self.config.model_copy(update={'mode':'observation'})
        self.s.save_rule(RuleDraft(name='Observar',reason='Solo observar',expected_version=1,config=config),'tester',self.rid,True)
        with self.ai(): result=self.s.run_rule(self.rid)
        self.assertEqual(result['status'],'completed')
        self.assertFalse(self.s.action_proposals())
        self.assertEqual(self.s._one('SELECT COUNT(*) AS n FROM public.purchase_orders')['n'],0)

    def test_explicit_objective_evaluated_without_claiming_decision_reliability(self):
        config=self.config.model_copy(update={'kind':'stagnant_stock','objective_target':Decimal(1)})
        self.s.save_rule(RuleDraft(name='Objetivo medible',reason='Evaluar despachos',expected_version=1,config=config),'tester',self.rid,True)
        with self.ai('suspend_reorder'): self.s.run_rule(self.rid)
        p=self.s.action_proposals()[0]
        self.s.decide(p['id'],True,'Autorizar supresión','approver');self.s.act(p['id'],'operator')
        self.s._write("UPDATE public.agent_action_proposals SET review_at=now()-INTERVAL '1 second',updated_at=now()-INTERVAL '1 day' WHERE id=%s",(p['id'],));self.c.commit()
        self.s.evaluate_due()
        metrics=self.s.metrics()
        self.assertEqual(metrics['objective_evaluable'],1)
        self.assertEqual(metrics['objective_success_rate'],0)
        self.assertEqual(metrics['reliability'],'Evidencia insuficiente')

    def test_budget_block_leaves_no_order(self):
        p=self.propose();self.s.decide(p['id'],True,'Aprobar propuesta','approver')
        supplier=self.s._one("INSERT INTO public.inventory_suppliers(name) VALUES('Proveedor caro') RETURNING id");self.c.commit()
        quote=Quote(supplier_id=supplier['id'],unit_price=10000,reference='Oferta cara',valid_until=datetime.now(timezone.utc)+timedelta(days=1))
        with self.assertRaises(ValueError): self.s.act(p['id'],'operator',quote=quote)
        self.assertEqual(self.s._one('SELECT COUNT(*) AS n FROM public.purchase_orders')['n'],0)

    def test_scheduler_one_failed_rule_does_not_stop_others(self):
        self.s._write('UPDATE public.automation_rules SET is_active=TRUE');self.c.commit()
        calls=[]
        def run(rule_id,actor):
            calls.append(rule_id)
            if rule_id==self.rid: raise ValueError('Regla fallida')
            return {'status':'completed'}
        with patch.object(self.s,'run_rule',side_effect=run), self.assertLogs('automation_service',level='ERROR'):
            self.s.run_due_rules()
        self.assertEqual(len(calls),4)

    def test_unknown_rule_and_abandoned_lease_recovery(self):
        bad=self.s._one("INSERT INTO public.automation_rules(code,name,description) VALUES('unknown','Desconocida','test') RETURNING id")
        self.c.commit()
        with self.assertRaises(ValueError): self.s.run_rule(bad['id'])
        first=self.s.claim(self.rid,'manual')
        self.s._write("UPDATE public.automation_rules SET lease_until=now()-INTERVAL '1 second' WHERE id=%s",(self.rid,));self.c.commit()
        second=self.s.claim(self.rid,'manual')
        self.assertNotEqual(first[3],second[3])
        self.assertEqual(self.s._one('SELECT status FROM public.automation_runs WHERE id=%s',(first[2]['id'],))['status'],'failed')

    def test_concurrent_edit_and_autonomy_authorization(self):
        draft=RuleDraft(name='Cambio',reason='Cambiar objetivo',expected_version=1,config=self.config)
        self.s.save_rule(draft,'tester',self.rid)
        with self.assertRaises(ValueError): self.s.save_rule(draft,'tester',self.rid)
        auto=self.config.model_copy(update={'mode':'limited_auto','allowed_actions':['suspend_reorder']})
        with self.assertRaises(PermissionError):
            self.s.save_rule(RuleDraft(name='Autonomía',reason='Solicitar ejecución',expected_version=2,config=auto),'tester',self.rid)

    def test_physical_transfer_requires_confirmation_conserves_stock_and_is_idempotent(self):
        # Give the destination one confirmed historical dispatch without creating a sales document.
        inventory = __import__('inventory_service').InventoryService(self.c)
        unit=self.s._one("SELECT id FROM public.inventory_units WHERE code='unit'")['id']
        inventory._insert_movement(movement_type='dispatch',product_id=self.pid,warehouse_id=1,warehouse_destination_id=None,
            quantity=Decimal(90),quantity_signed=Decimal(-90),base_unit_id=unit,document_type='test_baseline',document_id=1,
            document_line_id=None,operation_key='isolated-test-sale',reason='Baseline test',user_name='tester')
        self.c.commit()
        with self.ai('transfer'): self.s.run_rule(self.rid)
        p=self.s.action_proposals()[0]
        self.s.decide(p['id'],True,'Traslado preparado','approver')
        with self.assertRaises(ValueError): self.s.act(p['id'],'operator')
        before=self.s._one('SELECT SUM(physical_qty) AS total FROM public.inventory_stock_levels')['total']
        result=self.s.act(p['id'],'operator',physical_confirmed=True)
        self.assertEqual(result,self.s.act(p['id'],'operator',physical_confirmed=True))
        self.assertEqual(before,self.s._one('SELECT SUM(physical_qty) AS total FROM public.inventory_stock_levels')['total'])
        moves=self.s._all("SELECT quantity_signed FROM public.inventory_movements WHERE movement_type IN ('transfer_in','transfer_out')")
        self.assertEqual(len(moves),2);self.assertEqual(sum(m['quantity_signed'] for m in moves),0)


if __name__=='__main__': unittest.main(verbosity=2)
