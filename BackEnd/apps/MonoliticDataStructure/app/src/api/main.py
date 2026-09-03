"""Aplicación principal FastAPI de Proyecto Jupiter."""

import logging
from pathlib import Path
from datetime import datetime

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from .config import settings
from .database import engine, Base
from .routes import (
    products, inventory, sales, suppliers, 
    logistics, metrics, analytics
)
from endpoints.endpoints import public_router, router as kitia_router
from DataBaseManagement.dbConectionPostgres import init_db, init_products_db

# Crear tablas
Base.metadata.create_all(bind=engine)
LOGGER = logging.getLogger("src.api.main")

# Inicializar app
app = FastAPI(
    title="Proyecto Jupiter API",
    version="2.0.0",
    description="Integración del backend local con las capacidades operativas de Kitia",
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

uploads_root = Path("/app/data/uploads")
uploads_root.mkdir(parents=True, exist_ok=True)
app.mount("/media", StaticFiles(directory=str(uploads_root)), name="media")

# =============================================
# RUTAS PRINCIPALES
# =============================================

@app.get("/")
async def root():
    """Endpoint raíz"""
    return {
        "message": "Proyecto Jupiter API",
        "version": "2.0.0",
        "docs": "/docs",
        "redoc": "/redoc"
    }

@app.get("/health")
async def health_check():
    """Health check"""
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}


@app.on_event("startup")
def on_startup_init_db() -> None:
    LOGGER.info("event=startup_init_db")
    init_db()
    init_products_db()


@app.exception_handler(RequestValidationError)
async def request_validation_exception_handler(_request, exc: RequestValidationError):
    LOGGER.warning("event=request_validation_error errors=%s", exc.errors())
    return JSONResponse(
        status_code=422,
        content={"detail": "Bad Request on json body", "errors": exc.errors()},
    )

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
app.include_router(public_router, prefix="/api", tags=["Auth"])
app.include_router(kitia_router, prefix="/api", tags=["Proyecto Jupiter"])

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "src.api.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True
    )
