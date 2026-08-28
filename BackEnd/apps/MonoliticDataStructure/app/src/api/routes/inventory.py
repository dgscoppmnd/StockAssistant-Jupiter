"""Endpoints para inventario"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import and_, func
from typing import List, Optional
from ..database import get_db
from ..models import Inventory, Product, Warehouse
from ..schemas import Inventory as InventorySchema, InventoryWithDetails, PaginatedResponse
from ..utils.pagination import paginate

router = APIRouter()

@router.get("/", response_model=PaginatedResponse)
async def get_inventory(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    warehouse_id: Optional[str] = None,
    product_id: Optional[str] = None,
    min_stock: Optional[int] = None,
    max_stock: Optional[int] = None,
    critical_only: bool = False,
    db: Session = Depends(get_db)
):
    """
    Obtener inventario con filtros
    
    - **warehouse_id**: Filtrar por almacén
    - **product_id**: Filtrar por producto
    - **min_stock**: Stock mínimo
    - **max_stock**: Stock máximo
    - **critical_only**: Solo productos con stock crítico
    """
    query = db.query(Inventory)
    
    if warehouse_id:
        query = query.filter(Inventory.warehouse_id == warehouse_id)
    if product_id:
        query = query.filter(Inventory.product_id == product_id)
    if min_stock is not None:
        query = query.filter(Inventory.current_stock >= min_stock)
    if max_stock is not None:
        query = query.filter(Inventory.current_stock <= max_stock)
    if critical_only:
        query = query.filter(Inventory.current_stock < Inventory.reorder_level)
    
    return paginate(query, skip, limit)

@router.get("/critical", response_model=List[dict])
async def get_critical_stock(
    warehouse_id: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """Obtener productos con stock crítico (por debajo del punto de reorden)"""
    query = db.query(Inventory, Product, Warehouse).join(Product).join(Warehouse)
    query = query.filter(Inventory.current_stock < Inventory.reorder_level)
    
    if warehouse_id:
        query = query.filter(Inventory.warehouse_id == warehouse_id)
    
    results = query.all()
    
    return [
        {
            "product_id": inv.product_id,
            "product_category": product.product_category,
            "brand": product.brand,
            "sku": product.sku,
            "current_stock": inv.current_stock,
            "reorder_level": inv.reorder_level,
            "safety_stock": inv.safety_stock,
            "warehouse_id": inv.warehouse_id,
            "warehouse_location": warehouse.warehouse_location,
            "stock_gap": inv.current_stock - inv.reorder_level,
            "stockout_risk": inv.stockout_risk
        }
        for inv, product, warehouse in results
    ]

@router.get("/overstock", response_model=List[dict])
async def get_overstock(
    warehouse_id: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """Obtener productos con exceso de stock (muy por encima del punto de reorden)"""
    query = db.query(Inventory, Product, Warehouse).join(Product).join(Warehouse)
    query = query.filter(Inventory.current_stock > Inventory.reorder_level * 2)
    
    if warehouse_id:
        query = query.filter(Inventory.warehouse_id == warehouse_id)
    
    results = query.all()
    
    return [
        {
            "product_id": inv.product_id,
            "product_category": product.product_category,
            "brand": product.brand,
            "current_stock": inv.current_stock,
            "reorder_level": inv.reorder_level,
            "warehouse_id": inv.warehouse_id,
            "warehouse_location": warehouse.warehouse_location,
            "stock_excess": inv.current_stock - inv.reorder_level,
            "overstock_risk": inv.overstock_risk
        }
        for inv, product, warehouse in results
    ]

@router.get("/warehouse/{warehouse_id}/summary")
async def get_warehouse_summary(
    warehouse_id: str,
    db: Session = Depends(get_db)
):
    """Obtener resumen de inventario por almacén"""
    
    # Verificar que el almacén existe
    warehouse = db.query(Warehouse).filter(Warehouse.warehouse_id == warehouse_id).first()
    if not warehouse:
        raise HTTPException(status_code=404, detail="Almacén no encontrado")
    
    inventory_items = db.query(Inventory).filter(
        Inventory.warehouse_id == warehouse_id
    ).all()
    
    total_products = len(inventory_items)
    total_stock = sum(item.current_stock for item in inventory_items)
    avg_turnover = sum(item.inventory_turnover or 0 for item in inventory_items) / total_products if total_products > 0 else 0
    
    return {
        "warehouse_id": warehouse_id,
        "warehouse_location": warehouse.warehouse_location,
        "storage_capacity": warehouse.storage_capacity,
        "utilization_rate": warehouse.utilization_rate,
        "total_products": total_products,
        "total_stock": total_stock,
        "avg_turnover": avg_turnover,
        "critical_items": sum(1 for item in inventory_items if item.current_stock < item.reorder_level),
        "overstock_items": sum(1 for item in inventory_items if item.current_stock > item.reorder_level * 2)
    }

@router.get("/product/{product_id}")
async def get_product_inventory(
    product_id: str,
    db: Session = Depends(get_db)
):
    """Obtener inventario de un producto en todos los almacenes"""
    
    # Verificar que el producto existe
    product = db.query(Product).filter(Product.product_id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Producto no encontrado")
    
    inventory_items = db.query(Inventory, Warehouse).join(Warehouse).filter(
        Inventory.product_id == product_id
    ).all()
    
    return {
        "product_id": product_id,
        "product_category": product.product_category,
        "brand": product.brand,
        "locations": [
            {
                "warehouse_id": inv.warehouse_id,
                "warehouse_location": warehouse.warehouse_location,
                "current_stock": inv.current_stock,
                "reorder_level": inv.reorder_level,
                "safety_stock": inv.safety_stock,
                "stockout_risk": inv.stockout_risk,
                "inventory_turnover": inv.inventory_turnover
            }
            for inv, warehouse in inventory_items
        ],
        "total_stock": sum(inv.current_stock for inv, _ in inventory_items)
    }