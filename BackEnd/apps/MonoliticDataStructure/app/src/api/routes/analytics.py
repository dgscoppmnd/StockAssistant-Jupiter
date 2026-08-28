"""Endpoints para análisis avanzados"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, or_, desc
from datetime import datetime, date, timedelta
from typing import List, Optional
from ..database import get_db
from ..models import Product, Sales, Inventory, Logistics, SupplyChainMetric, Supplier

router = APIRouter()

@router.get("/product-performance")
async def get_product_performance(
    category: Optional[str] = None,
    limit: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db)
):
    """Obtener rendimiento de productos por categoría"""
    query = db.query(
        Product.product_id,
        Product.product_category,
        Product.brand,
        func.count(Sales.sales_id).label('num_sales'),
        func.sum(Sales.units_sold).label('total_units_sold'),
        func.sum(Sales.revenue_usd).label('total_revenue'),
        func.sum(Sales.profit_usd).label('total_profit'),
        func.avg(Sales.profit_usd).label('avg_profit_per_sale'),
        func.avg(Inventory.inventory_optimization_score).label('avg_optimization_score'),
        func.avg(Inventory.operational_risk_score).label('avg_risk_score')
    ).join(Sales, Product.product_id == Sales.product_id)\
     .join(Inventory, Product.product_id == Inventory.product_id)
    
    if category:
        query = query.filter(Product.product_category == category)
    
    query = query.group_by(
        Product.product_id,
        Product.product_category,
        Product.brand
    ).order_by(desc(func.sum(Sales.revenue_usd))).limit(limit)
    
    results = query.all()
    
    return [
        {
            "product_id": r[0],
            "product_category": r[1],
            "brand": r[2],
            "num_sales": r[3],
            "total_units_sold": float(r[4]) if r[4] else 0,
            "total_revenue": float(r[5]) if r[5] else 0,
            "total_profit": float(r[6]) if r[6] else 0,
            "avg_profit_per_sale": float(r[7]) if r[7] else 0,
            "avg_optimization_score": float(r[8]) if r[8] else 0,
            "avg_risk_score": float(r[9]) if r[9] else 0
        }
        for r in results
    ]

@router.get("/risk-analysis")
async def get_risk_analysis(
    db: Session = Depends(get_db)
):
    """Obtener análisis de riesgos combinados"""
    
    # Productos con mayor riesgo de stockout
    high_risk_products = db.query(
        Product.product_id,
        Product.product_category,
        Product.brand,
        Inventory.current_stock,
        Inventory.reorder_level,
        Inventory.stockout_risk
    ).join(Inventory, Product.product_id == Inventory.product_id)\
     .filter(Inventory.stockout_risk > 70)\
     .order_by(desc(Inventory.stockout_risk)).limit(10).all()
    
    # Productos con mayor riesgo operacional
    high_operational_risk = db.query(
        Product.product_id,
        Product.product_category,
        Product.brand,
        Inventory.operational_risk_score
    ).join(Inventory, Product.product_id == Inventory.product_id)\
     .filter(Inventory.operational_risk_score > 70)\
     .order_by(desc(Inventory.operational_risk_score)).limit(10).all()
    
    # Proveedores con mayor riesgo
    high_risk_suppliers = db.query(
        Supplier.supplier_id,
        Supplier.supplier_rating,
        Supplier.supplier_performance_score,
        func.avg(Logistics.supply_disruption_risk).label('avg_disruption_risk')
    ).join(Logistics, Supplier.supplier_id == Logistics.supplier_id)\
     .group_by(Supplier.supplier_id, Supplier.supplier_rating, Supplier.supplier_performance_score)\
     .having(func.avg(Logistics.supply_disruption_risk) > 60)\
     .order_by(desc(func.avg(Logistics.supply_disruption_risk))).limit(10).all()
    
    return {
        "high_stockout_risk_products": [
            {
                "product_id": r[0],
                "product_category": r[1],
                "brand": r[2],
                "current_stock": r[3],
                "reorder_level": r[4],
                "stockout_risk": r[5]
            }
            for r in high_risk_products
        ],
        "high_operational_risk_products": [
            {
                "product_id": r[0],
                "product_category": r[1],
                "brand": r[2],
                "operational_risk_score": r[3]
            }
            for r in high_operational_risk
        ],
        "high_risk_suppliers": [
            {
                "supplier_id": r[0],
                "supplier_rating": r[1],
                "supplier_performance_score": r[2],
                "avg_disruption_risk": r[3]
            }
            for r in high_risk_suppliers
        ]
    }

@router.get("/inventory-optimization")
async def get_inventory_optimization(
    db: Session = Depends(get_db)
):
    """Obtener productos que necesitan optimización de inventario"""
    
    query = db.query(
        Product.product_id,
        Product.product_category,
        Product.brand,
        Inventory.current_stock,
        Inventory.reorder_level,
        Inventory.safety_stock,
        Inventory.inventory_optimization_score,
        Inventory.stockout_risk,
        Inventory.overstock_risk
    ).join(Inventory, Product.product_id == Inventory.product_id)
    
    # Productos con baja optimización (< 30) o alto riesgo
    query = query.filter(
        or_(
            Inventory.inventory_optimization_score < 30,
            and_(
                Inventory.stockout_risk > 60,
                Inventory.overstock_risk > 60
            )
        )
    ).order_by(Inventory.inventory_optimization_score).limit(20)
    
    results = query.all()
    
    return [
        {
            "product_id": r[0],
            "product_category": r[1],
            "brand": r[2],
            "current_stock": r[3],
            "reorder_level": r[4],
            "safety_stock": r[5],
            "optimization_score": r[6],
            "stockout_risk": r[7],
            "overstock_risk": r[8],
            "recommendation": _get_optimization_recommendation(r[6], r[7], r[8])
        }
        for r in results
    ]

def _get_optimization_recommendation(score, stockout_risk, overstock_risk):
    """Genera recomendación basada en métricas"""
    if score < 30:
        if stockout_risk > 70:
            return "⚠️ Aumentar stock críticamente bajo"
        elif overstock_risk > 70:
            return "⚠️ Reducir exceso de inventario"
        else:
            return "📊 Revisar política de inventario"
    elif score < 50:
        return "📈 Mejorar eficiencia de inventario"
    else:
        return "✅ Optimización adecuada"