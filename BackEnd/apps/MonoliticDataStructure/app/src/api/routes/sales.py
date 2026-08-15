"""Endpoints para ventas"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, and_
from datetime import datetime, date, timedelta
from typing import List, Optional
from ..database import get_db
from ..models import Sales, Product
from ..schemas import Sales as SalesSchema, SalesCreate, PaginatedResponse
from ..utils.pagination import paginate

router = APIRouter()

@router.get("/", response_model=PaginatedResponse)
async def get_sales(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    product_id: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    year: Optional[int] = None,
    quarter: Optional[int] = None,
    db: Session = Depends(get_db)
):
    """
    Obtener ventas con filtros
    
    - **product_id**: Filtrar por producto
    - **start_date**: Fecha de inicio (YYYY-MM-DD)
    - **end_date**: Fecha de fin (YYYY-MM-DD)
    - **year**: Año específico
    - **quarter**: Trimestre específico (1-4)
    """
    query = db.query(Sales)
    
    if product_id:
        query = query.filter(Sales.product_id == product_id)
    if start_date:
        query = query.filter(Sales.date >= start_date)
    if end_date:
        query = query.filter(Sales.date <= end_date)
    if year:
        query = query.filter(Sales.year == year)
    if quarter:
        query = query.filter(Sales.quarter == quarter)
    
    return paginate(query, skip, limit)

@router.get("/trends")
async def get_sales_trends(
    product_id: Optional[str] = None,
    days: int = Query(30, ge=1, le=365),
    db: Session = Depends(get_db)
):
    """Obtener tendencias de ventas en un período de días"""
    since_date = date.today() - timedelta(days=days)
    
    query = db.query(
        Sales.date,
        func.sum(Sales.units_sold).label('total_units'),
        func.sum(Sales.revenue_usd).label('total_revenue'),
        func.sum(Sales.profit_usd).label('total_profit'),
        func.count(Sales.sales_id).label('num_transactions')
    ).filter(Sales.date >= since_date)
    
    if product_id:
        query = query.filter(Sales.product_id == product_id)
    
    query = query.group_by(Sales.date).order_by(Sales.date)
    results = query.all()
    
    return [
        {
            "date": r[0].isoformat(),
            "total_units": float(r[1]) if r[1] else 0,
            "total_revenue": float(r[2]) if r[2] else 0,
            "total_profit": float(r[3]) if r[3] else 0,
            "num_transactions": r[4]
        }
        for r in results
    ]

@router.get("/summary")
async def get_sales_summary(
    product_id: Optional[str] = None,
    year: Optional[int] = None,
    db: Session = Depends(get_db)
):
    """Obtener resumen de ventas"""
    
    query = db.query(
        func.count(Sales.sales_id).label('total_transactions'),
        func.sum(Sales.units_sold).label('total_units'),
        func.sum(Sales.revenue_usd).label('total_revenue'),
        func.sum(Sales.profit_usd).label('total_profit'),
        func.avg(Sales.profit_usd).label('avg_profit'),
        func.avg(Sales.units_sold).label('avg_units_per_sale')
    )
    
    if product_id:
        query = query.filter(Sales.product_id == product_id)
    if year:
        query = query.filter(Sales.year == year)
    
    result = query.first()
    
    return {
        "total_transactions": result[0] or 0,
        "total_units_sold": float(result[1]) if result[1] else 0,
        "total_revenue": float(result[2]) if result[2] else 0,
        "total_profit": float(result[3]) if result[3] else 0,
        "avg_profit_per_sale": float(result[4]) if result[4] else 0,
        "avg_units_per_sale": float(result[5]) if result[5] else 0
    }

@router.get("/top-products")
async def get_top_products(
    limit: int = Query(10, ge=1, le=100),
    period: int = Query(30, ge=1, le=365),
    db: Session = Depends(get_db)
):
    """Obtener los productos más vendidos en un período"""
    since_date = date.today() - timedelta(days=period)
    
    query = db.query(
        Product.product_id,
        Product.product_category,
        Product.brand,
        func.sum(Sales.units_sold).label('total_units'),
        func.sum(Sales.revenue_usd).label('total_revenue'),
        func.sum(Sales.profit_usd).label('total_profit'),
        func.count(Sales.sales_id).label('num_sales')
    ).join(Sales, Product.product_id == Sales.product_id)\
     .filter(Sales.date >= since_date)\
     .group_by(
        Product.product_id,
        Product.product_category,
        Product.brand
    ).order_by(func.sum(Sales.units_sold).desc()).limit(limit)
    
    results = query.all()
    
    return [
        {
            "product_id": r[0],
            "product_category": r[1],
            "brand": r[2],
            "total_units_sold": float(r[3]) if r[3] else 0,
            "total_revenue": float(r[4]) if r[4] else 0,
            "total_profit": float(r[5]) if r[5] else 0,
            "num_sales": r[6]
        }
        for r in results
    ]