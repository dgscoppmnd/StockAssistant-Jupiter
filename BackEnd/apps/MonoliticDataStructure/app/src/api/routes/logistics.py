"""Endpoints para logística"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List, Optional
from ..database import get_db
from ..models import Logistics, Product, Supplier, Warehouse
from ..schemas import PaginatedResponse
from ..utils.pagination import paginate

router = APIRouter()

@router.get("/", response_model=PaginatedResponse)
async def get_logistics(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    product_id: Optional[str] = None,
    supplier_id: Optional[str] = None,
    warehouse_id: Optional[str] = None,
    transport_mode: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """Obtener registros logísticos con filtros"""
    query = db.query(Logistics)
    
    if product_id:
        query = query.filter(Logistics.product_id == product_id)
    if supplier_id:
        query = query.filter(Logistics.supplier_id == supplier_id)
    if warehouse_id:
        query = query.filter(Logistics.warehouse_id == warehouse_id)
    if transport_mode:
        query = query.filter(Logistics.transportation_mode == transport_mode)
    
    return paginate(query, skip, limit)

@router.get("/transport-modes")
async def get_transport_modes(db: Session = Depends(get_db)):
    """Obtener modos de transporte disponibles"""
    modes = db.query(Logistics.transportation_mode).distinct().all()
    return [m[0] for m in modes]

@router.get("/summary")
async def get_logistics_summary(
    supplier_id: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """Obtener resumen de logística"""
    
    query = db.query(
        func.count(Logistics.logistics_id).label('total_shipments'),
        func.avg(Logistics.shipping_cost_usd).label('avg_shipping_cost'),
        func.avg(Logistics.delivery_time_days).label('avg_delivery_days'),
        func.avg(Logistics.on_time_delivery_rate).label('avg_on_time_rate'),
        func.avg(Logistics.supply_chain_efficiency).label('avg_efficiency'),
        func.avg(Logistics.supply_disruption_risk).label('avg_disruption_risk')
    )
    
    if supplier_id:
        query = query.filter(Logistics.supplier_id == supplier_id)
    
    result = query.first()
    
    return {
        "total_shipments": result[0] or 0,
        "avg_shipping_cost": float(result[1]) if result[1] else 0,
        "avg_delivery_days": float(result[2]) if result[2] else 0,
        "avg_on_time_delivery_rate": float(result[3]) if result[3] else 0,
        "avg_supply_chain_efficiency": float(result[4]) if result[4] else 0,
        "avg_supply_disruption_risk": float(result[5]) if result[5] else 0
    }

@router.get("/efficiency")
async def get_efficiency_metrics(
    warehouse_id: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """Obtener métricas de eficiencia logística"""
    
    query = db.query(
        Logistics.transportation_mode,
        func.count(Logistics.logistics_id).label('shipments'),
        func.avg(Logistics.shipping_cost_usd).label('avg_cost'),
        func.avg(Logistics.delivery_time_days).label('avg_delivery'),
        func.avg(Logistics.on_time_delivery_rate).label('avg_on_time')
    )
    
    if warehouse_id:
        query = query.filter(Logistics.warehouse_id == warehouse_id)
    
    query = query.group_by(Logistics.transportation_mode)
    results = query.all()
    
    return [
        {
            "transportation_mode": r[0],
            "shipments": r[1],
            "avg_shipping_cost": float(r[2]) if r[2] else 0,
            "avg_delivery_days": float(r[3]) if r[3] else 0,
            "avg_on_time_delivery": float(r[4]) if r[4] else 0
        }
        for r in results
    ]