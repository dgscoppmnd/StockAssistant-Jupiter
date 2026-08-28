"""Endpoints para métricas de cadena de suministro"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, and_
from datetime import datetime, date, timedelta
from typing import List, Optional
from ..database import get_db
from ..models import SupplyChainMetric, Product
from ..schemas import Metric as MetricSchema, PaginatedResponse
from ..utils.pagination import paginate

router = APIRouter()

@router.get("/", response_model=PaginatedResponse)
async def get_metrics(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    product_id: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """Obtener métricas con filtros"""
    query = db.query(SupplyChainMetric)
    
    if product_id:
        query = query.filter(SupplyChainMetric.product_id == product_id)
    if start_date:
        query = query.filter(SupplyChainMetric.date >= start_date)
    if end_date:
        query = query.filter(SupplyChainMetric.date <= end_date)
    
    return paginate(query, skip, limit)

@router.get("/product/{product_id}")
async def get_product_metrics(
    product_id: str,
    days: int = Query(90, ge=1, le=365),
    db: Session = Depends(get_db)
):
    """Obtener métricas históricas de un producto"""
    
    # Verificar que el producto existe
    product = db.query(Product).filter(Product.product_id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Producto no encontrado")
    
    since_date = date.today() - timedelta(days=days)
    
    metrics = db.query(SupplyChainMetric).filter(
        and_(
            SupplyChainMetric.product_id == product_id,
            SupplyChainMetric.date >= since_date
        )
    ).order_by(SupplyChainMetric.date).all()
    
    return {
        "product_id": product_id,
        "product_category": product.product_category,
        "brand": product.brand,
        "period_days": days,
        "metrics": [
            {
                "date": m.date.isoformat(),
                "inventory_optimization_score": m.inventory_optimization_score,
                "supplier_performance_score": m.supplier_performance_score,
                "supply_chain_efficiency": m.supply_chain_efficiency,
                "sustainability_score": m.sustainability_score,
                "operational_risk_score": m.operational_risk_score
            }
            for m in metrics
        ],
        "summary": {
            "avg_inventory_optimization": sum(m.inventory_optimization_score or 0 for m in metrics) / len(metrics) if metrics else 0,
            "avg_supplier_performance": sum(m.supplier_performance_score or 0 for m in metrics) / len(metrics) if metrics else 0,
            "avg_supply_chain_efficiency": sum(m.supply_chain_efficiency or 0 for m in metrics) / len(metrics) if metrics else 0,
            "avg_sustainability": sum(m.sustainability_score or 0 for m in metrics) / len(metrics) if metrics else 0,
            "avg_operational_risk": sum(m.operational_risk_score or 0 for m in metrics) / len(metrics) if metrics else 0
        }
    }

@router.get("/summary")
async def get_metrics_summary(
    category: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """Obtener resumen de métricas por categoría"""
    
    query = db.query(
        Product.product_category,
        func.avg(SupplyChainMetric.inventory_optimization_score).label('avg_optimization'),
        func.avg(SupplyChainMetric.supplier_performance_score).label('avg_supplier_performance'),
        func.avg(SupplyChainMetric.supply_chain_efficiency).label('avg_efficiency'),
        func.avg(SupplyChainMetric.sustainability_score).label('avg_sustainability'),
        func.avg(SupplyChainMetric.operational_risk_score).label('avg_risk'),
        func.count(SupplyChainMetric.metric_id).label('total_metrics')
    ).join(Product, SupplyChainMetric.product_id == Product.product_id)
    
    if category:
        query = query.filter(Product.product_category == category)
    
    query = query.group_by(Product.product_category)
    results = query.all()
    
    return [
        {
            "category": r[0],
            "avg_inventory_optimization": float(r[1]) if r[1] else 0,
            "avg_supplier_performance": float(r[2]) if r[2] else 0,
            "avg_supply_chain_efficiency": float(r[3]) if r[3] else 0,
            "avg_sustainability": float(r[4]) if r[4] else 0,
            "avg_operational_risk": float(r[5]) if r[5] else 0,
            "total_metrics": r[6]
        }
        for r in results
    ]