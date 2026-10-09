import logging

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from uuid import uuid4

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
from sales_service import SalesService
from .endpointsSales import sales_user

router = APIRouter(prefix="/inventory", tags=["inventory"])
logger = logging.getLogger("api.endpointsInventory")


def _service(db=Depends(get_db_products)) -> InventoryService:
    return InventoryService(db)


def _managed_sale(service, payload, authorization, action):
    order = service._fetchone(
        "SELECT * FROM public.sales_orders WHERE id=%s", (payload.sales_order_id,)
    )
    if not order or order.get("client_id") is None:
        return None
    if payload.warehouse_id != order["warehouse_id"]:
        raise InventoryError("La bodega no corresponde al pedido.", 409)
    sales = SalesService(service.connection, sales_user(service.connection, authorization))
    data = {
        "operation_key": payload.operation_key or f"sales-{uuid4().hex}",
        "reason": getattr(payload, "reason", None) or getattr(payload, "notes", None) or action,
    }
    if action != "cancel":
        by_product = {line["product_id"]: line for line in sales.order_lines(order["id"])}
        data["lines"] = []
        seen = set()
        for line in payload.lines:
            if line.product_id not in by_product or line.product_id in seen:
                raise InventoryError("Producto ajeno al pedido o repetido.", 400)
            seen.add(line.product_id)
            qty, _ = sales._convert_to_base_qty(line.product_id, line.quantity, line.unit_code)
            data["lines"].append({"line_id": by_product[line.product_id]["id"], "quantity": qty})
    fn = {
        "dispatch": sales.dispatch_order,
        "cancel": sales.cancel_order,
        "return": sales.return_order,
    }[action]
    result = fn(order["id"], data)
    document_id = result.get("dispatch_id", result.get("return_id", order["id"]))
    document_type = {
        "dispatch": "sales_dispatch",
        "cancel": "sales_order_cancel",
        "return": "sales_return",
    }[action]
    movements = sales._fetchall(
        "SELECT id FROM public.inventory_movements WHERE operation_key=%s", (data["operation_key"],)
    )
    return {
        "status": "confirmed",
        "document_type": document_type,
        "document_id": document_id,
        "document_number": order["sales_order_number"],
        "operation_key": data["operation_key"],
        "movement_ids": [row["id"] for row in movements],
        "invoice_id": result.get("invoice_id"),
    }


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
        return service.create_warehouse(
            payload.code, payload.name, payload.description, payload.is_active
        )
    except InventoryError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc


@router.get("/stock", response_model=list[StockView])
def list_stock(service: InventoryService = Depends(_service)):
    return service.list_stock()


@router.get("/movements", response_model=list[InventoryMovementResponse])
def list_movements(
    limit: int = Query(default=100, ge=1, le=500), service: InventoryService = Depends(_service)
):
    return service.list_movements(limit=limit)


@router.put("/products/config", response_model=ProductInventoryConfigResponse)
def configure_product(
    payload: ProductInventoryConfigRequest, service: InventoryService = Depends(_service)
):
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
def dispatch_sales_order(
    payload: DispatchRequest,
    service: InventoryService = Depends(_service),
    authorization: str | None = Header(default=None),
):
    try:
        managed = _managed_sale(service, payload, authorization, "dispatch")
        if managed is not None:
            return managed
        return service.dispatch_sales_order(payload.model_dump())
    except InventoryError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc


@router.post("/sales-orders/cancel", response_model=InventoryOperationResponse)
def cancel_sales_order(
    payload: CancelSalesOrderRequest,
    service: InventoryService = Depends(_service),
    authorization: str | None = Header(default=None),
):
    try:
        managed = _managed_sale(service, payload, authorization, "cancel")
        if managed is not None:
            return managed
        return service.cancel_sales_order(payload.model_dump())
    except InventoryError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc


@router.post("/returns", response_model=InventoryOperationResponse)
def process_return(
    payload: ReturnRequest,
    service: InventoryService = Depends(_service),
    authorization: str | None = Header(default=None),
):
    try:
        managed = _managed_sale(service, payload, authorization, "return")
        if managed is not None:
            return managed
        return service.process_return(payload.model_dump())
    except InventoryError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
