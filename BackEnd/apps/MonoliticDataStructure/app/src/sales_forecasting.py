"""Forecast recorded dispatches using rolling temporal model comparison.

Missing dates mean no recorded dispatch, not proven zero demand or complete
coverage. This numerical component never calls an LLM or changes inventory.
"""
from datetime import date, timedelta
from decimal import Decimal

MODELS = ('mean_90', 'mean_30', 'weekly_repeat', 'linear_90')
ZERO = Decimal(0)


def forecasts(history, horizon):
    if len(history) != 90 or not 1 <= horizon <= 365:
        raise ValueError('Expected 90 past daily observations and horizon 1..365')
    values = [Decimal(str(value)) for value in history]
    if any(not value.is_finite() or value < 0 for value in values):
        raise ValueError('Dispatch quantities must be finite and nonnegative')
    mean = sum(values, ZERO) / 90
    center = Decimal('44.5')
    slope = sum(((Decimal(i)-center)*(value-mean) for i,value in enumerate(values)), ZERO) / sum(((Decimal(i)-center)**2 for i in range(90)), ZERO)
    return {
        'mean_90': mean*horizon,
        'mean_30': sum(values[-30:], ZERO)/30*horizon,
        'weekly_repeat': sum((values[-7:][i % 7] for i in range(horizon)), ZERO),
        'linear_90': sum((max(ZERO, mean+slope*(Decimal(i)-center)) for i in range(90,90+horizon)), ZERO),
    }


def select_method(history, horizon):
    """Compare up to five disjoint future windows; each model sees only its past."""
    origins = list(range(90, len(history)-horizon+1, horizon))[-5:]
    if len(origins) < 3:
        raise ValueError('At least three temporal validation windows are required')
    errors = {name: [] for name in MODELS}
    for origin in origins:
        predicted = forecasts(history[origin-90:origin], horizon)
        actual = sum(history[origin:origin+horizon], ZERO)
        for name in MODELS:
            errors[name].append(predicted[name]-actual)
    scores = {name: {'mae_units':sum(map(abs,values),ZERO)/len(values),
                     'bias_units':sum(values,ZERO)/len(values),
                     'windows':len(values)} for name,values in errors.items()}
    selected = min(MODELS, key=lambda name:scores[name]['mae_units'])
    return selected, scores


def forecast_dispatches(rows, as_of, horizon, fallback_qty):
    """as_of is exclusive UTC date; fallback preserves the legacy calculation."""
    if type(as_of) is not date or not 1 <= horizon <= 365:
        raise ValueError('Expected UTC cutoff date and horizon 1..365')
    result = {
        'forecast_qty':Decimal(str(fallback_qty)),
        'forecast_method':'mean_90_legacy',
        'forecast_validation':{'status':'insufficient_history','reason':'Not enough recorded history for temporal comparison'},
        'forecast_scope':'recorded_dispatches_not_unconstrained_demand',
        'forecast_warnings':[
            'History completeness and stock availability are unknown.',
            'No dispatch record is not proof of zero demand.',
            'Temporal comparison does not guarantee future accuracy.',
        ],
    }
    recorded={}
    for row in rows:
        day=row.get('day')
        if type(day) is not date:
            raise ValueError('Daily dispatch dates must be date values')
        qty=Decimal(str(row['sold_qty']))
        if not qty.is_finite() or qty < 0 or day in recorded:
            raise ValueError('Invalid or duplicate daily dispatch observation')
        if as_of-timedelta(days=540) <= day < as_of:
            recorded[day]=qty
    positive_days=sum(qty>0 for qty in recorded.values())
    if not recorded or positive_days < 30:
        result['forecast_validation']['reason']='Fewer than 30 days with positive recorded dispatches'
        return result
    start=min(recorded)
    series=[recorded.get(start+timedelta(days=i),ZERO) for i in range((as_of-start).days)]
    # Do not tune a model with too few observations or extrapolate beyond tested horizon.
    if len(series) < 90+3*horizon or horizon > 90:
        return result
    selected,scores=select_method(series,horizon)
    predicted=forecasts(series[-90:],horizon)
    result.update({
        'forecast_qty':predicted[selected],
        'forecast_method':selected,
        'forecast_validation':{'status':'rolling_comparison','selected_mae_units':scores[selected]['mae_units'],
                               'candidate_scores':scores,'horizon_days':horizon,
                               'meaning':'Historical model-selection error, not a confidence interval or independent final test'},
        'forecast_as_of_exclusive':as_of.isoformat(),
        'forecast_history':{'start':start.isoformat(),'end_exclusive':as_of.isoformat(),
                            'calendar_days':len(series),'positive_dispatch_days':positive_days,
                            'missing_date_policy':'No recorded dispatch is represented as zero recorded dispatch; demand coverage remains unknown'},
        'forecast_baseline_qty':predicted['mean_90'],
    })
    return result
