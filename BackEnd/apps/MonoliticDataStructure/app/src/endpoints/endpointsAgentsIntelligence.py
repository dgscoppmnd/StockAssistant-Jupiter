from fastapi import APIRouter, Depends, HTTPException

from DataBaseManagement.dbConectionPostgres import get_db_products
from DataBaseManagement.schemasAgents import PurchaseRecommendationRequest, ReviewBatchRequest
from agent_service import AgentService

router = APIRouter(prefix="/agents", tags=["agents"])


def _service(db=Depends(get_db_products)) -> AgentService:
    return AgentService(db)


@router.get("/sources/status")
def source_statuses(service: AgentService = Depends(_service)):
    return {"sources": service.source_statuses()}


@router.get("/stock/alerts")
def stock_alerts(service: AgentService = Depends(_service)):
    return service.stock_alerts()


@router.post("/purchasing/recommendations")
def purchase_recommendation(payload: PurchaseRecommendationRequest, service: AgentService = Depends(_service)):
    try:
        return service.purchase_recommendation(payload.product_id, payload.country, payload.language)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/reviews/batches")
def process_review_batch(payload: ReviewBatchRequest, service: AgentService = Depends(_service)):
    return service.process_review_batch(payload.product_id, payload.source, [item.model_dump(mode="json") for item in payload.reviews], payload.country, payload.currency)
