"""Restricted business rule language and deterministic scenario calculations."""
from decimal import Decimal, ROUND_CEILING
from typing import Literal, Annotated
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field, model_validator
from rules_policy import RULE_OBJECTIVES, validate_rule_objective
import json
import re

Action = Literal['wait', 'replenish', 'transfer', 'suspend_reorder', 'promotion', 'supplier_return']
PositiveId = Annotated[int, Field(gt=0, strict=True)]


class Contract(BaseModel):
    model_config = ConfigDict(extra='forbid', allow_inf_nan=False, validate_default=True)


class Condition(Contract):
    field: Literal['available', 'pending', 'sold_90', 'coverage_days', 'days_without_sales']
    operator: Literal['lt', 'lte', 'gt', 'gte', 'eq']
    value: Decimal = Field(ge=0, le=1000000000)


class Conditions(Contract):
    mode: Literal['all', 'any'] = 'all'
    items: list[Condition] = Field(default_factory=list, max_length=12)

    @model_validator(mode='after')
    def consistent(self):
        if self.mode == 'all':
            bounds = {}
            for c in self.items:
                lo, hi = bounds.get(c.field, (None, None))
                if c.operator in ('gt', 'gte', 'eq'):
                    bound = (c.value, c.operator == 'gt')
                    lo = max(lo, bound) if lo else bound
                if c.operator in ('lt', 'lte', 'eq'):
                    bound = (c.value, c.operator == 'lt')
                    hi = min(hi, bound, key=lambda b: (b[0], not b[1])) if hi else bound
                if lo and hi and (lo[0] > hi[0] or (lo[0] == hi[0] and (lo[1] or hi[1]))):
                    raise ValueError('Condiciones contradictorias')
                bounds[c.field] = (lo, hi)
        return self


class RuleConfig(Contract):
    kind: Literal['stock_reorder_proposals', 'stagnant_stock', 'daily_inventory_report', 'risk_alerts'] = 'stock_reorder_proposals'
    objective: str = Field(default='Reducir roturas manteniendo cobertura y capital', min_length=3, max_length=500)
    objective_metric: Literal['confirmed_dispatch_qty'] = 'confirmed_dispatch_qty'
    objective_target: Decimal | None = Field(default=None, ge=0, le=1000000000)
    mode: Literal['observation', 'assisted', 'limited_auto'] = 'assisted'
    simulation: bool = False
    interval_minutes: int = Field(default=1440, ge=15, le=525600)
    timezone: str = 'Europe/Madrid'
    window_start_hour: int = Field(default=0, ge=0, le=23)
    window_end_hour: int = Field(default=24, ge=1, le=24)
    product_ids: list[PositiveId] = Field(default_factory=list, max_length=100)
    warehouse_ids: list[PositiveId] = Field(default_factory=list, max_length=100)
    target_days: Decimal = Field(default=30, ge=1, le=365)
    safety_qty: Decimal = Field(default=0, ge=0, le=1000000)
    minimum_order: Decimal = Field(default=0, ge=0, le=1000000, decimal_places=4)
    order_multiple: Decimal = Field(default=1, gt=0, le=1000000, decimal_places=4)
    lead_days: Decimal | None = Field(default=None, ge=0, le=365)
    stagnant_days: int = Field(default=90, ge=7, le=730)
    maximum_coverage_days: Decimal = Field(default=120, ge=1, le=730)
    origin_min_days: Decimal = Field(default=30, ge=1, le=365)
    minimum_margin_percent: Decimal = Field(default=20, ge=0, lt=100)
    per_action_budget: Decimal = Field(default=0, ge=0, le=100000000)
    daily_budget: Decimal = Field(default=0, ge=0, le=100000000)
    allowed_actions: list[Action] = Field(default_factory=list, max_length=6)
    expires_hours: int = Field(default=24, ge=1, le=168)
    cooldown_hours: int = Field(default=24, ge=1, le=720)
    review_days: int = Field(default=30, ge=1, le=365)
    max_entities: int = Field(default=30, ge=1, le=100)
    # Legacy higher budgets remain readable; direct selection uses at most one call and no tools.
    max_model_calls: int = Field(default=1, ge=0, le=3)
    max_tool_calls: int = Field(default=0, ge=0, le=10)
    max_seconds: int = Field(default=120, ge=10, le=240)
    # Without metered provider costs only local inference is permitted by default.
    allow_unmetered_paid_ai: bool = False
    conditions: Conditions = Field(default_factory=Conditions)

    @model_validator(mode='after')
    def validate_policy(self):
        if 'objective' not in self.model_fields_set:
            self.objective = RULE_OBJECTIVES[self.kind][0]
        try:
            ZoneInfo(self.timezone)
        except (ZoneInfoNotFoundError, ValueError) as exc:
            raise ValueError('Zona horaria desconocida') from exc
        if self.window_start_hour >= self.window_end_hour:
            raise ValueError('Ventana de ejecución vacía')
        if any(type(i) is not int or i <= 0 for i in self.product_ids + self.warehouse_ids):
            raise ValueError('Identificadores inválidos')
        if self.per_action_budget > self.daily_budget:
            raise ValueError('Presupuesto por acción superior al diario')
        if self.mode != 'limited_auto' and self.allowed_actions:
            raise ValueError('Acciones automáticas requieren modo automático limitado')
        if self.kind in ('daily_inventory_report', 'risk_alerts'):
            if self.mode == 'limited_auto' or self.allowed_actions:
                raise ValueError('Los informes y alertas solo observan datos; no admiten acciones automáticas')
            if self.conditions.items:
                raise ValueError('Las condiciones de stock solo se aplican a reposición y stock estancado; usa filtros de producto y almacén para informes')
        # Physical operations and external publication always need separate confirmation.
        if any(a not in ('replenish', 'suspend_reorder') for a in self.allowed_actions):
            raise ValueError('Esta acción requiere confirmación operativa específica')
        return self


class RuleDraft(Contract):
    name: str = Field(min_length=3, max_length=160)
    description: str = Field(default='', max_length=2000)
    reason: str = Field(min_length=3, max_length=500)
    expected_version: int = Field(default=0, ge=0)
    config: RuleConfig

    @model_validator(mode='after')
    def objective_in_scope(self):
        validate_rule_objective(self.config.kind, self.config.objective)
        return self


class ToolCall(Contract):
    name: Literal['product_snapshot', 'compare_scenarios']
    product_id: int = Field(gt=0, strict=True)
    warehouse_id: int = Field(gt=0, strict=True)


class Choice(Contract):
    product_id: int = Field(gt=0, strict=True)
    warehouse_id: int = Field(gt=0, strict=True)
    action: Action
    reason: str = Field(min_length=3, max_length=700)


class ModelTurn(Contract):
    tools: list[ToolCall] = Field(default_factory=list, max_length=0)
    choices: list[Choice] = Field(default_factory=list, max_length=100)
    finish_reason: str = Field(min_length=3, max_length=500)

def model_turn_schema():
    """Derive the provider schema from the same contract validated locally."""
    schema = ModelTurn.model_json_schema()
    def require_fields(node):
        if isinstance(node, dict):
            node.pop('default', None)
            if node.get('type') == 'object':
                node['required'] = list(node.get('properties', {}))
                node['additionalProperties'] = False
            for value in node.values():
                require_fields(value)
        elif isinstance(node, list):
            for value in node:
                require_fields(value)
    require_fields(schema)
    return schema


def parse_model_turn(response: str):
    """Accept pure JSON or one complete Markdown fence, never extract arbitrary prose."""
    if not isinstance(response, str):
        raise ValueError('La respuesta del modelo debe ser texto JSON')
    text = response.strip()
    fenced = re.fullmatch(r'```(?:json)?\s*\n([\s\S]*?)\n```', text, flags=re.IGNORECASE)
    if fenced:
        text = fenced.group(1).strip()
    def unique_object(pairs):
        obj = {}
        for key, value in pairs:
            if key in obj:
                raise ValueError('Clave JSON duplicada en la respuesta del modelo')
            obj[key] = value
        return obj
    def reject_constant(value):
        raise ValueError('Constante JSON no válida: ' + value)
    try:
        data = json.loads(text, object_pairs_hook=unique_object, parse_constant=reject_constant)
    except json.JSONDecodeError as exc:
        raise ValueError(f'Respuesta JSON no válida: {exc.msg} (línea {exc.lineno}, columna {exc.colno})') from exc
    return ModelTurn.model_validate(data), fenced is not None


class Quote(Contract):
    supplier_id: PositiveId
    currency_code: Literal['EUR'] = 'EUR'
    unit_price: Decimal = Field(gt=0, le=100000000, decimal_places=4)
    valid_until: datetime
    reference: str = Field(min_length=3, max_length=500)

    @model_validator(mode='after')
    def aware(self):
        if self.valid_until.tzinfo is None:
            raise ValueError('La caducidad requiere zona horaria')
        return self


class ProposalDecision(Contract):
    approve: bool
    reason: str = Field(min_length=3, max_length=500)


class ActionRequest(Contract):
    physical_confirmed: bool = False
    quote: Quote | None = None


class StopRequest(Contract):
    stopped: bool


class PhysicalReceipt(Contract):
    operation_key: str = Field(min_length=6, max_length=60, pattern=r'^[a-zA-Z0-9_-]+$')
    physical_confirmed: bool
    quantity: Decimal = Field(gt=0, le=1000000000, decimal_places=4)
    reason: str = Field(min_length=3, max_length=500)


def dec(value):
    result = Decimal(str(value))
    if not result.is_finite():
        raise ValueError('Cantidad no finita')
    return result


def replenishment(row, config: RuleConfig):
    available = dec(row['physical_qty']) - dec(row['reserved_qty'])
    daily = dec(row['sold_90']) / Decimal(90)
    target = max(dec(row['reorder_point']), daily * (config.target_days + (config.lead_days or 0)) + config.safety_qty)
    need = max(Decimal(0), target - available - dec(row['pending']))
    if need:
        need = (max(need, config.minimum_order, dec(row['reorder_quantity'])) / config.order_multiple).to_integral_value(rounding=ROUND_CEILING) * config.order_multiple
    return need.quantize(Decimal('0.0001'))


def conditions_match(values, group: Conditions):
    def check(c):
        value = values.get(c.field)
        if value is None:
            return False
        left, right = dec(value), c.value
        return {'lt': left < right, 'lte': left <= right, 'gt': left > right, 'gte': left >= right, 'eq': left == right}[c.operator]
    results = [check(c) for c in group.items]
    return (all(results) if group.mode == 'all' else any(results)) if results else True


def forecast_metrics(pairs):
    if not pairs:
        return {'n': 0, 'mae': None, 'wape': None, 'bias': None}
    errors = [dec(predicted) - dec(actual) for predicted, actual in pairs]
    denominator = sum((abs(dec(actual)) for _, actual in pairs), Decimal(0))
    return {'n': len(pairs), 'mae': sum(map(abs, errors)) / len(pairs),
            'wape': sum(map(abs, errors)) / denominator if denominator else None,
            'bias': sum(errors) / len(pairs)}
