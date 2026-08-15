"""Endpoints para proveedores"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List, Optional
from ..database import get_db
from ..models import Supplier, Logistics
from ..schemas import SupplierEfficiency, PaginatedResponse
from ..utils.pagination import paginate

router = APIRouter()

@router.get("/", response_model=PaginatedResponse)
async def get_suppliers(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    min_rating: Optional[float] = None,
    db: Session = Depends(get_db)
):
    """Obtener proveedores con filtros"""
    query = db.query(Supplier)
    
    if min_rating is not None:
        query = query.filter(Supplier.supplier_rating >= min_rating)
    
    return paginate(query, skip, limit)

@router.get("/{supplier_id}")
async def get_supplier(
    supplier_id: str,
    db: Session = Depends(get_db)
):
    """Obtener proveedor por ID"""
    supplier = db.query(Supplier).filter(Supplier.supplier_id == supplier_id).first()
    if not supplier:
        raise HTTPException(status_code=404, detail="Proveedor no encontrado")
    return supplier

@router.get("/efficiency", response_model=List[SupplierEfficiency])
async def get_supplier_efficiency(
    min_rating: Optional[float] = None,
    db: Session = Depends(get_db)
):
    """Obtener eficiencia de proveedores"""
    query = db.query(
        Supplier.supplier_id,
        Supplier.supplier_rating,
        Supplier.supplier_performance_score,
        Supplier.sustainability_score,
        func.avg(Logistics.on_time_delivery_rate).label('avg_on_time_delivery'),
        func.avg(Logistics.delivery_time_days).label('avg_delivery_days'),
        func.count(Logistics.product_id).label('products_supplied')
    ).join(Logistics, Supplier.supplier_id == Logistics.supplier_id)
    
    if min_rating is not None:
        query = query.filter(Supplier.supplier_rating >= min_rating)
    
    query = query.group_by(
        Supplier.supplier_id,
        Supplier.supplier_rating,
        Supplier.supplier_performance_score,
        Supplier.sustainability_score
    ).order_by(Supplier.supplier_rating.desc())
    
    results = query.all()
    
    return [
        {
            "supplier_id": r[0],
            "supplier_rating": r[1],
            "supplier_performance_score": r[2],
            "sustainability_score": r[3],
            "avg_on_time_delivery": r[4],
            "avg_delivery_days": r[5],
            "products_supplied": r[6]
        }
        for r in results
    ]

@router.get("/{supplier_id}/performance")
async def get_supplier_performance(
    supplier_id: str,
    db: Session = Depends(get_db)
):
    """Obtener rendimiento detallado de un proveedor"""
    
    supplier = db.query(Supplier).filter(Supplier.supplier_id == supplier_id).first()
    if not supplier:
        raise HTTPException(status_code=404, detail="Proveedor no encontrado")
    
    # Métricas de logística
    logistics_metrics = db.query(
        func.avg(Logistics.on_time_delivery_rate).label('avg_on_time'),
        func.avg(Logistics.delivery_time_days).label('avg_delivery_days'),
        func.avg(Logistics.shipping_cost_usd).label('avg_shipping_cost'),
        func.avg(Logistics.supply_disruption_risk).label('avg_disruption_risk'),
        func.count(Logistics.logistics_id).label('total_shipments')
    ).filter(Logistics.supplier_id == supplier_id).first()
    
    return {
        "supplier_id": supplier.supplier_id,
        "supplier_rating": supplier.supplier_rating,
        "supplier_performance_score": supplier.supplier_performance_score,
        "sustainability_score": supplier.sustainability_score,
        "lead_time_days": supplier.lead_time_days,
        "performance_metrics": {
            "avg_on_time_delivery": logistics_metrics[0],
            "avg_delivery_days": logistics_metrics[1],
            "avg_shipping_cost": logistics_metrics[2],
            "avg_disruption_risk": logistics_metrics[3],
            "total_shipments": logistics_metrics[4]
        }
    }