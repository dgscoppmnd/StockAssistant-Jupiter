"""Read-only trace explanations, bounded context and coalesced per-revision caching."""
from collections import Counter, OrderedDict
from concurrent.futures import Future
from datetime import datetime, timezone
import hashlib
import json
from threading import Lock
import time

from ai_service import generate_ai, AIProviderError
from SystemPrompts.rules_agents import rules_trace_system_prompt

_cache = OrderedDict()
_pending = {}
_lock = Lock()
_CACHE_LIMIT = 128


def _bounded(value, depth=0):
    if depth > 6:
        return '[Detalle resumido]'
    if isinstance(value, str):
        return value if len(value) <= 700 else value[:700] + '… [Texto resumido]'
    if isinstance(value, dict):
        result = {k: _bounded(v, depth+1) for k,v in list(value.items())[:20]}
        if len(value) > 20:
            result['_campos_omitidos'] = len(value)-20
        return result
    if isinstance(value, list):
        result = [_bounded(v, depth+1) for v in value[:12]]
        if len(value) > 12:
            result.append({'elementos_omitidos': len(value)-12})
        return result
    return value


def _context(run, events, proposals):
    result = run.get('result') or {}
    context = {'run': {k: run.get(k) for k in ('id','rule_name','rule_code','rule_version','status',
               'started_at','completed_at','error_message')},
               'result': _bounded(result), 'proposals': _bounded(proposals),
               'proposal_status_counts': dict(Counter(p['status'] for p in proposals)),
               'events': [], 'omitted_events': max(0,len(events)-40)}
    for event in events[-40:]:
        detail = event.get('detail') or {}
        if event['phase'] == 'analysis' and 'scenarios' in detail:
            scenarios = detail['scenarios']
            detail = {'entities': len(scenarios), 'sample': [
                {k:s.get(k) for k in ('product_id','warehouse_id','values','quality','relevant')}
                for s in scenarios[:8]], 'omitted_entities': max(0,len(scenarios)-8)}
        elif event['phase'] == 'proposal':
            plan = detail.get('plan') or {}
            detail = {**{k:v for k,v in detail.items() if k != 'plan'},
                      'plan': {k:plan.get(k) for k in ('reason','action','requires_approval')}}
        context['events'].append({'phase':event['phase'],'detail':_bounded(detail)})
    # Remove whole events instead of cutting serialized JSON in the middle.
    while True:
        prompt = json.dumps(context, default=str, ensure_ascii=False, separators=(',', ':'))
        if len(prompt) <= 24000:
            return prompt
        if context['events']:
            context['events'].pop(0)
            context['omitted_events'] += 1
        else:
            raise ValueError('La traza supera el tamaño máximo de interpretación')


def _fallback(run, proposals):
    result = run.get('result') or {}
    reason = run.get('error_message') or result.get('degraded_reason')
    if run['status'] == 'running':
        text = 'La ejecución sigue en curso. La explicación estará disponible cuando termine.'
    elif run['status'] in ('failed','degraded'):
        text = 'La ejecución no se completó con normalidad.'
        if reason:
            text += ' Causa registrada: ' + str(reason)[:700]
        if run['status'] == 'degraded':
            text += ' Se conserva el análisis calculado, pero la decisión de IA no se completó.'
    elif 'report' in result:
        text = 'La regla completó un informe calculado sin utilizar IA para decidir acciones.'
    else:
        text = 'La ejecución terminó. Consulta el evento de decisión para ver los motivos registrados.'
    counts = Counter(p['status'] for p in proposals)
    if counts:
        text += f" Propuestas registradas: {len(proposals)}; pendientes de aprobación: {counts['pending_approval']}; aprobadas: {counts['approved']}; con acción ejecutada: {counts['executed']}."
        text += ' Una acción ejecutada no acredita por sí sola recepción física ni éxito de negocio.'
    else:
        text += ' No hay propuestas persistidas asociadas a esta ejecución.'
    return text


def interpret_trace(run, events, proposals, *, retry=False):
    # Hash all recorded evidence, including updated proposal states, before summarizing it.
    evidence = json.dumps([run,events,proposals], default=str, sort_keys=True, ensure_ascii=False)
    fingerprint = hashlib.sha256(evidence.encode()).hexdigest()
    if run['status'] == 'running':
        return {'source':'pending','explanation':_fallback(run,proposals),'ai':None,'revision':fingerprint}
    with _lock:
        cached = _cache.get(fingerprint)
        if cached and cached[0] > time.monotonic() and not (retry and cached[1]['source']=='fallback'):
            _cache.move_to_end(fingerprint)
            return cached[1]
        pending = _pending.get(fingerprint)
        leader = pending is None
        if leader:
            pending = _pending[fingerprint] = Future()
    if not leader:
        return pending.result(timeout=40)
    try:
        allow_paid = (run.get('config_snapshot') or {}).get('allow_unmetered_paid_ai') is True
        try:
            raw = generate_ai(_context(run,events,proposals),rules_trace_system_prompt(),
                              timeout_seconds=30,max_output_tokens=800,allow_paid=allow_paid)
            explanation = raw.get('response')
            if not isinstance(explanation,str) or not explanation.strip() or len(explanation) > 5000:
                raise ValueError('La IA devolvió una explicación vacía o demasiado extensa')
            response = {'source':'ai','explanation':explanation.strip(),
                        'ai':{k:raw.get(k) for k in ('provider','model','used_fallback')},'warning':None}
        except (AIProviderError,ValueError) as exc:
            warning = str(exc)
            if not allow_paid:
                warning += ' Esta ejecución no autoriza IA de pago; OpenAI no se utiliza como alternativa.'
            response = {'source':'fallback','explanation':_fallback(run,proposals),'ai':None,'warning':warning}
        response.update(revision=fingerprint,generated_at=datetime.now(timezone.utc).isoformat())
        with _lock:
            _cache[fingerprint] = (time.monotonic()+(600 if response['source']=='ai' else 30),response)
            _cache.move_to_end(fingerprint)
            while len(_cache) > _CACHE_LIMIT:
                _cache.popitem(last=False)
        pending.set_result(response)
        return response
    except Exception as exc:
        pending.set_exception(exc)
        raise
    finally:
        with _lock:
            _pending.pop(fingerprint,None)
