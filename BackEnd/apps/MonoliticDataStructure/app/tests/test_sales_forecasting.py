from datetime import date, timedelta, datetime, timezone
from decimal import Decimal
import unittest
from unittest.mock import patch

from sales_forecasting import forecasts, select_method, forecast_dispatches


class ForecastingTests(unittest.TestCase):
    def test_constant_and_zero(self):
        for qty in (0,3):
            self.assertTrue(all(value==qty*30 for value in forecasts([qty]*90,30).values()))

    def test_linear_known_future(self):
        result=forecasts(list(range(1,91)),30)
        self.assertEqual(result['linear_90'], sum(range(91,121)))

    def test_weekly_alignment(self):
        history=[Decimal(6 if i%7==5 else 4 if i%7==6 else 0) for i in range(240)]
        predicted=forecasts(history[-90:],30)['weekly_repeat']
        actual=sum(Decimal(6 if i%7==5 else 4 if i%7==6 else 0) for i in range(240,270))
        self.assertEqual(predicted,actual)
        self.assertEqual(select_method(history,30)[0],'weekly_repeat')

    def test_decline_never_negative(self):
        self.assertGreaterEqual(forecasts(list(range(90,0,-1)),90)['linear_90'],0)

    def test_invalid_data(self):
        for values in ([1]*89,[-1]*90,[Decimal('NaN')]*90):
            with self.assertRaises(ValueError): forecasts(values,30)

    def test_sparse_fallback(self):
        end=date(2026,10,14)
        result=forecast_dispatches([{'day':end-timedelta(days=1),'sold_qty':1}],end,30,Decimal(1)/3)
        self.assertEqual(result['forecast_qty'],Decimal(1)/3)
        self.assertEqual(result['forecast_method'],'mean_90_legacy')

    def test_cutoff_excludes_today_and_future(self):
        end=date(2026,10,14)
        rows=[{'day':end-timedelta(days=240-i),'sold_qty':Decimal(1+i//20)} for i in range(240)]
        before=forecast_dispatches(rows,end,30,0)
        after=forecast_dispatches(rows+[{'day':end,'sold_qty':99999},{'day':end+timedelta(days=1),'sold_qty':99999}],end,30,0)
        self.assertEqual(before,after)
        self.assertEqual(before['forecast_method'],'linear_90')
        self.assertEqual(before['forecast_validation']['candidate_scores']['linear_90']['windows'],5)

    def test_each_validation_prediction_sees_only_past(self):
        history=list(map(Decimal,range(1,241)))
        import sales_forecasting
        original=sales_forecasting.forecasts
        seen=[]
        def spy(past,horizon):
            seen.append(list(past))
            return original(past,horizon)
        with patch.object(sales_forecasting,'forecasts',side_effect=spy):
            select_method(history,30)
        for past,origin in zip(seen,range(90,211,30)):
            self.assertEqual(past,history[origin-90:origin])
            self.assertEqual(max(past),history[origin-1])

    def test_large_horizon_preserves_fallback(self):
        end=date(2026,10,14)
        rows=[{'day':end-timedelta(days=240-i),'sold_qty':3} for i in range(240)]
        self.assertEqual(forecast_dispatches(rows,end,365,1095)['forecast_method'],'mean_90_legacy')

    def test_service_selects_model_and_sends_evidence_to_ai(self):
        from commercial_agent_service import CommercialAgentService
        end=date(2026,10,14)
        rows=[{'day':end-timedelta(days=240-i),'sold_qty':Decimal(1+i//20)} for i in range(240)]
        service=CommercialAgentService(None)
        service._product=lambda product_id:{'name_product':'Test'}
        service._all=lambda query,params=():rows if '540 days' in query else rows[-90:]
        ai={'response':'Test','provider':'test','model':'test','used_fallback':False}
        # Source timestamps vary; verify integration and metadata rather than a frozen forecast.
        with patch('commercial_agent_service.generate_ai',return_value=ai) as mocked, patch('commercial_agent_service.datetime') as clock:
            clock.now.return_value=datetime(2026,10,14,tzinfo=timezone.utc)
            result=service.sales_forecast(1)
        self.assertEqual(result['forecast_method'],'linear_90')
        self.assertEqual(result['forecast_qty'],forecasts([r['sold_qty'] for r in rows[-90:]],30)['linear_90'])
        self.assertIn('forecast_method',mocked.call_args.args[0])
        self.assertEqual(result['evidence']['confirmed_dispatch_qty'],Decimal(920))


if __name__=='__main__':
    unittest.main()
