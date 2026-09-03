import logging
import os
import subprocess
import sys
import smtplib
from datetime import datetime, timezone
from email.message import EmailMessage
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from DataBaseManagement.dbConectionPostgres import get_db_products
from DataBaseManagement.dbManagementProducts import insert_product

router = APIRouter(prefix="/tools", tags=["tools"])
logger = logging.getLogger("api.endpointTools")


class ProductToolCreatePayload(BaseModel):
    name_product: str = Field(min_length=1, max_length=200)
    description_product: str | None = Field(default=None, max_length=1000)
    price: float | None = None
    final_price: float | None = None
    supplier: str | None = Field(default=None, max_length=200)
    link: str | None = Field(default=None, max_length=255)
    cdgo_producto_externo: str | None = Field(default=None, max_length=200)
    currency: str | None = Field(default="USD", max_length=50)


class UpgradeLibrariesPayload(BaseModel):
    package_list: list[str]


class ToolEmailPayload(BaseModel):
    to_email: str
    subject: str = Field(min_length=1, max_length=200)
    body: str = Field(min_length=1)


def tool_search_products_db(connection: Any, query: str, limit: int = 10) -> list[dict[str, Any]]:
    if not query.strip():
        return []

    sql = """
        SELECT
            pk_product,
            TRIM(BOTH FROM name_product) AS name_product,
            TRIM(BOTH FROM supplier) AS supplier,
            TRIM(BOTH FROM link) AS link,
            price,
            final_price,
            disabled,
            last_update
        FROM public.productos
        WHERE name_product ILIKE %s
            OR description_product ILIKE %s
            OR supplier ILIKE %s
        ORDER BY last_update DESC NULLS LAST, pk_product DESC
        LIMIT %s
    """

    like = f"%{query.strip()}%"
    with connection.cursor() as cursor:
        cursor.execute(sql, [like, like, like, limit])
        rows = cursor.fetchall()

    data: list[dict[str, Any]] = []
    for row in rows:
        data.append(
            {
                "pk_product": row[0],
                "name_product": row[1],
                "supplier": row[2],
                "link": row[3],
                "price": row[4],
                "final_price": row[5],
                "disabled": row[6],
                "last_update": row[7],
            }
        )

    return data


def tool_save_product(connection: Any, payload: ProductToolCreatePayload) -> dict[str, Any]:
    row = {
        "cdgo_producto_externo": payload.cdgo_producto_externo,
        "name_product": payload.name_product.strip(),
        "description_product": payload.description_product,
        "disabled": False,
        "price": payload.price if payload.price is not None else 0,
        "unit": 1,
        "final_price": payload.final_price if payload.final_price is not None else payload.price or 0,
        "discount": 0,
        "discount_end_date": None,
        "fk_currency": 1,
        "currency": payload.currency,
        "user_rating": 0,
        "link": payload.link,
        "creation_date": datetime.now(timezone.utc),
        "fk_last_update_user": 1,
        "last_update": datetime.now(timezone.utc),
        "supplier": payload.supplier,
    }
    return insert_product(row, connection=connection)


def tool_upgrade_libraries(packages: list[str]) -> dict[str, Any]:
    allowed = {
        "requests",
        "beautifulsoup4",
        "lxml",
        "httpx",
        "pydantic",
        "fastapi",
        "uvicorn",
    }
    sanitized = [pkg.strip() for pkg in packages if pkg and pkg.strip()]
    if not sanitized:
        raise ValueError("Debes indicar al menos una libreria")

    blocked = [pkg for pkg in sanitized if pkg.lower() not in allowed]
    if blocked:
        raise ValueError(f"No permitido en upgrade automatico: {', '.join(blocked)}")

    cmd = [sys.executable, "-m", "pip", "install", "--upgrade", *sanitized]
    completed = subprocess.run(cmd, capture_output=True, text=True, check=False)
    return {
        "command": " ".join(cmd),
        "return_code": completed.returncode,
        "stdout": completed.stdout[-4000:],
        "stderr": completed.stderr[-4000:],
    }


def tool_send_email(payload: ToolEmailPayload) -> dict[str, Any]:
    smtp_host = os.getenv("KITIA_SMTP_HOST", "smtp.gmail.com")
    smtp_port = int(os.getenv("KITIA_SMTP_PORT", "587"))
    smtp_user = os.getenv("KITIA_SMTP_USER")
    smtp_password = os.getenv("KITIA_SMTP_PASSWORD")

    if not smtp_user or not smtp_password:
        raise ValueError(
            "Configura KITIA_SMTP_USER y KITIA_SMTP_PASSWORD para enviar correo desde soporte@kitrobotic.com"
        )

    message = EmailMessage()
    message["From"] = smtp_user
    message["To"] = payload.to_email
    message["Subject"] = payload.subject
    message.set_content(payload.body)

    with smtplib.SMTP(smtp_host, smtp_port, timeout=20) as smtp:
        smtp.starttls()
        smtp.login(smtp_user, smtp_password)
        smtp.send_message(message)

    return {
        "status": "sent",
        "to": payload.to_email,
        "subject": payload.subject,
    }


@router.get("/products/search-db")
def products_search_db(query: str = Query(..., min_length=2), limit: int = Query(10, ge=1, le=50), db=Depends(get_db_products)):
    logger.info("event=tool_products_search query=%s limit=%s", query, limit)
    rows = tool_search_products_db(connection=db, query=query, limit=limit)
    return {
        "query": query,
        "count": len(rows),
        "items": rows,
    }


@router.post("/products/save")
def products_save(payload: ProductToolCreatePayload, db=Depends(get_db_products)):
    logger.info("event=tool_products_save name=%s", payload.name_product)
    try:
        created = tool_save_product(connection=db, payload=payload)
        return {"status": "created", "record": created}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"No fue posible guardar el producto: {exc}") from exc


@router.post("/libraries/upgrade")
def upgrade_libraries(payload: UpgradeLibrariesPayload):
    logger.info("event=tool_upgrade_libraries package_count=%s", len(payload.package_list))
    try:
        result = tool_upgrade_libraries(payload.package_list)
        if result["return_code"] != 0:
            raise HTTPException(status_code=500, detail=result)
        return result
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/email/send")
def send_email(payload: ToolEmailPayload):
    logger.info("event=tool_send_email to=%s", payload.to_email)
    try:
        return tool_send_email(payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"No fue posible enviar el correo: {exc}") from exc
