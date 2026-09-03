from datetime import date, datetime
from decimal import Decimal
from typing import Literal, Optional

from pydantic import BaseModel, Field


DocumentStatus = Literal["borrador", "confirmado", "parcial", "cancelado", "completado"]


class WarehouseCreate(BaseModel):
    code: str = Field(min_length=1, max_length=40)
    name: str = Field(min_length=1, max_length=120)
    description: Optional[str] = Field(default=None, max_length=255)
    is_active: bool = True


class WarehouseResponse(BaseModel):
    id: int
    code: str
    name: str
    description: Optional[str] = None
    is_active: bool
    created_at: datetime
    updated_at: datetime


class StockView(BaseModel):
    product_id: int
    product_name: str
    warehouse_id: int
    warehouse_code: str
    warehouse_name: str
    physical_qty: Decimal
    reserved_qty: Decimal
    available_qty: Decimal
    base_unit_code: str
    reorder_point: Decimal
    reorder_quantity: Decimal
    currency: Optional[str] = None


class DashboardResponse(BaseModel):
    total_products: int
    total_warehouses: int
    total_stock_units: Decimal
    total_reserved_units: Decimal
    total_available_units: Decimal
    low_stock_items: int
    warehouses: list[WarehouseResponse]
    recent_movements: list[dict]
    stock_snapshot: list[StockView]


class ProductInventoryConfigRequest(BaseModel):
    product_id: int
    base_unit_code: str = Field(min_length=1, max_length=20)
    reorder_point: Decimal = Field(default=Decimal("0"), ge=Decimal("0"))
    reorder_quantity: Decimal = Field(default=Decimal("0"), ge=Decimal("0"))
    allow_negative_stock: bool = False


class ProductInventoryConfigResponse(BaseModel):
    product_id: int
    base_unit_id: int
    base_unit_code: str
    reorder_point: Decimal
    reorder_quantity: Decimal
    allow_negative_stock: bool
    created_at: datetime
    updated_at: datetime


class InventoryLineRequest(BaseModel):
    product_id: int
    quantity: Decimal = Field(gt=Decimal("0"))
    unit_code: str = Field(min_length=1, max_length=20)
    unit_price: Decimal = Field(default=Decimal("0"), ge=Decimal("0"))
    currency_code: Optional[str] = Field(default=None, min_length=3, max_length=3)
    exchange_rate: Decimal = Field(default=Decimal("1"), gt=Decimal("0"))
    exchange_rate_date: Optional[date] = None


class ReceiptConfirmRequest(BaseModel):
    warehouse_id: int
    supplier_name: str = Field(min_length=1, max_length=200)
    supplier_code: Optional[str] = Field(default=None, max_length=80)
    purchase_order_number: Optional[str] = Field(default=None, max_length=80)
    receipt_number: Optional[str] = Field(default=None, max_length=80)
    operation_key: Optional[str] = Field(default=None, max_length=120)
    user_name: str = Field(default="system", min_length=1, max_length=120)
    notes: Optional[str] = Field(default=None, max_length=500)
    lines: list[InventoryLineRequest] = Field(min_length=1)


class TransferRequest(BaseModel):
    source_warehouse_id: int
    destination_warehouse_id: int
    user_name: str = Field(default="system", min_length=1, max_length=120)
    reason: str = Field(default="transferencia", min_length=1, max_length=120)
    operation_key: Optional[str] = Field(default=None, max_length=120)
    lines: list[InventoryLineRequest] = Field(min_length=1)


class ReservationRequest(BaseModel):
    warehouse_id: int
    customer_name: str = Field(min_length=1, max_length=200)
    sales_order_number: Optional[str] = Field(default=None, max_length=80)
    operation_key: Optional[str] = Field(default=None, max_length=120)
    user_name: str = Field(default="system", min_length=1, max_length=120)
    notes: Optional[str] = Field(default=None, max_length=500)
    lines: list[InventoryLineRequest] = Field(min_length=1)


class DispatchRequest(BaseModel):
    sales_order_id: int
    warehouse_id: int
    dispatch_number: Optional[str] = Field(default=None, max_length=80)
    invoice_number: Optional[str] = Field(default=None, max_length=80)
    operation_key: Optional[str] = Field(default=None, max_length=120)
    user_name: str = Field(default="system", min_length=1, max_length=120)
    notes: Optional[str] = Field(default=None, max_length=500)
    lines: list[InventoryLineRequest] = Field(min_length=1)


class CancelSalesOrderRequest(BaseModel):
    sales_order_id: int
    warehouse_id: int
    operation_key: Optional[str] = Field(default=None, max_length=120)
    user_name: str = Field(default="system", min_length=1, max_length=120)
    reason: str = Field(default="cancelacion", min_length=1, max_length=120)


class ReturnRequest(BaseModel):
    sales_order_id: int
    warehouse_id: int
    return_number: Optional[str] = Field(default=None, max_length=80)
    credit_note_number: Optional[str] = Field(default=None, max_length=80)
    operation_key: Optional[str] = Field(default=None, max_length=120)
    user_name: str = Field(default="system", min_length=1, max_length=120)
    reason: str = Field(default="devolucion", min_length=1, max_length=120)
    lines: list[InventoryLineRequest] = Field(min_length=1)


class InventoryOperationResponse(BaseModel):
    status: str
    document_type: str
    document_id: int
    document_number: str
    operation_key: str
    movement_ids: list[int]
    provider: Optional[str] = None
    model: Optional[str] = None


class InventoryMovementResponse(BaseModel):
    id: int
    movement_type: str
    product_id: int
    warehouse_id: Optional[int] = None
    warehouse_destination_id: Optional[int] = None
    quantity: Decimal
    quantity_signed: Decimal
    base_unit_code: str
    document_type: Optional[str] = None
    document_id: Optional[int] = None
    operation_key: str
    reason: Optional[str] = None
    user_name: str
    created_at: datetime
