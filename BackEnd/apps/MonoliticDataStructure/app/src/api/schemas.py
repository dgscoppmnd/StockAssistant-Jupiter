"""Schemas Pydantic para validación y serialización"""

from pydantic import BaseModel, Field, ConfigDict
from datetime import date, datetime
from typing import Optional, List
from decimal import Decimal

# =============================================
# SCHEMAS DE PRODUCTOS
# =============================================

class ProductBase(BaseModel):
    product_id: str
    product_category: str
    brand: Optional[str] = None
    sku: str
    product_cost_usd: Optional[Decimal] = None
    selling_price_usd: Optional[Decimal] = None

class ProductCreate(ProductBase):
    pass

class Product(ProductBase):
    created_at: datetime
    updated_at: datetime
    
    model_config = ConfigDict(from_attributes=True)  # ← NUEVO

# =============================================
# SCHEMAS DE INVENTARIO
# =============================================

class InventoryBase(BaseModel):
    product_id: str
    warehouse_id: str
    current_stock: int = 0
    reorder_level: int = 0
    safety_stock: int = 0
    inventory_turnover: Optional[Decimal] = 0
    stockout_risk: Optional[Decimal] = 0
    overstock_risk: Optional[Decimal] = 0
    inventory_optimization_score: Optional[Decimal] = 0
    operational_risk_score: Optional[Decimal] = 0

class InventoryCreate(InventoryBase):
    pass

class Inventory(InventoryBase):
    inventory_id: int
    created_at: datetime
    updated_at: datetime
    
    model_config = ConfigDict(from_attributes=True)

class InventoryWithDetails(Inventory):
    product: Optional[Product] = None
    warehouse_location: Optional[str] = None

# =============================================
# SCHEMAS DE VENTAS
# =============================================

class SalesBase(BaseModel):
    product_id: str
    date: date
    month: int = Field(ge=1, le=12)
    quarter: int = Field(ge=1, le=4)
    year: int = Field(ge=2000)
    units_sold: int = 0
    daily_demand: int = 0
    monthly_demand: int = 0
    seasonal_demand_index: Optional[Decimal] = 0
    revenue_usd: Optional[Decimal] = 0
    profit_usd: Optional[Decimal] = 0
    demand_forecast: int = 0
    predicted_reorder_quantity: int = 0

class SalesCreate(SalesBase):
    pass

class Sales(SalesBase):
    sales_id: int
    created_at: datetime
    
    model_config = ConfigDict(from_attributes=True)

class SalesSummary(BaseModel):
    product_id: str
    total_units_sold: int
    total_revenue: Decimal
    total_profit: Decimal
    avg_profit_per_sale: Decimal
    num_sales: int

# =============================================
# SCHEMAS DE PROVEEDORES
# =============================================

class SupplierBase(BaseModel):
    supplier_id: str
    supplier_rating: Optional[Decimal] = 0
    lead_time_days: Optional[int] = 0
    supplier_performance_score: Optional[Decimal] = 0
    sustainability_score: Optional[Decimal] = 0

class SupplierCreate(SupplierBase):
    pass

class Supplier(SupplierBase):
    created_at: datetime
    updated_at: datetime
    
    model_config = ConfigDict(from_attributes=True)

class SupplierEfficiency(BaseModel):
    supplier_id: str
    supplier_rating: Optional[Decimal] = 0
    supplier_performance_score: Optional[Decimal] = 0
    sustainability_score: Optional[Decimal] = 0
    avg_on_time_delivery: Optional[Decimal] = 0
    avg_delivery_days: Optional[Decimal] = 0
    products_supplied: int

# =============================================
# SCHEMAS DE MÉTRICAS
# =============================================

class MetricBase(BaseModel):
    product_id: str
    date: date
    inventory_optimization_score: Optional[Decimal] = 0
    supplier_performance_score: Optional[Decimal] = 0
    supply_chain_efficiency: Optional[Decimal] = 0
    sustainability_score: Optional[Decimal] = 0
    operational_risk_score: Optional[Decimal] = 0

class MetricCreate(MetricBase):
    pass

class Metric(MetricBase):
    metric_id: int
    created_at: datetime
    
    model_config = ConfigDict(from_attributes=True)

# =============================================
# SCHEMAS DE PAGINACIÓN
# =============================================

class PaginationParams(BaseModel):
    skip: int = 0
    limit: int = 100

class PaginatedResponse(BaseModel):
    items: List
    total: int
    skip: int
    limit: int
    has_more: bool