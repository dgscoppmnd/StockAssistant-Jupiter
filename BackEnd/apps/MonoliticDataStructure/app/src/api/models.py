"""Modelos SQLAlchemy para la base de datos"""

from sqlalchemy import Column, Integer, String, Float, Date, DateTime, ForeignKey, Numeric
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from datetime import datetime

from .database import Base

class Product(Base):
    __tablename__ = "products"
    
    product_id = Column(String(20), primary_key=True)
    product_category = Column(String(50), nullable=False)
    brand = Column(String(50))
    sku = Column(String(50), unique=True, nullable=False)
    product_cost_usd = Column(Numeric(12, 2))
    selling_price_usd = Column(Numeric(12, 2))
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
    
    # Relaciones
    inventory = relationship("Inventory", back_populates="product")
    sales = relationship("Sales", back_populates="product")
    logistics = relationship("Logistics", back_populates="product")
    metrics = relationship("SupplyChainMetric", back_populates="product")

class Supplier(Base):
    __tablename__ = "suppliers"
    
    supplier_id = Column(String(20), primary_key=True)
    supplier_rating = Column(Numeric(3, 2))
    lead_time_days = Column(Integer)
    supplier_performance_score = Column(Numeric(5, 2))
    sustainability_score = Column(Numeric(5, 2))
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
    
    logistics = relationship("Logistics", back_populates="supplier")

class Warehouse(Base):
    __tablename__ = "warehouses"
    
    warehouse_id = Column(String(20), primary_key=True)
    warehouse_location = Column(String(50), nullable=False)
    storage_capacity = Column(Integer)
    utilization_rate = Column(Numeric(5, 2))
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
    
    inventory = relationship("Inventory", back_populates="warehouse")
    logistics = relationship("Logistics", back_populates="warehouse")

class Inventory(Base):
    __tablename__ = "inventory"
    
    inventory_id = Column(Integer, primary_key=True, autoincrement=True)
    product_id = Column(String(20), ForeignKey("products.product_id", ondelete="CASCADE"))
    warehouse_id = Column(String(20), ForeignKey("warehouses.warehouse_id", ondelete="CASCADE"))
    current_stock = Column(Integer, default=0)
    reorder_level = Column(Integer, default=0)
    safety_stock = Column(Integer, default=0)
    inventory_turnover = Column(Numeric(10, 2), default=0)
    stockout_risk = Column(Numeric(5, 2), default=0)
    overstock_risk = Column(Numeric(5, 2), default=0)
    inventory_optimization_score = Column(Numeric(5, 2), default=0)
    operational_risk_score = Column(Numeric(5, 2), default=0)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
    
    product = relationship("Product", back_populates="inventory")
    warehouse = relationship("Warehouse", back_populates="inventory")

class Sales(Base):
    __tablename__ = "sales"
    
    sales_id = Column(Integer, primary_key=True, autoincrement=True)
    product_id = Column(String(20), ForeignKey("products.product_id", ondelete="CASCADE"))
    date = Column(Date, nullable=False)
    month = Column(Integer)
    quarter = Column(Integer)
    year = Column(Integer)
    units_sold = Column(Integer, default=0)
    daily_demand = Column(Integer, default=0)
    monthly_demand = Column(Integer, default=0)
    seasonal_demand_index = Column(Numeric(5, 2), default=0)
    revenue_usd = Column(Numeric(15, 2), default=0)
    profit_usd = Column(Numeric(15, 2), default=0)
    demand_forecast = Column(Integer, default=0)
    predicted_reorder_quantity = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.now)
    
    product = relationship("Product", back_populates="sales")

class Logistics(Base):
    __tablename__ = "logistics"
    
    logistics_id = Column(Integer, primary_key=True, autoincrement=True)
    product_id = Column(String(20), ForeignKey("products.product_id", ondelete="CASCADE"))
    supplier_id = Column(String(20), ForeignKey("suppliers.supplier_id", ondelete="CASCADE"))
    warehouse_id = Column(String(20), ForeignKey("warehouses.warehouse_id", ondelete="CASCADE"))
    shipping_cost_usd = Column(Numeric(12, 2), default=0)
    transportation_mode = Column(String(20), nullable=False)
    delivery_time_days = Column(Integer, default=0)
    on_time_delivery_rate = Column(Numeric(5, 2), default=0)
    supply_disruption_risk = Column(Numeric(5, 2), default=0)
    supply_chain_efficiency = Column(Numeric(5, 2), default=0)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
    
    product = relationship("Product", back_populates="logistics")
    supplier = relationship("Supplier", back_populates="logistics")
    warehouse = relationship("Warehouse", back_populates="logistics")

class SupplyChainMetric(Base):
    __tablename__ = "supply_chain_metrics"
    
    metric_id = Column(Integer, primary_key=True, autoincrement=True)
    product_id = Column(String(20), ForeignKey("products.product_id", ondelete="CASCADE"))
    date = Column(Date, nullable=False)
    inventory_optimization_score = Column(Numeric(5, 2))
    supplier_performance_score = Column(Numeric(5, 2))
    supply_chain_efficiency = Column(Numeric(5, 2))
    sustainability_score = Column(Numeric(5, 2))
    operational_risk_score = Column(Numeric(5, 2))
    created_at = Column(DateTime, default=datetime.now)
    
    product = relationship("Product", back_populates="metrics")