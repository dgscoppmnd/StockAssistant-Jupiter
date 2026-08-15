"""Aplicación principal FastAPI"""

from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime, date, timedelta
from .config import settings
from .database import engine, Base
from .routes import (
    products, inventory, sales, suppliers, 
    logistics, metrics, analytics
)

# Crear tablas
Base.metadata.create_all(bind=engine)

# Inicializar app
app = FastAPI(
    title=settings.API_TITLE,
    version=settings.API_VERSION,
    description=settings.API_DESCRIPTION,
    docs_url="/docs",
    redoc_url="/redoc"
)

# Configurar CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# =============================================
# RUTAS PRINCIPALES
# =============================================

@app.get("/")
async def root():
    """Endpoint raíz"""
    return {
        "message": "Supply Chain Management API",
        "version": settings.API_VERSION,
        "docs": "/docs",
        "redoc": "/redoc"
    }

@app.get("/health")
async def health_check():
    """Health check"""
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}

# =============================================
# REGISTRAR ROUTERS
# =============================================

app.include_router(products.router, prefix="/api/v1/products", tags=["Products"])
app.include_router(inventory.router, prefix="/api/v1/inventory", tags=["Inventory"])
app.include_router(sales.router, prefix="/api/v1/sales", tags=["Sales"])
app.include_router(suppliers.router, prefix="/api/v1/suppliers", tags=["Suppliers"])
app.include_router(logistics.router, prefix="/api/v1/logistics", tags=["Logistics"])
app.include_router(metrics.router, prefix="/api/v1/metrics", tags=["Metrics"])
app.include_router(analytics.router, prefix="/api/v1/analytics", tags=["Analytics"])

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "src.api.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True
    )