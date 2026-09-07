from fastapi import APIRouter, Depends, HTTPException

from DataBaseManagement.dbConectionPostgres import get_db_products
from DataBaseManagement.schemasAgents import CommercialContentRequest, CustomerSupportRequest, MarketIntelligenceRequest, ProductAnalysisRequest
from commercial_agent_service import CommercialAgentError, CommercialAgentService

router = APIRouter(prefix="/agents", tags=["commercial agents"])


def _service(db=Depends(get_db_products)) -> CommercialAgentService:
    return CommercialAgentService(db)


def _call(fn):
    try:
        return fn()
    except CommercialAgentError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/sales/forecast")
def sales_forecast(payload: ProductAnalysisRequest, service: CommercialAgentService = Depends(_service)):
    return _call(lambda: service.sales_forecast(payload.product_id, payload.horizon_days))


@router.get("/financial/summary")
def financial_summary(product_id: int | None = None, service: CommercialAgentService = Depends(_service)):
    return service.financial_summary(product_id)


@router.post("/competition")
def competition(payload: ProductAnalysisRequest, service: CommercialAgentService = Depends(_service)):
    return _call(lambda: service.competition(payload.product_id, payload.country))


@router.post("/market-intelligence")
def market_intelligence(payload: MarketIntelligenceRequest, service: CommercialAgentService = Depends(_service)):
    return service.market_intelligence(payload.term, payload.country)


@router.post("/commercial/content")
def commercial_content(payload: CommercialContentRequest, service: CommercialAgentService = Depends(_service)):
    return _call(lambda: service.commercial_content(payload.product_id, payload.channel))


@router.post("/customer-support")
def customer_support(payload: CustomerSupportRequest, service: CommercialAgentService = Depends(_service)):
    return _call(lambda: service.support_answer(payload.question, payload.product_id))


@router.get("/risks")
def risks(service: CommercialAgentService = Depends(_service)):
    return service.risks()
