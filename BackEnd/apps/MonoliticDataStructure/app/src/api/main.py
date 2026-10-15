"""Aplicación principal FastAPI de Proyecto Jupiter."""

import logging
import mimetypes
import re
from pathlib import Path
from datetime import datetime

from secrets_loader import load_secrets_from_ssm

load_secrets_from_ssm()  # antes de importar módulos que leen la configuración del entorno

from fastapi import Depends, FastAPI, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from .config import settings
from .database import engine, Base
from .routes import products, inventory, sales, suppliers, logistics, metrics, analytics, knowledge
from endpoints.endpoints import public_router, router as stockassistant_router
from DataBaseManagement.dbConectionPostgres import (
    init_db,
    init_products_db,
    _get_postgres_connection_server,
)
from executive_service import start_automation_worker, stop_automation_worker
from knowledge_schema import ensure_knowledge_schema
import file_storage
from knowledge_worker import process_pending, start_knowledge_worker
from security import require_api_key


import os
import sys
from pathlib import Path

# Lambda: FS de solo lectura salvo /tmp, sin hilos persistentes y usuario sin DDL
IS_LAMBDA = bool(os.getenv("AWS_LAMBDA_FUNCTION_NAME"))

if not IS_LAMBDA:
    Base.metadata.create_all(bind=engine)
LOGGER = logging.getLogger("src.api.main")

app = FastAPI(
    title="Proyecto Jupiter API",
    version="2.0.0",
    description="Integración del backend local con las capacidades operativas de StockAssistant",
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

uploads_root = Path(os.getenv("UPLOADS_DIR") or ("/tmp/uploads" if IS_LAMBDA else "/app/data/uploads"))
uploads_root.mkdir(parents=True, exist_ok=True)
app.mount("/media", StaticFiles(directory=str(uploads_root)), name="media")


@app.get("/")
async def root():
    return {
        "message": "Proyecto Jupiter API",
        "version": "2.0.0",
        "docs": "/docs",
        "redoc": "/redoc",
    }


@app.get("/health")
async def health_check():
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}


@app.on_event("startup")
def on_startup_init_db() -> None:
    if IS_LAMBDA:
        LOGGER.info("event=startup_skipped reason=lambda")
        return
    LOGGER.info("event=startup_init_db")
    init_db()
    init_products_db()
    connection = _get_postgres_connection_server()
    try:
        ensure_knowledge_schema(connection)
    finally:
        connection.close()
    app.state.knowledge_stop = start_knowledge_worker(_get_postgres_connection_server)
    start_automation_worker(_get_postgres_connection_server)


@app.on_event("shutdown")
def on_shutdown() -> None:
    if hasattr(app.state, "knowledge_stop"):
        app.state.knowledge_stop.set()
    stop_automation_worker()


@app.exception_handler(RequestValidationError)
async def request_validation_exception_handler(_request, exc: RequestValidationError):
    LOGGER.warning("event=request_validation_error errors=%s", exc.errors())
    return JSONResponse(
        status_code=422,
        content={"detail": "Bad Request on json body", "errors": exc.errors()},
    )


PROTECTED = [Depends(require_api_key)]
app.include_router(products.router, prefix="/api/v1/products", tags=["Products"], dependencies=PROTECTED)
app.include_router(inventory.router, prefix="/api/v1/inventory", tags=["Inventory"], dependencies=PROTECTED)
app.include_router(sales.router, prefix="/api/v1/sales", tags=["Sales"], dependencies=PROTECTED)
app.include_router(suppliers.router, prefix="/api/v1/suppliers", tags=["Suppliers"], dependencies=PROTECTED)
app.include_router(logistics.router, prefix="/api/v1/logistics", tags=["Logistics"], dependencies=PROTECTED)
app.include_router(metrics.router, prefix="/api/v1/metrics", tags=["Metrics"], dependencies=PROTECTED)
app.include_router(analytics.router, prefix="/api/v1/analytics", tags=["Analytics"], dependencies=PROTECTED)
app.include_router(knowledge.router, prefix="/api/v1/knowledge", tags=["Knowledge RAG"], dependencies=PROTECTED)
app.include_router(public_router, prefix="/api", tags=["Auth"])
app.include_router(stockassistant_router, prefix="/api", tags=["Proyecto Jupiter"])


@app.post("/internal/index", include_in_schema=False)
def internal_index(event: dict):
    """Destino de la invocación asíncrona (AWS_LWA_PASS_THROUGH_PATH); exige el secreto compartido."""
    if not file_storage.valid_trigger_token(event.get("jupiter_index")):
        return JSONResponse(status_code=403, content={"detail": "forbidden"})
    process_pending(_get_postgres_connection_server)
    return {"status": "done"}


@app.get("/api/media/products/{filename}", include_in_schema=False)
def product_image(filename: str):
    if not file_storage.bucket() or not re.fullmatch(r"[0-9a-f]{32}\.[a-z0-9]{2,5}", filename):
        return JSONResponse(status_code=404, content={"detail": "Not found"})
    data = file_storage.read_bytes(f"products/{filename}")
    if data is None:
        return JSONResponse(status_code=404, content={"detail": "Not found"})
    media_type = mimetypes.guess_type(filename)[0] or "application/octet-stream"
    return Response(
        content=data,
        media_type=media_type,
        headers={
            "Cache-Control": "public, max-age=86400",
            "X-Content-Type-Options": "nosniff",
            "Content-Security-Policy": "default-src 'none'; style-src 'unsafe-inline'",
        },
    )

if __name__ == "__main__":
    import uvicorn

    uvicorn.run("src.api.main:app", host="0.0.0.0", port=8000, reload=True)
