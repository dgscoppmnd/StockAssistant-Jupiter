"""Utilidades de paginación para la API"""

from sqlalchemy.orm import Query
from typing import Dict, Any, List
from pydantic import BaseModel

def paginate(query: Query, skip: int = 0, limit: int = 100) -> Dict[str, Any]:
    """
    Aplica paginación a una consulta SQLAlchemy
    
    Args:
        query: Consulta SQLAlchemy
        skip: Número de registros a saltar
        limit: Número máximo de registros a retornar
    
    Returns:
        Dict con items, total, skip, limit y has_more
    """
    # Obtener total
    total = query.count()
    
    # Aplicar paginación
    items = query.offset(skip).limit(limit).all()
    
    # Convertir objetos SQLAlchemy a diccionarios para serialización
    serialized_items = []
    for item in items:
        if hasattr(item, '__table__'):  # Es un objeto SQLAlchemy
            # Convertir a diccionario
            item_dict = {}
            for column in item.__table__.columns:
                value = getattr(item, column.name)
                # Convertir fechas y decimales a tipos serializables
                if hasattr(value, 'isoformat'):
                    value = value.isoformat()
                item_dict[column.name] = value
            serialized_items.append(item_dict)
        else:
            serialized_items.append(item)
    
    return {
        "items": serialized_items,
        "total": total,
        "skip": skip,
        "limit": limit,
        "has_more": (skip + limit) < total
    }

def paginate_with_columns(query: Query, columns: list, skip: int = 0, limit: int = 100) -> Dict[str, Any]:
    """
    Aplica paginación a una consulta con columnas específicas
    
    Args:
        query: Consulta SQLAlchemy
        columns: Lista de columnas a seleccionar
        skip: Número de registros a saltar
        limit: Número máximo de registros a retornar
    
    Returns:
        Dict con items (como diccionarios), total, skip, limit y has_more
    """
    # Obtener total
    total = query.count()
    
    # Aplicar paginación
    results = query.offset(skip).limit(limit).all()
    
    # Convertir a diccionarios
    items = []
    for row in results:
        if hasattr(row, '_asdict'):  # Para namedtuples
            items.append(row._asdict())
        elif isinstance(row, tuple):  # Para tuplas
            items.append(dict(zip(columns, row)))
        elif hasattr(row, '__table__'):  # Para objetos SQLAlchemy
            item_dict = {}
            for col in columns:
                value = getattr(row, col)
                if hasattr(value, 'isoformat'):
                    value = value.isoformat()
                item_dict[col] = value
            items.append(item_dict)
        else:
            items.append(row)
    
    return {
        "items": items,
        "total": total,
        "skip": skip,
        "limit": limit,
        "has_more": (skip + limit) < total
    }