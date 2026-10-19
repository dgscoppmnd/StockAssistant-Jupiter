"""Source-controlled values and chart data for concise trace explanations."""
from collections import Counter
from decimal import Decimal, InvalidOperation
from pydantic import BaseModel, ConfigDict, Field, model_validator


class TraceNote(BaseModel):
    model_config = ConfigDict(extra='forbid')
    summary: str = Field(min_length=1, max_length=500)
    next_step: str = Field(max_length=200)
    metric_ids: list[str] = Field(max_length=4)
    chart_id: str

    @model_validator(mode='after')
    def concise(self):
        if not self.summary.strip() or len(self.summary.split()) > 60 or len(self.next_step.split()) > 25:
            raise ValueError('La nota supera el límite de extensión')
        if len(set(self.metric_ids)) != len(self.metric_ids):
            raise ValueError('Los indicadores de la nota no pueden repetirse')
        return self


def _number(value):
    if value is None or isinstance(value, bool):
        return None
    try:
        number = Decimal(str(value))
        return str(number) if number.is_finite() and abs(number) <= Decimal('1e12') else None
    except (InvalidOperation, ValueError):
        return None


def presentation_catalog(run, events, proposals):
    metrics, charts = {}, {}
    def metric(key, label, value, unit):
        number = _number(value)
        if number is not None:
            metrics[key] = {'label':label,'value':number,'unit':unit}
    states = Counter(p['status'] for p in proposals)
    metric('proposals_total','Propuestas registradas',len(proposals),'propuestas')
    labels = {'pending_approval':'Pendientes de aprobación','approved':'Aprobadas','executed':'Acción ejecutada',
              'rejected':'Rechazadas','obsolete':'Obsoletas','expired':'Caducadas'}
    for state,label in labels.items():
        if states[state]:
            metric('proposals_'+state,label,states[state],'propuestas')
    points = [{'label':label,'value':str(states[state])} for state,label in labels.items() if states[state]]
    if len(points) >= 2:
        charts['proposal_states'] = {'title':'Estado actual de las propuestas','unit':'propuestas','points':points}
    report = (run.get('result') or {}).get('report') or {}
    metric('movements_24h','Movimientos en 24 horas',report.get('movements_24h'),'movimientos')
    if isinstance(report.get('alerts'),list):
        metric('risk_alerts','Alertas detectadas',len(report['alerts']),'alertas')
    analysis = next((e.get('detail') or {} for e in reversed(events) if e['phase']=='analysis'),{})
    scenarios = analysis.get('scenarios')
    if isinstance(scenarios,list):
        metric('entities_analyzed','Producto / almacén revisados',analysis.get('rows_examined'),'combinaciones')
        metric('eligible_entities','Combinaciones que cumplen la regla',len(scenarios),'combinaciones')
        for index,scenario in enumerate(scenarios[:3]):
            values,unit = scenario.get('values') or {},scenario.get('unit')
            available,pending = _number(values.get('available')),_number(values.get('pending'))
            if not isinstance(unit,str) or not unit or available is None or pending is None:
                continue
            if Decimal(available)==0 and Decimal(pending)==0:
                continue
            charts['stock_'+str(index)] = {
                'title':f"Stock · producto #{scenario['product_id']} / almacén #{scenario['warehouse_id']}",
                'unit':unit,'points':[{'label':'Disponible','value':available},{'label':'Pendiente','value':pending}]}
    return metrics,charts


def note_schema(metrics,charts):
    schema = TraceNote.model_json_schema()
    schema['properties']['metric_ids']['items']['enum'] = list(metrics)
    schema['properties']['chart_id']['enum'] = ['',*charts]
    return schema


def validate_note(text,metrics,charts):
    note = TraceNote.model_validate_json(text)
    if any(key not in metrics for key in note.metric_ids) or (note.chart_id and note.chart_id not in charts):
        raise ValueError('La nota seleccionó indicadores o gráficas ajenos a la evidencia')
    return {'explanation':note.summary.strip(),'next_step':note.next_step.strip(),
            'metrics':[metrics[key] for key in note.metric_ids], 'chart':charts.get(note.chart_id)}
