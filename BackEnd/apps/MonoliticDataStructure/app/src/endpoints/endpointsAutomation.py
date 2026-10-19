"""Session and database permission checks apply independently of API key access."""
from typing import Annotated
from fastapi import APIRouter, Depends, Header, HTTPException, Query
from psycopg2 import IntegrityError
from DataBaseManagement.dbConectionPostgres import get_db_products
from automation_service import AutomationService
from automation_contracts import RuleDraft, RuleConfig, ProposalDecision, ActionRequest, StopRequest, PhysicalReceipt
from automation_purchasing import receive_purchase
from inventory_service import InventoryError
from rules_policy import RULE_OBJECTIVES, validate_rule_objective
from .endpointsSales import sales_user

router = APIRouter(prefix='/automation', tags=['Agent control'])


def service(db=Depends(get_db_products), authorization: str | None = Header(default=None)):
    user = sales_user(db, authorization)
    svc = AutomationService(db)
    permissions = svc._one('SELECT automation_permissions FROM public.users WHERE id=%s', (user['id'],))
    svc.user = {**user, **permissions}
    return svc


Service = Annotated[AutomationService, Depends(service)]


def permit(svc, permission):
    if permission not in svc.user.get('automation_permissions', []):
        raise HTTPException(403, 'No tienes permiso de automatización: ' + permission)


def execute(fn, *args, **kwargs):
    try:
        return fn(*args, **kwargs)
    except PermissionError as exc:
        raise HTTPException(403, str(exc)) from exc
    except (ValueError, InventoryError) as exc:
        raise HTTPException(409, str(exc)) from exc
    except IntegrityError as exc:
        raise HTTPException(409, 'Conflicto concurrente; recarga los datos') from exc


@router.get('/control')
def control(svc: Service):
    permit(svc, 'read')
    return {'stopped': svc.stopped(), 'permissions': svc.user['automation_permissions']}


@router.put('/control')
def stop(payload: StopRequest, svc: Service):
    permit(svc, 'activate')
    return svc.stop(payload.stopped, svc.user['email'])


@router.get('/rules')
def rules(svc: Service):
    permit(svc, 'read')
    return svc.rules()


@router.get('/objectives')
def objectives(svc: Service):
    permit(svc, 'read')
    return RULE_OBJECTIVES


@router.get('/scope-defaults')
def scope_defaults(svc: Service):
    permit(svc,'read')
    return svc.scope_defaults()


@router.get('/scope-products')
def scope_products(svc: Service, ids: str = Query(default='',max_length=1400)):
    permit(svc,'read')
    try:
        selected = [int(value.strip()) for value in ids.split(',')] if ids.strip() else []
    except ValueError:
        raise HTTPException(422,'Indica IDs de productos separados por comas')
    return execute(svc.scope_product_options,selected)


@router.post('/rules')
def create(payload: RuleDraft, svc: Service):
    permit(svc, 'edit')
    return execute(svc.save_rule, payload, svc.user['email'], can_authorize='authorize' in svc.user['automation_permissions'])


@router.put('/rules/{rule_id}')
def update(rule_id: int, payload: RuleDraft, svc: Service):
    permit(svc, 'edit')
    return execute(svc.save_rule, payload, svc.user['email'], rule_id, 'authorize' in svc.user['automation_permissions'])


@router.get('/rules/{rule_id}/versions')
def versions(rule_id: int, svc: Service):
    permit(svc, 'read')
    return svc.versions(rule_id)


@router.post('/simulate')
def simulate(payload: RuleConfig, svc: Service):
    permit(svc, 'edit')
    execute(validate_rule_objective, payload.kind, payload.objective)
    return execute(svc.simulate, payload)


@router.get('/runs')
def runs(svc: Service, limit: int = Query(default=100, ge=1, le=200)):
    permit(svc, 'read')
    return svc.runs(limit)


@router.get('/runs/{run_id}/events')
def trace(run_id: int, svc: Service):
    permit(svc, 'read')
    return svc.trace(run_id)


@router.post('/runs/{run_id}/interpretation')
def interpretation(run_id: int, svc: Service, retry: bool = False):
    permit(svc, 'read')
    return execute(svc.interpret_trace, run_id, retry)


@router.get('/proposals')
def proposals(svc: Service):
    permit(svc, 'read')
    return svc.action_proposals()


@router.post('/proposals/{proposal_id}/decision')
def decision(proposal_id: int, payload: ProposalDecision, svc: Service):
    permit(svc, 'approve')
    return execute(svc.decide, proposal_id, payload.approve, payload.reason, svc.user['email'])


@router.post('/proposals/{proposal_id}/execute')
def act(proposal_id: int, payload: ActionRequest, svc: Service):
    permit(svc, 'execute')
    return execute(svc.act, proposal_id, svc.user['email'], physical_confirmed=payload.physical_confirmed, quote=payload.quote)


@router.post('/evaluate')
def evaluate(svc: Service):
    permit(svc, 'read')
    return {'evaluated': svc.evaluate_due()}


@router.post('/proposals/{proposal_id}/receipt')
def receipt(proposal_id: int, payload: PhysicalReceipt, svc: Service):
    permit(svc, 'execute')
    return execute(receive_purchase, svc, proposal_id, payload, svc.user['email'])


@router.get('/metrics')
def metrics(svc: Service, rule_id: int | None = Query(default=None, gt=0), days: int = Query(default=30, ge=1, le=365),
            version: int | None = Query(default=None, ge=0), model: str | None = Query(default=None, max_length=120)):
    permit(svc, 'read')
    return svc.metrics(rule_id, days, version, model)
