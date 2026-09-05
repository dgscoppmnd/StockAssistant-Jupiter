import logging

from fastapi import APIRouter, Depends, HTTPException, Query, status

from DataBaseManagement.dbConectionPostgres import get_db_products
from DataBaseManagement.schemasInventory import (
    CancelSalesOrderRequest,
    DashboardResponse,
    ExecutiveDashboardResponse,
    DispatchRequest,
    InventoryMovementResponse,
    InventoryOperationResponse,
    ProductInventoryConfigRequest,
    ProductInventoryConfigResponse,
    ReceiptConfirmRequest,
    ReservationRequest,
    ReturnRequest,
    StockView,
    TransferRequest,
    WarehouseCreate,
    WarehouseResponse,
)
from inventory_service import InventoryError, InventoryService

router = APIRouter(prefix="/inventory", tags=["inventory"])
logger = logging.getLogger("api.endpointsInventory")


def _service(db=Depends(get_db_products)) -> InventoryService:
    return InventoryService(db)


@router.get("/dashboard", response_model=DashboardResponse)
def inventory_dashboard(service: InventoryService = Depends(_service)):
    return service.get_dashboard()


@router.get("/executive-dashboard", response_model=ExecutiveDashboardResponse)
def executive_inventory_dashboard(
    period_days: int = Query(default=30, ge=7, le=365),
    service: InventoryService = Depends(_service),
):
    return service.get_executive_dashboard(period_days=period_days)


@router.get("/warehouses", response_model=list[WarehouseResponse])
def list_warehouses(service: InventoryService = Depends(_service)):
    return service.list_warehouses()


@router.post("/warehouses", response_model=WarehouseResponse, status_code=status.HTTP_201_CREATED)
def create_warehouse(payload: WarehouseCreate, service: InventoryService = Depends(_service)):
    try:
        return service.create_warehouse(payload.code, payload.name, payload.description, payload.is_active)
    except InventoryError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc


@router.get("/stock", response_model=list[StockView])
def list_stock(service: InventoryService = Depends(_service)):
    return service.list_stock()


@router.get("/movements", response_model=list[InventoryMovementResponse])
def list_movements(limit: int = Query(default=100, ge=1, le=500), service: InventoryService = Depends(_service)):
    return service.list_movements(limit=limit)


@router.put("/products/config", response_model=ProductInventoryConfigResponse)
def configure_product(payload: ProductInventoryConfigRequest, service: InventoryService = Depends(_service)):
    try:
        return service.configure_product(
            product_id=payload.product_id,
            base_unit_code=payload.base_unit_code,
            reorder_point=payload.reorder_point,
            reorder_quantity=payload.reorder_quantity,
            allow_negative_stock=payload.allow_negative_stock,
        )
    except InventoryError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc


@router.post("/receipts/confirm", response_model=InventoryOperationResponse)
def confirm_receipt(payload: ReceiptConfirmRequest, service: InventoryService = Depends(_service)):
    try:
        return service.confirm_receipt(payload.model_dump())
    except InventoryError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc


@router.post("/transfers", response_model=InventoryOperationResponse)
def transfer_stock(payload: TransferRequest, service: InventoryService = Depends(_service)):
    try:
        return service.transfer_stock(payload.model_dump())
    except InventoryError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc


@router.post("/reservations", response_model=InventoryOperationResponse)
def reserve_stock(payload: ReservationRequest, service: InventoryService = Depends(_service)):
    try:
        return service.reserve_stock(payload.model_dump())
    except InventoryError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc


@router.post("/dispatches", response_model=InventoryOperationResponse)
def dispatch_sales_order(payload: DispatchRequest, service: InventoryService = Depends(_service)):
    try:
        return service.dispatch_sales_order(payload.model_dump())
    except InventoryError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc


@router.post("/sales-orders/cancel", response_model=InventoryOperationResponse)
def cancel_sales_order(payload: CancelSalesOrderRequest, service: InventoryService = Depends(_service)):
    try:
        return service.cancel_sales_order(payload.model_dump())
    except InventoryError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc


@router.post("/returns", response_model=InventoryOperationResponse)
def process_return(payload: ReturnRequest, service: InventoryService = Depends(_service)):
    try:
        return service.process_return(payload.model_dump())
    except InventoryError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
