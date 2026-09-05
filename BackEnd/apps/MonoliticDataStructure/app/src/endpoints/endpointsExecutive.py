from fastapi import APIRouter, Depends, HTTPException, Query

from DataBaseManagement.dbConectionPostgres import get_db_products
from DataBaseManagement.schemasAgents import AutomationStateRequest, ExecutiveRequest
from executive_service import AutomationService, ExecutiveService

router = APIRouter(prefix="/executive", tags=["executive"])


def _executive(db=Depends(get_db_products)) -> ExecutiveService:
    return ExecutiveService(db)


def _automation(db=Depends(get_db_products)) -> AutomationService:
    return AutomationService(db)


@router.post("/query")
def executive_query(payload: ExecutiveRequest, service: ExecutiveService = Depends(_executive)):
    try:
        return service.execute(payload.question, payload.product_id, payload.agent)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/decisions")
def decisions(limit: int = Query(default=50, ge=1, le=200), service: ExecutiveService = Depends(_executive)):
    return service.decisions(limit)


@router.get("/automations")
def automation_rules(service: AutomationService = Depends(_automation)):
    return service.rules()


@router.put("/automations/{rule_id}")
def update_automation(rule_id: int, payload: AutomationStateRequest, service: AutomationService = Depends(_automation)):
    try:
        return service.set_rule_active(rule_id, payload.is_active)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/automations/{rule_id}/run")
def run_automation(rule_id: int, service: AutomationService = Depends(_automation)):
    try:
        return service.run_rule(rule_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/automations/runs")
def automation_runs(limit: int = Query(default=50, ge=1, le=200), service: AutomationService = Depends(_automation)):
    return service.runs(limit)


@router.get("/purchase-proposals")
def purchase_proposals(service: AutomationService = Depends(_automation)):
    return service.proposals()
