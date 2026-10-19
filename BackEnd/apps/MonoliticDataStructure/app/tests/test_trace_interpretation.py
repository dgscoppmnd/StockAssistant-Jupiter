import json
import threading
from concurrent.futures import ThreadPoolExecutor
import unittest
from unittest.mock import Mock, patch

from ai_service import AIProviderError
import trace_interpretation as traces
from trace_presentation import presentation_catalog, validate_note


class TraceInterpretationTests(unittest.TestCase):
    def setUp(self):
        traces._cache.clear()
        self.run = {'id':1,'rule_name':'Reposición','rule_code':'stock_reorder_proposals',
                    'rule_version':1,'status':'completed','result':{'ai':None,'proposals':[]},
                    'config_snapshot':{'allow_unmetered_paid_ai':True}}
        self.events = [{'id':1,'phase':'decision','detail':{'choices':[],'reason':'Faltan datos'}}]
        self.answer = {'response':json.dumps({'summary':'La regla terminó sin propuestas porque faltan datos verificables.',
                                             'next_step':'','metric_ids':['proposals_total'],'chart_id':''}),
                       'provider':'openai','model':'test-model','used_fallback':True}

    def test_completed_trace_is_explained_once_and_cached_without_modifying_evidence(self):
        before = json.dumps([self.run,self.events])
        with patch('trace_interpretation.generate_ai',return_value=self.answer) as generate:
            result = traces.interpret_trace(self.run,self.events,[])
            again = traces.interpret_trace(self.run,self.events,[])
        self.assertEqual(result,again)
        self.assertEqual(result['source'],'ai')
        self.assertEqual(result['ai']['model'],'test-model')
        self.assertTrue(result['ai']['used_fallback'])
        generate.assert_called_once()
        self.assertEqual(json.dumps([self.run,self.events]),before)
        self.assertIn('no instrucciones',generate.call_args.args[1])
        self.assertTrue(generate.call_args.kwargs['allow_paid'])
        self.assertEqual(result['metrics'],[{'label':'Propuestas registradas','value':'0','unit':'propuestas'}])
        self.assertEqual(generate.call_args.kwargs['response_schema']['additionalProperties'],False)

    def test_new_events_or_proposal_state_invalidate_explanation(self):
        with patch('trace_interpretation.generate_ai',return_value=self.answer) as generate:
            first = traces.interpret_trace(self.run,self.events,[])
            second = traces.interpret_trace(self.run,self.events,[{'id':1,'status':'pending_approval'}])
            third = traces.interpret_trace(self.run,self.events,[{'id':1,'status':'approved'}])
        self.assertEqual(generate.call_count,3)
        self.assertEqual(len({r['revision'] for r in (first,second,third)}),3)

    def test_running_trace_never_calls_model(self):
        with patch('trace_interpretation.generate_ai') as generate:
            result = traces.interpret_trace({**self.run,'status':'running'},[],[])
        generate.assert_not_called()
        self.assertEqual(result['source'],'pending')

    def test_unavailable_provider_respects_paid_policy_and_returns_honest_fallback(self):
        run = {**self.run,'status':'degraded','result':{'degraded_reason':'Cannot connect to Ollama'},'config_snapshot':{}}
        with patch('trace_interpretation.generate_ai',side_effect=AIProviderError('Cannot connect to Ollama',provider='ollama',retryable=True)) as generate:
            result = traces.interpret_trace(run,self.events,[])
        self.assertFalse(generate.call_args.kwargs['allow_paid'])
        self.assertEqual(result['source'],'fallback')
        self.assertIsNone(result['ai'])
        self.assertIn('no autoriza IA de pago',result['warning'])
        self.assertIn('Cannot connect to Ollama',result['explanation'])

    def test_explicit_retry_bypasses_failed_cache_but_keeps_successful_cache(self):
        with patch('trace_interpretation.generate_ai',return_value={'response':''}) as generate:
            self.assertEqual(traces.interpret_trace(self.run,self.events,[])['source'],'fallback')
            traces.interpret_trace(self.run,self.events,[])
            self.assertEqual(generate.call_count,1)
            generate.return_value=self.answer
            result = traces.interpret_trace(self.run,self.events,[],retry=True)
            traces.interpret_trace(self.run,self.events,[],retry=True)
        self.assertEqual(result['source'],'ai')
        self.assertEqual(generate.call_count,2)

    def test_context_is_valid_bounded_json_and_declares_omissions(self):
        events = [{'phase':'decision','detail':{'reason':'X'*5000}} for _ in range(100)]
        context = traces._context(self.run,events,[])
        self.assertLessEqual(len(context),24000)
        self.assertGreater(json.loads(context)['omitted_events'],0)
        self.assertIn('Texto resumido',context)

    def test_concurrent_requests_share_one_model_call(self):
        started,release = threading.Event(),threading.Event()
        def answer(*args,**kwargs):
            started.set()
            self.assertTrue(release.wait(5))
            return self.answer
        with patch('trace_interpretation.generate_ai',side_effect=answer) as generate:
            with ThreadPoolExecutor(max_workers=2) as pool:
                first = pool.submit(traces.interpret_trace,self.run,self.events,[])
                self.assertTrue(started.wait(5))
                second = pool.submit(traces.interpret_trace,self.run,self.events,[])
                release.set()
                self.assertEqual(first.result(),second.result())
        generate.assert_called_once()

    def test_api_requires_read_permission(self):
        from endpoints.endpointsAutomation import interpretation
        from fastapi import HTTPException
        service = Mock(user={'automation_permissions':[]})
        with self.assertRaises(HTTPException) as denied:
            interpretation(1,service)
        self.assertEqual(denied.exception.status_code,403)
        service.interpret_trace.assert_not_called()
        service.user['automation_permissions']=['read']
        interpretation(1,service)
        service.interpret_trace.assert_called_once_with(1,False)

    def test_chart_and_values_are_selected_from_recorded_data_not_generated_numbers(self):
        proposals = [{'status':'pending_approval'},{'status':'approved'},{'status':'pending_approval'}]
        metrics,charts = presentation_catalog(self.run,self.events,proposals)
        note = json.dumps({'summary':'Hay propuestas pendientes de aprobación.','next_step':'Revisa las propuestas.',
                           'metric_ids':['proposals_total','proposals_pending_approval'],'chart_id':'proposal_states'})
        with patch('trace_interpretation.generate_ai',return_value={**self.answer,'response':note}):
            result = traces.interpret_trace(self.run,self.events,proposals)
        self.assertEqual(result['metrics'][0]['value'],'3')
        self.assertEqual(result['metrics'][1]['value'],'2')
        self.assertEqual(result['chart']['points'],[{'label':'Pendientes de aprobación','value':'2'},
                                                  {'label':'Aprobadas','value':'1'}])
        for change in [{'metric_ids':['invented_profit']},{'chart_id':'invented_sales_trend'},
                       {'metric_ids':['proposals_total','proposals_total']},{'values':[1000]}]:
            with self.assertRaises(ValueError):
                validate_note(json.dumps({**json.loads(note),**change}),metrics,charts)

    def test_stock_chart_never_mixes_units_or_invents_missing_values(self):
        events = [{'phase':'analysis','detail':{'scenarios':[
            {'product_id':1,'warehouse_id':1,'unit':'kg','values':{'available':'-2','pending':'5'}},
            {'product_id':2,'warehouse_id':1,'unit':'unit','values':{'available':'3','pending':'0'}},
            {'product_id':3,'warehouse_id':1,'unit':'kg','values':{'available':None,'pending':'5'}}]}}]
        metrics,charts = presentation_catalog(self.run,events,[])
        self.assertNotIn('entities_analyzed',metrics)
        self.assertEqual(metrics['eligible_entities']['value'],'3')
        self.assertEqual(charts['stock_0']['unit'],'kg')
        self.assertEqual(charts['stock_0']['points'][0]['value'],'-2')
        self.assertEqual(charts['stock_1']['unit'],'unit')
        self.assertNotIn('stock_2',charts)

    def test_no_chart_is_offered_for_single_or_all_zero_values(self):
        run = {**self.run,'result':{'report':{'movements_24h':4}}}
        metrics,charts = presentation_catalog(run,[],[])
        self.assertEqual(metrics['movements_24h']['value'],'4')
        self.assertEqual(charts,{})
        events = [{'phase':'analysis','detail':{'scenarios':[
            {'product_id':1,'warehouse_id':1,'unit':'kg','values':{'available':0,'pending':0}}]}}]
        self.assertEqual(presentation_catalog(run,events,[])[1],{})

    def test_verbose_or_invalid_output_falls_back_to_source_values(self):
        for payload in ['{"summary":"incompleto"}',json.dumps({'summary':'palabra '*61,'next_step':'',
                          'metric_ids':[],'chart_id':''}),json.dumps({'summary':'Resultado.',
                          'next_step':'palabra '*26,'metric_ids':[],'chart_id':''})]:
            traces._cache.clear()
            with patch('trace_interpretation.generate_ai',return_value={**self.answer,'response':payload}):
                result = traces.interpret_trace(self.run,self.events,[])
            self.assertEqual(result['source'],'fallback')
            self.assertEqual(result['metrics'][0]['value'],'0')
            self.assertIsNone(result['chart'])

    def test_no_eligible_scenarios_is_not_presented_as_no_products_or_warehouses(self):
        events=[{'phase':'analysis','detail':{'rows_examined':8,'scenarios':[],
                 'product_ids':[1,2],'warehouse_ids':[1]}}]
        context=json.loads(traces._context(self.run,events,[]))
        detail=context['events'][0]['detail']
        self.assertEqual(detail['rows_examined'],8)
        self.assertEqual(detail['eligible_entities'],0)
        metrics,_=presentation_catalog(self.run,events,[])
        self.assertEqual(metrics['entities_analyzed']['value'],'8')
        self.assertEqual(metrics['eligible_entities']['value'],'0')
        legacy=json.loads(traces._context(self.run,[{'phase':'analysis','detail':{'scenarios':[]}}],[]))
        self.assertIsNone(legacy['events'][0]['detail']['rows_examined'])


if __name__=='__main__':
    unittest.main(verbosity=2)
