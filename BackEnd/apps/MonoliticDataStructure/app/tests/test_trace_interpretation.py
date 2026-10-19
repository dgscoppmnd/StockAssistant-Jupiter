import json
import threading
from concurrent.futures import ThreadPoolExecutor
import unittest
from unittest.mock import Mock, patch

from ai_service import AIProviderError
import trace_interpretation as traces


class TraceInterpretationTests(unittest.TestCase):
    def setUp(self):
        traces._cache.clear()
        self.run = {'id':1,'rule_name':'Reposición','rule_code':'stock_reorder_proposals',
                    'rule_version':1,'status':'completed','result':{'ai':None,'proposals':[]},
                    'config_snapshot':{'allow_unmetered_paid_ai':True}}
        self.events = [{'id':1,'phase':'decision','detail':{'choices':[],'reason':'Faltan datos'}}]
        self.answer = {'response':'La regla terminó sin propuestas porque faltan datos verificables.',
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


if __name__=='__main__':
    unittest.main(verbosity=2)
