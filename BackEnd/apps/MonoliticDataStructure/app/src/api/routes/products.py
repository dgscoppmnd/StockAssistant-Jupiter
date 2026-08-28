"""Endpoints para productos"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import or_
from typing import List, Optional
from ..database import get_db
from ..models import Product
from ..schemas import Product as ProductSchema, ProductCreate, PaginatedResponse
from ..utils.pagination import paginate

router = APIRouter()

@router.get("/")
async def get_products(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    category: Optional[str] = None,
    brand: Optional[str] = None,
    search: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """
    Obtener todos los productos con filtros
    
    - **category**: Filtrar por categoría
    - **brand**: Filtrar por marca
    - **search**: Buscar en product_id, sku o brand
    """
    query = db.query(Product)
    
    if category:
        query = query.filter(Product.product_category == category)
    if brand:
        query = query.filter(Product.brand == brand)
    if search:
        query = query.filter(
            or_(
                Product.product_id.ilike(f"%{search}%"),
                Product.sku.ilike(f"%{search}%"),
                Product.brand.ilike(f"%{search}%")
            )
        )
    
    # Usar paginación y serializar manualmente
    result = paginate(query, skip, limit)
    
    # Asegurar que los items son serializables
    result["items"] = [
        {
            "product_id": item["product_id"],
            "product_category": item["product_category"],
            "brand": item["brand"],
            "sku": item["sku"],
            "product_cost_usd": float(item["product_cost_usd"]) if item["product_cost_usd"] else None,
            "selling_price_usd": float(item["selling_price_usd"]) if item["selling_price_usd"] else None,
            "created_at": item["created_at"],
            "updated_at": item["updated_at"]
        }
        for item in result["items"]
    ]
    
    return result

@router.get("/{product_id}")
async def get_product(product_id: str, db: Session = Depends(get_db)):
    """Obtener producto por ID"""
    product = db.query(Product).filter(Product.product_id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Producto no encontrado")
    
    return {
        "product_id": product.product_id,
        "product_category": product.product_category,
        "brand": product.brand,
        "sku": product.sku,
        "product_cost_usd": float(product.product_cost_usd) if product.product_cost_usd else None,
        "selling_price_usd": float(product.selling_price_usd) if product.selling_price_usd else None,
        "created_at": product.created_at.isoformat() if product.created_at else None,
        "updated_at": product.updated_at.isoformat() if product.updated_at else None
    }

@router.get("/search/{sku}")
async def get_product_by_sku(sku: str, db: Session = Depends(get_db)):
    """Obtener producto por SKU"""
    product = db.query(Product).filter(Product.sku == sku).first()
    if not product:
        raise HTTPException(status_code=404, detail="Producto no encontrado")
    
    return {
        "product_id": product.product_id,
        "product_category": product.product_category,
        "brand": product.brand,
        "sku": product.sku,
        "product_cost_usd": float(product.product_cost_usd) if product.product_cost_usd else None,
        "selling_price_usd": float(product.selling_price_usd) if product.selling_price_usd else None,
        "created_at": product.created_at.isoformat() if product.created_at else None,
        "updated_at": product.updated_at.isoformat() if product.updated_at else None
    }

@router.get("/categories/", response_model=List[str])
async def get_categories(db: Session = Depends(get_db)):
    """Obtener todas las categorías de productos"""
    categories = db.query(Product.product_category).distinct().all()
    return [c[0] for c in categories if c[0]]

@router.get("/brands/", response_model=List[str])
async def get_brands(db: Session = Depends(get_db)):
    """Obtener todas las marcas de productos"""
    brands = db.query(Product.brand).distinct().all()
    return [b[0] for b in brands if b[0] is not None]