"""Operational automation, composed separately from the read-only executive.

Database locks are short lived. Model calls receive bounded, allowlisted data and
never run with a database transaction open. Physical transfers require a human.
"""
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from decimal import Decimal, ROUND_FLOOR
import hashlib
import json
import logging
import os
import time
from uuid import uuid4
from zoneinfo import ZoneInfo

from psycopg2.extras import Json, RealDictCursor
from ai_service import generate_ai, AIProviderError
from agent_service import AgentService
from commercial_agent_service import CommercialAgentService
from inventory_service import InventoryService
from automation_contracts import RuleConfig, RuleDraft, parse_model_turn, model_turn_schema, replenishment, conditions_match, dec, forecast_metrics
from rules_policy import validate_rule_objective
from SystemPrompts.rules_agents import rules_agent_system_prompt
from trace_interpretation import interpret_trace

logger = logging.getLogger(__name__)


def document(data):
    return Json(data, dumps=lambda value: json.dumps(value, default=str, ensure_ascii=False))


def digest(data):
    return hashlib.sha256(json.dumps(data, default=str, sort_keys=True).encode()).hexdigest()


class AtomicInventory(InventoryService):
    """Use domain stock invariants inside the caller's single atomic transaction."""
    @contextmanager
    def transaction(self):
        yield


class AutomationService:
    DEFAULT_RULES = (
        ('stock_reorder_proposals', 'Propuestas de reposición', 'Compara reposición, traslado y espera.'),
        ('daily_inventory_report', 'Informe diario', 'Observa movimientos confirmados.'),
        ('risk_alerts', 'Alertas de riesgos', 'Observa devoluciones confirmadas.'),
        ('stagnant_stock', 'Stock estancado', 'Compara alternativas para exceso de cobertura.'),
    )

    def __init__(self, connection):
        self.connection = connection
        self.inventory = AgentService(connection)
        self.commercial = CommercialAgentService(connection)

    def _all(self, sql, params=()):
        with self.connection.cursor(cursor_factory=RealDictCursor) as c:
            c.execute(sql, params)
            return [dict(row) for row in c.fetchall()]

    def _one(self, sql, params=()):
        rows = self._all(sql, params)
        return rows[0] if rows else None

    def _write(self, sql, params=()):
        with self.connection.cursor() as c:
            c.execute(sql, params)
            return c.rowcount

    def event(self, run_id, rule_id, phase, detail):
        self._write('INSERT INTO public.automation_events(run_id,rule_id,phase,detail) VALUES(%s,%s,%s,%s)',
                    (run_id, rule_id, phase, document(detail)))

    def ensure_default_rules(self):
        for code, name, description in self.DEFAULT_RULES:
            self._write('''INSERT INTO public.automation_rules(code,name,description) VALUES(%s,%s,%s)
                           ON CONFLICT(code) DO NOTHING''', (code, name, description))
        self.connection.commit()

    def rules(self):
        self.ensure_default_rules()
        return self._all('''SELECT r.*,v.config,
            COALESCE(r.last_run_at + r.interval_minutes * INTERVAL '1 minute',now()) AS next_run_at,
            (SELECT x.status FROM public.automation_runs x WHERE x.rule_id=r.id ORDER BY x.id DESC LIMIT 1) AS latest_run_status,
            (SELECT COUNT(*) FROM public.agent_action_proposals p WHERE p.rule_id=r.id AND p.status='pending_approval') AS pending_proposals,
            (SELECT COUNT(*) FROM public.agent_action_proposals p WHERE p.rule_id=r.id AND p.status='executed') AS executed_actions,
            (SELECT e.phase FROM public.automation_events e WHERE e.rule_id=r.id
              AND e.phase IN ('schema_valid','schema_rejected','provider_failure') ORDER BY e.id DESC LIMIT 1) AS last_provider_signal
            FROM public.automation_rules r LEFT JOIN public.automation_rule_versions v
            ON v.rule_id=r.id AND v.version=r.current_version ORDER BY r.id''')

    def config(self, rule):
        row = self._one('SELECT config FROM public.automation_rule_versions WHERE rule_id=%s AND version=%s',
                        (rule['id'], rule['current_version']))
        if row:
            return RuleConfig.model_validate(row['config'])
        if rule['code'] not in {r[0] for r in self.DEFAULT_RULES}:
            raise ValueError('Código de regla desconocido')
        return RuleConfig(kind=rule['code'], interval_minutes=rule['interval_minutes'])

    def save_rule(self, draft: RuleDraft, actor, rule_id=None, can_authorize=False):
        validate_rule_objective(draft.config.kind, draft.config.objective)
        try:
            if rule_id:
                rule = self._one('SELECT * FROM public.automation_rules WHERE id=%s FOR UPDATE', (rule_id,))
                if not rule or rule['current_version'] != draft.expected_version:
                    raise ValueError('Versión desactualizada; recarga la regla')
                old = self.config(rule)
                if rule['lease_until'] and rule['lease_until'] > datetime.now(timezone.utc):
                    raise ValueError('Hay una ejecución en curso; espera antes de editar')
            else:
                old = RuleConfig()
                rule = self._one('''INSERT INTO public.automation_rules(code,name,description)
                    VALUES(%s,%s,%s) RETURNING *''', ('custom_' + uuid4().hex[:20], draft.name, draft.description))
                rule_id = rule['id']
            config = draft.config
            expands = (config.mode == 'limited_auto' and old.mode != 'limited_auto') or (
                set(config.allowed_actions) - set(old.allowed_actions)) or any(
                getattr(config, k) > getattr(old, k) for k in ('daily_budget', 'per_action_budget')) or (
                config.allow_unmetered_paid_ai and not old.allow_unmetered_paid_ai)
            if config.mode == 'limited_auto' and old.mode == 'limited_auto' and config != old:
                expands = True  # Any executable policy revision requires an accountable authorizer.
            if expands and not can_authorize:
                raise PermissionError('Ampliar autonomía o presupuesto requiere permiso authorize')
            self.validate_references(config)
            version = rule['current_version'] + 1
            self._write('''INSERT INTO public.automation_rule_versions(rule_id,version,config,author,reason)
                        VALUES(%s,%s,%s,%s,%s)''', (rule_id, version, document(config.model_dump(mode='json')), actor, draft.reason))
            # A new version is a paused draft. Pending decisions cannot silently inherit it.
            self._write('''UPDATE public.automation_rules SET current_version=%s,name=%s,description=%s,
                interval_minutes=%s,is_active=FALSE,failures=0,updated_at=now() WHERE id=%s''',
                (version, draft.name, draft.description, config.interval_minutes, rule_id))
            self._write('''UPDATE public.agent_action_proposals SET status='obsolete',updated_at=now(),
                reason='Cambio de versión de regla' WHERE rule_id=%s AND status IN ('pending_approval','approved')''', (rule_id,))
            self.event(None, rule_id, 'version_saved', {'version': version, 'actor': actor, 'reason': draft.reason})
            self.connection.commit()
            return {'id': rule_id, 'version': version, 'is_active': False}
        except Exception:
            self.connection.rollback()
            raise

    def validate_references(self, config):
        for ids, sql in ((config.product_ids, 'SELECT pk_product AS id FROM public.productos WHERE pk_product=ANY(%s)'),
                         (config.warehouse_ids, 'SELECT id FROM public.inventory_warehouses WHERE id=ANY(%s)')):
            if ids and {r['id'] for r in self._all(sql, (ids,))} != set(ids):
                raise ValueError('Productos o almacenes inexistentes')

    def validate_execution_config(self, config):
        # Revalidate existing configurations as well as newly saved drafts.
        config = RuleConfig.model_validate(config.model_dump(mode='json'))
        validate_rule_objective(config.kind, config.objective)
        self.validate_references(config)

    def deterministic_report(self, config):
        if config.kind == 'daily_inventory_report':
            return self._one('''SELECT COUNT(*) AS movements_24h FROM public.inventory_movements
                WHERE created_at>=now()-INTERVAL '24 hours'
                AND (%s OR product_id=ANY(%s)) AND (%s OR warehouse_id=ANY(%s))''',
                (not config.product_ids, config.product_ids, not config.warehouse_ids, config.warehouse_ids))
        if config.kind == 'risk_alerts':
            return self.commercial.risks(product_ids=config.product_ids, warehouse_ids=config.warehouse_ids,
                                         limit=config.max_entities)
        raise ValueError('Este tipo de regla no genera un informe determinista')

    def versions(self, rule_id):
        return self._all('SELECT * FROM public.automation_rule_versions WHERE rule_id=%s ORDER BY version DESC', (rule_id,))

    def set_rule_active(self, rule_id, is_active, actor='legacy'):
        try:
            self._one('SELECT * FROM public.automation_control WHERE id=1 FOR UPDATE')
            rule = self._one('SELECT * FROM public.automation_rules WHERE id=%s FOR UPDATE', (rule_id,))
            if not rule:
                raise ValueError('Automatización no encontrada')
            config = self.config(rule)
            if is_active:
                self.validate_execution_config(config)
            overlaps = self.overlaps(config, rule_id) if is_active else []
            if config.mode == 'limited_auto' and any(r['conflict'] for r in overlaps):
                raise ValueError('Reglas activas contradictorias; ajusta el alcance antes de activar autonomía')
            self._write('UPDATE public.automation_rules SET is_active=%s,failures=0,updated_at=now() WHERE id=%s', (is_active, rule_id))
            self.event(None, rule_id, 'activation' if is_active else 'deactivation', {'actor': actor, 'version': rule['current_version']})
            self.connection.commit()
            return {**rule, 'is_active': is_active, 'overlapping_rules': overlaps}
        except Exception:
            self.connection.rollback()
            raise

    def stopped(self):
        return bool((self._one('SELECT stopped FROM public.automation_control WHERE id=1') or {}).get('stopped')) or os.getenv('AUTOMATION_EMERGENCY_STOP', 'false').lower() == 'true'

    def stop(self, stopped, actor):
        self._write('UPDATE public.automation_control SET stopped=%s,updated_by=%s,updated_at=now() WHERE id=1', (stopped, actor))
        self.connection.commit()
        return {'stopped': stopped}

    def snapshots(self, config):
        # Correlated aggregates avoid multiplying sales by purchases or receipts.
        return self._all('''SELECT s.product_id,s.warehouse_id,s.physical_qty,s.reserved_qty,
            s.updated_at AS stock_updated_at,TRIM(p.name_product) AS product_name,u.code AS unit,
            c.base_unit_id,c.reorder_point,c.reorder_quantity,
            COALESCE((SELECT SUM(l.pending_qty) FROM public.purchase_order_lines l
              JOIN public.purchase_orders o ON o.id=l.purchase_order_id
              WHERE l.product_id=s.product_id AND o.warehouse_id=s.warehouse_id
                AND o.status NOT IN ('cancelado','recibido','borrador')),0) AS pending,
            COALESCE((SELECT SUM(-m.quantity_signed) FROM public.inventory_movements m
              WHERE m.product_id=s.product_id AND m.warehouse_id=s.warehouse_id
                AND m.movement_type='dispatch' AND m.created_at>=now()-INTERVAL '90 days'),0) AS sold_90,
            (SELECT MAX(m.created_at) FROM public.inventory_movements m
              WHERE m.product_id=s.product_id AND m.warehouse_id=s.warehouse_id AND m.movement_type='dispatch') AS last_sale,
            (SELECT COUNT(DISTINCT DATE(m.created_at)) FROM public.inventory_movements m
              WHERE m.product_id=s.product_id AND m.warehouse_id=s.warehouse_id
                AND m.movement_type='dispatch' AND m.created_at>=now()-INTERVAL '90 days') AS sales_days,
            (SELECT SUM(g.received_qty*g.unit_price*g.exchange_rate)/NULLIF(SUM(g.received_qty),0)
              FROM public.goods_receipt_lines g WHERE g.product_id=s.product_id) AS historical_cost
            FROM public.inventory_stock_levels s JOIN public.productos p ON p.pk_product=s.product_id
            JOIN public.product_inventory_config c ON c.product_id=s.product_id
            JOIN public.inventory_units u ON u.id=c.base_unit_id
            WHERE (%s OR s.product_id=ANY(%s)) AND (%s OR s.warehouse_id=ANY(%s))
            ORDER BY s.product_id,s.warehouse_id LIMIT %s''',
            (not config.product_ids, config.product_ids, not config.warehouse_ids, config.warehouse_ids, config.max_entities))

    def suppressed(self, product_id, warehouse_id):
        return self._one('''SELECT id FROM public.agent_action_proposals WHERE product_id=%s AND warehouse_id=%s
            AND action='suspend_reorder' AND status='executed' AND (action_result->>'until')::timestamptz>now()''',
            (product_id, warehouse_id)) is not None

    @staticmethod
    def compare(row, rows, config):
        available = dec(row['physical_qty']) - dec(row['reserved_qty'])
        daily = dec(row['sold_90']) / 90
        coverage = available / daily if daily else None
        days_without = (datetime.now(timezone.utc) - row['last_sale']).days if row['last_sale'] else None
        values = {'available': available, 'pending': row['pending'], 'sold_90': row['sold_90'],
                  'coverage_days': coverage, 'days_without_sales': days_without}
        need = replenishment(row, config)
        stagnant = available > 0 and ((coverage is not None and coverage > config.maximum_coverage_days)
                    or days_without is None or days_without >= config.stagnant_days)
        relevant = (need > 0 if config.kind == 'stock_reorder_proposals' else stagnant) and conditions_match(values, config.conditions)
        assumptions = ['Media de despachos en ventana de 90 días; días sin registro no prueban demanda cero.',
                       'No hay serie diaria completa de disponibilidad; la demanda puede estar censurada.',
                       'Costes históricos no constituyen una oferta vigente; moneda de referencia según cambios de cada línea.']
        if config.lead_days is None:
            assumptions.append('Plazo de suministro desconocido; cálculo sin plazo adicional.')
        else:
            assumptions.append('Plazo de suministro configurado por el operador, no medido.')
        options = [{'action': 'wait', 'quantity': '0', 'executable': True, 'reason': 'Conservar stock y recopilar evidencia'}]
        if need > 0:
            options.append({'action': 'replenish', 'quantity': str(need), 'executable': False,
                'reason': 'Requiere oferta vigente confirmada, proveedor y presupuesto',
                'estimated_cost': str(need * dec(row['historical_cost'])) if row['historical_cost'] is not None else None})
        for other in rows:
            if other['product_id'] != row['product_id'] or other['warehouse_id'] == row['warehouse_id']:
                continue
            free = dec(other['physical_qty']) - dec(other['reserved_qty'])
            other_daily = dec(other['sold_90']) / 90
            if need > 0 and daily > 0:
                surplus = max(Decimal(0), free - max(dec(other['reorder_point']), other_daily * config.origin_min_days) - config.safety_qty)
                qty, source, destination = min(need, surplus), other, row
            elif stagnant and other_daily > 0:
                surplus = max(Decimal(0), available - max(dec(row['reorder_point']), daily * config.origin_min_days) - config.safety_qty)
                qty, source, destination = min(surplus, replenishment(other, config)), row, other
            else:
                continue
            qty = qty.quantize(Decimal('0.0001'),rounding=ROUND_FLOOR)
            if qty > 0:
                options.append({'action': 'transfer', 'quantity': str(qty), 'source_warehouse_id': source['warehouse_id'],
                    'destination_warehouse_id': destination['warehouse_id'], 'executable': False,
                    'reason': 'Destino con despachos; exige confirmación física', 'logistics_cost': None})
                break
        if stagnant:
            options.extend([
                {'action': 'suspend_reorder', 'quantity': '0', 'executable': True,
                 'reason': 'Suprime nuevas propuestas automáticas para este producto y almacén; no cancela pedidos'},
                {'action': 'promotion', 'quantity': str(max(available, Decimal(0))), 'executable': False,
                 'minimum_price_reference': str(dec(row['historical_cost']) / (1 - config.minimum_margin_percent / 100)) if row['historical_cost'] is not None else None,
                 'reason': 'Condicionada a coste vigente, precio, costes comerciales y autorización de publicación'},
                {'action': 'supplier_return', 'quantity': str(max(available, Decimal(0))), 'executable': False,
                 'reason': 'No constan condiciones verificadas de devolución al proveedor'}])
        return {'product_id': row['product_id'], 'warehouse_id': row['warehouse_id'], 'unit': row['unit'],
                'relevant': relevant, 'values': values, 'alternatives': options, 'assumptions': assumptions,
                'observed': row, 'forecast_90': str(row['sold_90']), 'coverage_days': coverage,
                'quality': 'insufficient' if row['sales_days'] < 2 else 'partial', 'snapshot_hash': digest(row)}

    def simulate(self, config):
        self.validate_execution_config(config)
        if config.kind in ('daily_inventory_report', 'risk_alerts'):
            report = self.deterministic_report(config)
            self.connection.rollback()
            return {'as_of': datetime.now(timezone.utc), 'simulation': True, 'report': report,
                    'scenarios': [], 'overlapping_rules': [],
                    'limitations': ['Informe calculado sin IA, propuestas ni acciones operativas.']}
        rows = self.snapshots(config)
        scenarios = [self.compare(r, rows, config) for r in rows]
        overlaps = self.overlaps(config)
        for scenario in scenarios:
            scenario['authorization'] = []
            for option in scenario['alternatives']:
                permitted_auto = (config.mode == 'limited_auto' and not config.simulation
                                  and option['action'] in config.allowed_actions and option['executable'])
                scenario['authorization'].append({'action': option['action'], 'automatic': permitted_auto,
                    'status': 'no_operation' if option['action']=='wait' else
                              'observation_only' if config.mode == 'observation' or config.simulation else
                              ('authorized_with_current_data' if permitted_auto else 'requires_approval_or_missing_dependencies'),
                    'conditions': option['reason']})
        self.connection.rollback()  # Simulation has no persistent or operational effects.
        return {'as_of': datetime.now(timezone.utc), 'simulation': True,
                'scenarios': [s for s in scenarios if s['relevant']],
                'overlapping_rules': overlaps,
                'limitations': ['Instantánea limitada por max_entities; no garantiza resultados futuros.',
                               'Estimaciones de coste no autorizan gasto ni prueban rentabilidad.']}

    def overlaps(self, config, exclude_id=None):
        candidates = self._all('''SELECT r.id,r.name,v.config FROM public.automation_rules r
            JOIN public.automation_rule_versions v ON v.rule_id=r.id AND v.version=r.current_version
            WHERE r.is_active AND (%s IS NULL OR r.id<>%s)''', (exclude_id, exclude_id))
        overlaps = []
        for row in candidates:
            other = RuleConfig.model_validate(row['config'])
            products = not config.product_ids or not other.product_ids or bool(set(config.product_ids) & set(other.product_ids))
            warehouses = not config.warehouse_ids or not other.warehouse_ids or bool(set(config.warehouse_ids) & set(other.warehouse_ids))
            if products and warehouses and {config.kind,other.kind} <= {'stock_reorder_proposals','stagnant_stock'}:
                overlaps.append({'id':row['id'],'name':row['name'],'conflict':config.kind != other.kind,
                    'reason':'Ámbitos coincidentes; reposición y supresión pueden ser contradictorias'})
        return overlaps

    def claim(self, rule_id, initiated_by):
        try:
            rule = self._one('SELECT * FROM public.automation_rules WHERE id=%s FOR UPDATE SKIP LOCKED', (rule_id,))
            now = datetime.now(timezone.utc)
            if not rule or self.stopped():
                self.connection.rollback()
                return None
            config = self.config(rule)
            self.validate_execution_config(config)
            if rule['lease_until'] and rule['lease_until'] > now:
                self.connection.rollback()
                return None
            if initiated_by == 'scheduler':
                local_hour = now.astimezone(ZoneInfo(config.timezone)).hour
                if not rule['is_active'] or rule['failures'] >= 3 or not config.window_start_hour <= local_hour < config.window_end_hour or (
                    rule['last_run_at'] and rule['last_run_at'] + timedelta(minutes=rule['interval_minutes']) > now):
                    self.connection.rollback()
                    return None
            recovered = self._write('''UPDATE public.automation_runs SET status='failed',error_message='Ejecución abandonada; lease caducado',completed_at=now()
                WHERE rule_id=%s AND status='running' ''', (rule_id,))
            if recovered:
                rule['failures'] += 1
                self._write('UPDATE public.automation_rules SET failures=%s WHERE id=%s', (rule['failures'],rule_id))
                self.event(None,rule_id,'recovery',{'abandoned_runs':recovered,'attempt':rule['failures']})
                if initiated_by == 'scheduler' and rule['failures'] >= 3:
                    self._write('UPDATE public.automation_rules SET lease_until=NULL,claim_token=NULL WHERE id=%s',(rule_id,))
                    self.connection.commit()
                    return None
            token = uuid4().hex
            self._write("UPDATE public.automation_rules SET claim_token=%s,lease_until=now()+INTERVAL '10 minutes' WHERE id=%s", (token, rule_id))
            run = self._one('''INSERT INTO public.automation_runs(rule_id,initiated_by,status,rule_version,config_snapshot,claim_token)
                VALUES(%s,%s,'running',%s,%s,%s) RETURNING *''',
                (rule_id, initiated_by, rule['current_version'], document(config.model_dump(mode='json')), token))
            self.event(run['id'], rule_id, 'observation', {'version': rule['current_version']})
            self.connection.commit()
            return rule, config, run, token
        except Exception:
            self.connection.rollback()
            raise

    def choose(self, scenarios, config, event):
        """One decision from complete precomputed evidence; no redundant tool round trips."""
        validate_rule_objective(config.kind, config.objective)
        if config.max_model_calls == 0:
            raise ValueError('No hay llamadas al modelo autorizadas')
        start = time.monotonic()
        by_key = {(s['product_id'], s['warehouse_id']): s for s in scenarios}
        # Values already include available, pending and sold_90. Send complementary stock data only.
        inventory_fields = ('physical_qty', 'reserved_qty', 'reorder_point', 'reorder_quantity',
                            'sales_days', 'last_sale', 'stock_updated_at', 'historical_cost')
        context = [{'product_id': s['product_id'], 'warehouse_id': s['warehouse_id'],
                    'unit': s['unit'], 'values': s['values'],
                    'inventory': {key: s['observed'].get(key) for key in inventory_fields},
                    'alternatives': s['alternatives'], 'quality': s['quality']} for s in scenarios]
        assumptions = list(dict.fromkeys(a for s in scenarios for a in s['assumptions']))
        schema = model_turn_schema()
        # The provider may return at most one decision per received entity.
        schema['properties']['choices']['maxItems'] = len(scenarios)
        system = rules_agent_system_prompt(config.kind)
        prompt = json.dumps({'rule': {'kind': config.kind, 'objective': config.objective,
            'mode': config.mode, 'simulation': config.simulation}, 'assumptions': assumptions,
            'context': context}, default=str, ensure_ascii=False, separators=(',', ':'))
        if len(prompt) > 60000:
            raise ValueError('Contexto del modelo demasiado grande; reduce el máximo de entidades de la regla')
        event('model_call', {'step': 1, 'strategy': 'direct_decision', 'entities': len(scenarios),
                            'prompt_characters': len(prompt), 'system_characters': len(system)})
        raw = generate_ai(prompt, system,
                          timeout_seconds=config.max_seconds-(time.monotonic()-start),
                          max_output_tokens=4096,
                          allow_paid=config.allow_unmetered_paid_ai, response_schema=schema)
        if time.monotonic() - start > config.max_seconds:
            raise ValueError('Respuesta recibida después del plazo; sin acciones')
        meta = {k: raw.get(k) for k in ('provider', 'model', 'used_fallback', 'usage', 'cost')}
        try:
            turn, normalized = parse_model_turn(raw['response'])
            seen = set()
            for choice in turn.choices:
                key = (choice.product_id, choice.warehouse_id)
                if key not in by_key or key in seen or choice.action not in {a['action'] for a in by_key[key]['alternatives']}:
                    raise ValueError('Selección del modelo fuera del contrato')
                seen.add(key)
        except (ValueError, KeyError):
            event('schema_rejected', {'step': 1, 'ai': meta})
            raise
        event('schema_valid', {'step': 1, 'ai': meta, 'finish_reason': turn.finish_reason})
        if normalized:
            event('response_normalized', {'step': 1, 'format': 'markdown_json_fence'})
        event('decision', {'choices': [c.model_dump() for c in turn.choices], 'reason': turn.finish_reason})
        return turn.choices, meta

    def run_rule(self, rule_id, initiated_by='manual'):
        claimed = self.claim(rule_id, initiated_by)
        if not claimed:
            return {'rule_id': rule_id, 'status': 'skipped', 'reason': 'Pausado, detenido, ocupado o fuera de ventana'}
        rule, config, run, token = claimed
        run_id = run['id']
        def event(phase, detail):
            self.event(run_id, rule_id, phase, detail)
            self.connection.commit()
        try:
            result = {'simulation': config.simulation, 'mode': config.mode, 'ai': None, 'proposals': []}
            if config.kind in ('daily_inventory_report', 'risk_alerts'):
                result['report'] = self.deterministic_report(config)
                event('analysis', {'strategy': 'deterministic_report', 'report': result['report'],
                                  'product_ids': config.product_ids, 'warehouse_ids': config.warehouse_ids})
                event('decision', {'reason': 'Informe sin IA; no genera propuestas ni acciones'})
            else:
                rows = self.snapshots(config)
                scenarios = [self.compare(r, rows, config) for r in rows]
                scenarios = [s for s in scenarios if s['relevant']]
                if config.kind == 'stock_reorder_proposals':
                    scenarios = [s for s in scenarios if not self.suppressed(s['product_id'], s['warehouse_id'])]
                event('analysis', {'as_of': datetime.now(timezone.utc), 'scenarios': scenarios})
                choices = []
                if scenarios:
                    try:
                        choices, result['ai'] = self.choose(scenarios, config, event)
                    except (AIProviderError, ValueError, KeyError, TypeError) as exc:
                        result['degraded'] = True
                        result['degraded_reason'] = str(exc)[:500]
                        if isinstance(exc, AIProviderError):
                            event('provider_failure', {'provider': exc.provider, 'retryable': exc.retryable})
                        event('degraded', {'reason': result['degraded_reason'], 'deterministic_analysis_preserved': True})
                else:
                    event('decision', {'reason': 'Ninguna entidad cumple las condiciones; sin acciones'})
                by_key = {(s['product_id'], s['warehouse_id']): s for s in scenarios}
                for choice in choices:
                    scenario = by_key[(choice.product_id, choice.warehouse_id)]
                    alternative = next(a for a in scenario['alternatives'] if a['action'] == choice.action)
                    if choice.action == 'wait':
                        continue
                    if config.mode == 'observation' or config.simulation:
                        event('proposal', {'choice': choice.model_dump(), 'alternative': alternative, 'persisted': False})
                        continue
                    proposal = self.persist_proposal(rule, run, config, scenario, alternative, choice.reason)
                    if proposal:
                        result['proposals'].append(proposal['id'])
                        if config.mode == 'limited_auto' and choice.action in config.allowed_actions:
                            try:
                                self.act(proposal['id'], 'scheduler', automatic=True)
                            except (ValueError, PermissionError) as exc:
                                self.connection.rollback()
                                result.setdefault('blocked_actions', []).append({'proposal_id': proposal['id'], 'reason': str(exc)})
                result['evaluations'] = self.evaluate_due()
            status = 'degraded' if result.get('degraded') else 'completed'
            event('review', {'scheduled': True})
            owner = self._one('SELECT claim_token FROM public.automation_rules WHERE id=%s FOR UPDATE',(rule_id,))
            if not owner or owner['claim_token'] != token:
                raise ValueError('La ejecución perdió su reclamación; resultado descartado')
            self._write("UPDATE public.automation_runs SET status=%s,result=%s,completed_at=now() WHERE id=%s AND claim_token=%s AND status='running'",
                        (status, document(result), run_id, token))
            self._write('''UPDATE public.automation_rules SET last_run_at=now(),lease_until=NULL,claim_token=NULL,failures=0
                WHERE id=%s AND claim_token=%s''', (rule_id, token))
            self.connection.commit()
            return {'run_id': run_id, 'status': status, 'result': result}
        except Exception as exc:
            self.connection.rollback()
            self._write("UPDATE public.automation_runs SET status='failed',error_message=%s,completed_at=now() WHERE id=%s AND status='running'", (str(exc)[:500], run_id))
            self._write('''UPDATE public.automation_rules SET lease_until=NULL,claim_token=NULL,last_run_at=now(),failures=failures+1
                WHERE id=%s AND claim_token=%s''', (rule_id, token))
            self.event(run_id, rule_id, 'error', {'reason': str(exc)[:500]})
            self.connection.commit()
            raise

    def persist_proposal(self, rule, run, config, scenario, alternative, reason):
        try:
            # Rule lock fences abandoned workers and serializes competing proposal producers.
            locked = self._one('SELECT * FROM public.automation_rules WHERE id=%s FOR UPDATE', (rule['id'],))
            if locked['claim_token'] != run['claim_token'] or locked['current_version'] != rule['current_version'] or self.stopped():
                raise ValueError('Ejecución o política caducada')
            self.event(run['id'],rule['id'],'validation',{'phase':'proposal','result':'passed',
                'checks':['rule_version','claim_owner','emergency_stop','typed_action','calculated_quantity']})
            self._write("SELECT pg_advisory_xact_lock(hashtextextended(%s,0))", (f"proposal:{scenario['product_id']}:{scenario['warehouse_id']}:{alternative['action']}",))
            self._write('''UPDATE public.agent_action_proposals SET status='obsolete',updated_at=now(),reason='Datos o caducidad cambiaron'
                WHERE product_id=%s AND warehouse_id=%s AND action=%s AND status IN ('pending_approval','approved')
                AND (snapshot_hash<>%s OR expires_at<=now())''',
                (scenario['product_id'], scenario['warehouse_id'], alternative['action'], scenario['snapshot_hash']))
            if self._one('''SELECT id FROM public.agent_action_proposals WHERE product_id=%s AND warehouse_id=%s
                AND action=%s AND status='executed' AND updated_at>now()-%s*INTERVAL '1 hour' ''',
                (scenario['product_id'], scenario['warehouse_id'], alternative['action'], config.cooldown_hours)):
                self.connection.commit()
                return None
            key = digest([rule['id'], rule['current_version'], scenario['snapshot_hash'], alternative])
            plan = {'action': alternative, 'evidence': {'source': 'PostgreSQL inventory/purchase/movement ledger',
                'as_of': datetime.now(timezone.utc).isoformat(), 'period_days': 90, 'snapshot': scenario['observed']},
                'alternatives': scenario['alternatives'], 'reason': reason, 'unit': scenario['unit'],
                'assumptions': scenario['assumptions'], 'limitations': ['No se atribuye causalidad a comparaciones antes/después'],
                'estimated_impact': {'coverage_days': str(scenario['coverage_days']) if scenario['coverage_days'] is not None else None,
                                     'net_benefit': None},
                'requires_approval': True, 'idempotency_key': key, 'objective': config.objective,
                'review_metric': config.objective_metric, 'objective_target': config.objective_target,
                'dependencies': {'replenish':['current_supplier_quote','approval','EUR_budget'],
                                 'transfer':['physical_confirmation','approval','free_stock_and_origin_coverage']}.get(alternative['action'],['current_policy']),
                'forecast_daily': str(dec(scenario['observed']['sold_90']) / 90)}
            proposal = self._one('''INSERT INTO public.agent_action_proposals
                (run_id,rule_id,rule_version,product_id,warehouse_id,action,idempotency_key,plan,snapshot_hash,expires_at,review_at)
                VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,now()+%s*INTERVAL '1 hour',now()+%s*INTERVAL '1 day')
                ON CONFLICT DO NOTHING RETURNING *''',
                (run['id'], rule['id'], rule['current_version'], scenario['product_id'], scenario['warehouse_id'], alternative['action'],
                 key, document(plan), scenario['snapshot_hash'], config.expires_hours, config.review_days))
            if proposal:
                self.event(run['id'], rule['id'], 'proposal', {'proposal_id': proposal['id'], 'plan': plan})
            self.connection.commit()
            return proposal
        except Exception:
            self.connection.rollback()
            raise

    def run_due_rules(self):
        self.ensure_default_rules()
        try:
            self.evaluate_due()
        except Exception:
            self.connection.rollback()
            logger.exception('Outcome review failed; continuing scheduled analysis')
        ids = self._all('''SELECT id FROM public.automation_rules WHERE is_active AND failures<3
            AND (lease_until IS NULL OR lease_until<=now())
            AND (last_run_at IS NULL OR last_run_at+interval_minutes*INTERVAL '1 minute'<=now()) ORDER BY id''')
        self.connection.commit()
        results = []
        for rule in ids:
            try:
                results.append(self.run_rule(rule['id'], 'scheduler'))
            except Exception:
                self.connection.rollback()
                logger.exception('Automation rule %s failed; continuing', rule['id'])
        return results

    def runs(self, limit=50):
        return self._all('''SELECT r.*,a.name AS rule_name,a.code AS rule_code,
            EXTRACT(EPOCH FROM (r.completed_at-r.started_at))*1000 AS latency_ms
            FROM public.automation_runs r JOIN public.automation_rules a ON a.id=r.rule_id ORDER BY r.id DESC LIMIT %s''', (limit,))

    def proposals(self):
        # Compatibility for the existing executive screen; new actions have a separate contract.
        old = self._all('''SELECT p.*,TRIM(pr.name_product) AS product_name,w.name AS warehouse_name
            FROM public.purchase_proposals p JOIN public.productos pr ON pr.pk_product=p.product_id
            JOIN public.inventory_warehouses w ON w.id=p.warehouse_id ORDER BY p.id DESC LIMIT 200''')
        current = self._all('''SELECT p.id,p.product_id,p.warehouse_id,TRIM(pr.name_product) AS product_name,w.name AS warehouse_name,
            p.plan->'action'->>'quantity' AS suggested_qty,p.plan->>'unit' AS base_unit_code,p.status,
            p.plan->>'reason' AS justification,p.created_at FROM public.agent_action_proposals p
            JOIN public.productos pr ON pr.pk_product=p.product_id JOIN public.inventory_warehouses w ON w.id=p.warehouse_id
            WHERE p.action='replenish' ORDER BY p.id DESC LIMIT 200''')
        return [{**p, 'source': 'operational'} for p in current] + [{**p, 'source': 'legacy'} for p in old]

    def action_proposals(self):
        return self._all('''SELECT p.*,TRIM(pr.name_product) AS product_name,w.name AS warehouse_name,
            (SELECT SUM(l.pending_qty) FROM public.purchase_order_lines l
              WHERE l.purchase_order_id=(p.action_result->>'purchase_order_id')::bigint) AS purchase_pending_qty
            FROM public.agent_action_proposals p JOIN public.productos pr ON pr.pk_product=p.product_id
            JOIN public.inventory_warehouses w ON w.id=p.warehouse_id ORDER BY p.id DESC LIMIT 300''')

    def trace(self, run_id):
        return self._all('SELECT * FROM public.automation_events WHERE run_id=%s ORDER BY id', (run_id,))

    def interpret_trace(self, run_id, retry=False):
        run = self._one('''SELECT r.*,a.name AS rule_name,a.code AS rule_code FROM public.automation_runs r
            JOIN public.automation_rules a ON a.id=r.rule_id WHERE r.id=%s''', (run_id,))
        if not run:
            self.connection.rollback()
            raise ValueError('Ejecución no encontrada')
        events = self.trace(run_id)
        proposals = self._all('''SELECT id,status,action,product_id,warehouse_id,updated_at,
            plan->'action' AS calculated_action,action_result FROM public.agent_action_proposals
            WHERE run_id=%s ORDER BY id''', (run_id,))
        # Release the read transaction before contacting a provider. No operational data is written.
        self.connection.rollback()
        return interpret_trace(run,events,proposals,retry=retry)

    def revalidate(self, p):
        rule = self._one('SELECT * FROM public.automation_rules WHERE id=%s FOR UPDATE', (p['rule_id'],))
        config = self.config(rule)
        if self.stopped() or config.simulation or config.mode == 'observation':
            raise ValueError('Operaciones detenidas o regla sin permiso operativo')
        if p['rule_version'] != rule['current_version'] or p['expires_at'] <= datetime.now(timezone.utc):
            raise ValueError('Propuesta caducada o versión obsoleta; vuelve a analizar')
        rows = self.snapshots(config)
        row = next((r for r in rows if r['product_id'] == p['product_id'] and r['warehouse_id'] == p['warehouse_id']), None)
        if not row or digest(row) != p['snapshot_hash']:
            raise ValueError('Los datos cambiaron; vuelve a analizar y aprobar')
        scenario = self.compare(row, rows, config)
        if not scenario['relevant'] or p['plan']['action'] not in scenario['alternatives']:
            # JSON stores decimals/datetimes as strings; alternatives contain strings/numbers only.
            raise ValueError('La alternativa ya no cumple las condiciones')
        return config, row

    def decide(self, proposal_id, approve, reason, actor):
        try:
            p = self._one('SELECT * FROM public.agent_action_proposals WHERE id=%s FOR UPDATE', (proposal_id,))
            if not p or p['status'] != 'pending_approval':
                raise ValueError('Propuesta no pendiente')
            if approve:
                self.revalidate(p)
                self.event(p['run_id'],p['rule_id'],'validation',{'proposal_id':p['id'],'phase':'approval',
                    'result':'passed','checks':['snapshot','current_policy','expiry','current_alternatives']})
            self._write('''UPDATE public.agent_action_proposals SET status=%s,approved_by=%s,approved_at=now(),reason=%s,updated_at=now()
                WHERE id=%s''', ('approved' if approve else 'rejected', actor, reason, proposal_id))
            self.event(p['run_id'], p['rule_id'], 'approval' if approve else 'rejection', {'proposal_id': proposal_id, 'actor': actor, 'reason': reason})
            self.connection.commit()
            return {'id': proposal_id, 'status': 'approved' if approve else 'rejected'}
        except Exception:
            self.connection.rollback()
            raise

    def act(self, proposal_id, actor, automatic=False, physical_confirmed=False, quote=None):
        try:
            # Global policy row also serializes budget checks across all rules/processes.
            self._one('SELECT * FROM public.automation_control WHERE id=1 FOR UPDATE')
            p = self._one('SELECT * FROM public.agent_action_proposals WHERE id=%s FOR UPDATE', (proposal_id,))
            if not p:
                raise ValueError('Propuesta inexistente')
            if p['status'] == 'executed':
                self.connection.rollback()
                return p['action_result']
            if p['status'] != ('pending_approval' if automatic else 'approved'):
                raise ValueError('La acción necesita aprobación vigente')
            if p['action'] != 'transfer':
                AtomicInventory(self.connection)._lock_stock(p['product_id'], p['warehouse_id'])
            config, row = self.revalidate(p)
            if automatic and (config.mode != 'limited_auto' or p['action'] not in config.allowed_actions):
                raise PermissionError('Tipo de acción no autorizado automáticamente')
            self.event(p['run_id'],p['rule_id'],'validation',{'proposal_id':p['id'],'phase':'execution',
                'checks':['stock_lock','snapshot','rule_version','expiry','autonomy'],'result':'passed'})
            action = p['plan']['action']
            qty = dec(action['quantity'])
            if p['action'] == 'suspend_reorder':
                # A suppression is scoped to this decision entity; it cannot change business permissions.
                result = {'kind': 'reorder_suppression', 'product_id': p['product_id'], 'warehouse_id': p['warehouse_id'],
                          'until': (datetime.now(timezone.utc) + timedelta(days=config.review_days)).isoformat(), 'cost': '0'}
            elif p['action'] == 'transfer':
                if automatic or not physical_confirmed:
                    raise ValueError('Exige confirmación humana del traslado físico')
                if qty <= 0:
                    raise ValueError('Cantidad inválida')
                # Stock locks and current revalidation prevent consuming free stock below coverage.
                inventory = AtomicInventory(self.connection)
                for wid in sorted([action['source_warehouse_id'], action['destination_warehouse_id']]):
                    inventory._lock_stock(p['product_id'], wid)
                self.revalidate(p)
                result = inventory.transfer_stock({'operation_key': p['idempotency_key'],
                    'source_warehouse_id': action['source_warehouse_id'], 'destination_warehouse_id': action['destination_warehouse_id'],
                    'user_name': actor, 'reason': 'Confirmación física de propuesta ' + str(p['id']),
                    'lines': [{'product_id': p['product_id'], 'quantity': qty, 'unit_code': p['plan']['unit']}]})
                result['logistics_cost'] = None
            elif p['action'] == 'replenish':
                if not quote or automatic:
                    raise ValueError('Compra condicionada a oferta vigente confirmada; no disponible automáticamente')
                if qty <= 0 or qty > Decimal('1000000000'):
                    raise ValueError('Cantidad fuera de rango')
                # Only a human can supply and attest a current offer. Never infer a supplier or a price from prose.
                supplier = self._one('SELECT id FROM public.inventory_suppliers WHERE id=%s', (quote.supplier_id,))
                currency = self._one('SELECT id,iso_code FROM public.inventory_currencies WHERE iso_code=%s', (quote.currency_code,))
                if not supplier or not currency or quote.valid_until <= datetime.now(timezone.utc):
                    raise ValueError('Oferta, proveedor o moneda inválidos')
                if quote.currency_code != 'EUR':
                    raise ValueError('Presupuestos operativos en EUR: se requiere oferta en EUR')
                cost = qty * quote.unit_price
                spent = self._one('''SELECT SUM((action_result->>'cost')::numeric) AS spent FROM public.agent_action_proposals
                    WHERE status='executed' AND action='replenish'
                    AND updated_at>=(date_trunc('day',now() AT TIME ZONE 'UTC') AT TIME ZONE 'UTC')''')['spent'] or 0
                if cost > config.per_action_budget or cost + dec(spent) > config.daily_budget:
                    raise ValueError('Presupuesto por operación o diario excedido')
                order = self._one('''INSERT INTO public.purchase_orders(supplier_id,warehouse_id,purchase_order_number,status,user_name,notes)
                    VALUES(%s,%s,%s,'emitido',%s,%s) RETURNING id''',
                    (supplier['id'], p['warehouse_id'], 'AUTO-' + str(p['id']), actor, quote.reference))
                self._write('''INSERT INTO public.purchase_order_lines(purchase_order_id,product_id,requested_qty,pending_qty,
                    base_unit_id,currency_id,currency_code,unit_price,exchange_rate,exchange_rate_date)
                    VALUES(%s,%s,%s,%s,%s,%s,'EUR',%s,1,CURRENT_DATE)''',
                    (order['id'], p['product_id'], qty, qty, row['base_unit_id'], currency['id'], quote.unit_price))
                result = {'purchase_order_id': order['id'], 'status': 'emitido', 'cost': str(cost),
                          'currency': 'EUR', 'quote': quote.model_dump(mode='json'), 'physical_receipt': False}
            else:
                raise ValueError('Acción condicionada: integración o condiciones verificadas no disponibles')
            self._write('''UPDATE public.agent_action_proposals SET status='executed',executed_by=%s,action_result=%s,
                review_at=now()+%s*INTERVAL '1 day',updated_at=now() WHERE id=%s''',
                (actor, document(result), config.review_days, proposal_id))
            self.event(p['run_id'], p['rule_id'], 'execution', {'proposal_id': p['id'], 'actor': actor,
                'automatic': automatic, 'physical_confirmed': physical_confirmed, 'result': result})
            self.connection.commit()
            return result
        except Exception as exc:
            self.connection.rollback()
            if 'p' in locals() and p:
                self.event(p['run_id'], p['rule_id'], 'policy_blocked', {'proposal_id': proposal_id, 'actor': actor, 'reason': str(exc)[:500]})
                self.connection.commit()
            raise

    def evaluate_due(self):
        count = 0
        due = self._all("SELECT * FROM public.agent_action_proposals WHERE status='executed' AND review_at<=now() AND evaluation IS NULL FOR UPDATE SKIP LOCKED")
        for p in due:
            observations = self._one('''SELECT
                COALESCE(SUM(CASE WHEN movement_type='dispatch' THEN -quantity_signed ELSE 0 END),0) AS sold,
                COALESCE(SUM(CASE WHEN movement_type='return' THEN quantity_signed ELSE 0 END),0) AS returned
                FROM public.inventory_movements WHERE product_id=%s AND warehouse_id=%s AND created_at>=%s AND created_at<=%s''',
                (p['product_id'], p['warehouse_id'], p['updated_at'], p['review_at']))
            days = dec((p['review_at'] - p['updated_at']).total_seconds()) / 86400
            expected = dec(p['plan']['forecast_daily']) * days
            target = p['plan'].get('objective_target')
            evaluation = {'period_start': p['updated_at'], 'period_end': p['review_at'], 'observed': observations,
                'expected_dispatch': expected, 'forecast_metrics': forecast_metrics([(expected, observations['sold'])]),
                'objective_met': observations['sold'] >= dec(target) if target is not None else None,
                'objective_target':target,'objective_metric':'confirmed_dispatch_qty',
                'objective_definition':'Unidades despachadas confirmadas del periodo >= umbral configurado; no mide demanda perdida ni causalidad',
                'net_benefit': None, 'stockouts': None, 'realized_margin': None,
                'method': 'Comparación descriptiva de despachos contra media histórica; demanda censurada y causalidad no evaluables',
                'correct_decision_definition': 'Requiere objetivo y disponibilidad observables con costes completos; aún no evaluable',
                'reliability': 'Evidencia insuficiente'}
            self._write('UPDATE public.agent_action_proposals SET evaluation=%s WHERE id=%s', (document(evaluation), p['id']))
            self.event(p['run_id'], p['rule_id'], 'evaluation', {'proposal_id': p['id'], 'evaluation': evaluation})
            count += 1
        self.connection.commit()
        return count

    def metrics(self, rule_id=None, days=30, version=None, model=None):
        run_filter = '''started_at>=now()-%s*INTERVAL '1 day' AND (%s IS NULL OR rule_id=%s)
            AND (%s IS NULL OR rule_version=%s) AND (%s IS NULL OR result->'ai'->>'model'=%s)'''
        params = (days, rule_id, rule_id, version, version, model, model)
        summary = self._one('''SELECT COUNT(*) AS executions,
            COUNT(*) FILTER(WHERE status IN ('completed','degraded')) AS technical_successes,
            COUNT(*) FILTER(WHERE status='degraded') AS degraded,
            COUNT(*) FILTER(WHERE status='failed') AS failures,
            percentile_cont(0.5) WITHIN GROUP(ORDER BY EXTRACT(EPOCH FROM(completed_at-started_at))*1000) AS median_ms,
            percentile_cont(0.95) WITHIN GROUP(ORDER BY EXTRACT(EPOCH FROM(completed_at-started_at))*1000) AS p95_ms
            FROM public.automation_runs WHERE ''' + run_filter, params)
        n = summary['executions']
        summary['technical_success_rate'] = summary['technical_successes'] / n if n else None
        summary['events'] = self._all('''SELECT e.phase,COUNT(*) AS count FROM public.automation_events e
            WHERE e.run_id IN (SELECT id FROM public.automation_runs WHERE ''' + run_filter + ''') GROUP BY e.phase''', params)
        summary['decisions'] = self._all('''SELECT action,status,COUNT(*) AS count,COUNT(evaluation) AS evaluated,
            COUNT(*) FILTER(WHERE evaluation->>'objective_met' IN ('true','false')) AS objective_evaluable,
            COUNT(*) FILTER(WHERE evaluation->>'objective_met'='true') AS objective_met
            FROM public.agent_action_proposals WHERE run_id IN
            (SELECT id FROM public.automation_runs WHERE ''' + run_filter + ''') GROUP BY action,status''', params)
        summary['series'] = self._all('''SELECT DATE(started_at AT TIME ZONE 'UTC') AS day,COUNT(*) AS executions,
            COUNT(*) FILTER(WHERE status='failed') AS failures,COUNT(*) FILTER(WHERE status='degraded') AS degraded,
            percentile_cont(0.5) WITHIN GROUP(ORDER BY EXTRACT(EPOCH FROM(completed_at-started_at))*1000) AS median_ms
            FROM public.automation_runs WHERE ''' + run_filter + ''' GROUP BY 1 ORDER BY 1''', params)
        counts = {e['phase']: e['count'] for e in summary['events']}
        summary['schema_compliance_rate'] = counts.get('schema_valid', 0) / counts['model_call'] if counts.get('model_call') else None
        summary['tool_calls'] = counts.get('tools', 0)
        summary['policy_blocks'] = counts.get('policy_blocked', 0)
        summary['provider_failures'] = counts.get('provider_failure', 0)
        summary['agent_version'] = 'operational-v1'
        summary['rule_version'] = version
        summary['model'] = model
        summary.update({'period_days': days, 'tokens': None, 'cost': None, 'cost_per_task': None,
                        'objective_success_rate': None, 'reliability': 'Evidencia insuficiente',
                        'limitations': 'Éxito técnico incluye modo degradado. No mide acierto. Coste y tokens no disponibles en generate_ai.'})
        evaluable = sum(d['objective_evaluable'] for d in summary['decisions'])
        met = sum(d['objective_met'] for d in summary['decisions'])
        summary['objective_evaluable'] = evaluable
        summary['objective_success_rate'] = met / evaluable if evaluable else None
        usage = self._one('''SELECT SUM((detail->'ai'->'usage'->>'input_tokens')::numeric) AS input_tokens,
            SUM((detail->'ai'->'usage'->>'output_tokens')::numeric) AS output_tokens,
            COUNT(*) FILTER(WHERE detail->'ai'->'usage'->>'input_tokens' IS NOT NULL) AS metered_calls
            FROM public.automation_events WHERE phase='schema_valid' AND run_id IN
            (SELECT id FROM public.automation_runs WHERE ''' + run_filter + ''')''', params)
        summary['usage'] = usage
        if usage['input_tokens'] is not None and usage['output_tokens'] is not None:
            summary['tokens'] = usage['input_tokens'] + usage['output_tokens']
        summary['limitations'] = ('Éxito técnico incluye modo degradado. No mide acierto. Tokens corresponden solo a llamadas con uso informado; '
                                  'el proveedor no facilita coste monetario. Datos anteriores a esta versión pueden carecer de eventos.')
        scope = RuleConfig(max_entities=100)
        if rule_id:
            rule = self._one('SELECT * FROM public.automation_rules WHERE id=%s', (rule_id,))
            if rule:
                scope = self.config(rule)
        stock_rows = self.snapshots(scope)
        summary['business_snapshot'] = {'as_of':datetime.now(timezone.utc), 'period_days':90,
            'scope_limit':scope.max_entities, 'comparison_reference':None, 'realized_margin':None,
            'historical_stockouts':None, 'inventory_turnover':None, 'rows':[]}
        for row in stock_rows:
            free = dec(row['physical_qty'])-dec(row['reserved_qty'])
            daily = dec(row['sold_90'])/90
            summary['business_snapshot']['rows'].append({'product_id':row['product_id'],'warehouse_id':row['warehouse_id'],
                'product_name':row['product_name'],'unit':row['unit'],'available':free,'unavailable_now':free<=0,
                'coverage_days':free/daily if daily else None,
                'historical_cost_capital':dec(row['physical_qty'])*dec(row['historical_cost']) if row['historical_cost'] is not None else None,
                'stock_updated_at':row['stock_updated_at'],'dispatch_90_days':row['sold_90']})
        return summary
