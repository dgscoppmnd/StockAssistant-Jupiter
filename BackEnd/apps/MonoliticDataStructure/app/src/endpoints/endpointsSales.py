"""Session-authenticated operational sales endpoints."""
from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from psycopg2 import IntegrityError

from DataBaseManagement.dbConectionPostgres import get_db_products
from DataBaseManagement.schemasSales import (
    InvoiceDraft,
    OrderDraft,
    OrderOperation,
    ReasonRequest,
    SalesRequest,
)
from inventory_service import InventoryError, InventoryService
from sales_service import SalesService
from security import extract_bearer_token, verify_session_token

router = APIRouter(prefix="/sales", tags=["Operational sales"])


def sales_user(db, authorization):
    claims = verify_session_token(extract_bearer_token(authorization))
    if not claims or not isinstance(claims.get("user_id"), int):
        raise HTTPException(401, "Inicia sesión para acceder a ventas.")
    user = InventoryService(db)._fetchone(
        """
        SELECT id,email,sales_permissions FROM public.users WHERE id=%s AND status=1
        AND (startline IS NULL OR startline<=CURRENT_TIMESTAMP)
        AND (deadline IS NULL OR deadline>CURRENT_TIMESTAMP)
    """,
        (claims["user_id"],),
    )
    if not user:
        raise HTTPException(401, "La cuenta no está activa o ha caducado.")
    return user


def service(db=Depends(get_db_products), authorization: str | None = Header(default=None)):
    return SalesService(db, sales_user(db, authorization))


Service = Annotated[SalesService, Depends(service)]


def execute(fn, *args):
    try:
        return fn(*args)
    except InventoryError as exc:
        raise HTTPException(exc.status_code, str(exc)) from exc
    except IntegrityError as exc:
        raise HTTPException(
            409, "Conflicto de datos o documento vinculado; actualiza la vista."
        ) from exc


@router.get("/permissions")
def permissions(svc: Service):
    return {"permissions": svc.user["sales_permissions"]}


@router.get("/clients")
def clients(
    svc: Service,
    q: str = Query(default="", max_length=200),
    page: int = Query(default=1, ge=1),
    size: int = Query(default=20, ge=1, le=50),
):
    execute(svc.permit, "read")
    return svc._fetchall(
        """
        SELECT pk_client AS id,client_code,name FROM public.clients
        WHERE name ILIKE %s OR client_code ILIKE %s ORDER BY name,pk_client LIMIT %s OFFSET %s
    """,
        ("%" + q + "%", "%" + q + "%", size, (page - 1) * size),
    )


@router.get("/orders")
def orders(
    svc: Service,
    q: str = Query(default="", max_length=200),
    status: str | None = None,
    client_id: int | None = Query(default=None, gt=0),
    date_from: date | None = None,
    date_to: date | None = None,
    page: int = Query(default=1, ge=1),
    size: int = Query(default=10, ge=1, le=100),
):
    return execute(
        svc.list_documents,
        "order",
        locals_filter(q, status, client_id, date_from, date_to, page, size),
    )


def locals_filter(q, status, client_id, date_from, date_to, page, size):
    if date_from and date_to and date_from > date_to:
        raise HTTPException(400, "El periodo de fechas no es válido.")
    return dict(
        q=q,
        status=status,
        client_id=client_id,
        date_from=date_from,
        date_to=date_to,
        page=page,
        size=size,
    )


@router.post("/orders", status_code=201)
def create_order(payload: OrderDraft, svc: Service):
    return execute(svc.save_order, payload.model_dump())


@router.get("/orders/{order_id}")
def order_detail(order_id: int, svc: Service):
    return execute(svc.detail, "order", order_id)


@router.put("/orders/{order_id}")
def edit_order(order_id: int, payload: OrderDraft, svc: Service):
    return execute(svc.save_order, payload.model_dump(), order_id)


@router.delete("/orders/{order_id}")
def delete_order(order_id: int, payload: SalesRequest, svc: Service):
    return execute(svc.delete_order, order_id, payload.model_dump())


@router.post("/orders/{order_id}/reserve")
def reserve_order(order_id: int, payload: OrderOperation, svc: Service):
    return execute(svc.reserve_order, order_id, payload.model_dump())


@router.post("/orders/{order_id}/dispatch")
def dispatch_order(order_id: int, payload: OrderOperation, svc: Service):
    return execute(svc.dispatch_order, order_id, payload.model_dump())


@router.post("/orders/{order_id}/cancel")
def cancel_order(order_id: int, payload: ReasonRequest, svc: Service):
    return execute(svc.cancel_order, order_id, payload.model_dump())


@router.post("/orders/{order_id}/return")
def return_order(order_id: int, payload: OrderOperation, svc: Service):
    return execute(svc.return_order, order_id, payload.model_dump())


@router.get("/invoices")
def invoices(
    svc: Service,
    q: str = Query(default="", max_length=200),
    status: str | None = None,
    client_id: int | None = Query(default=None, gt=0),
    date_from: date | None = None,
    date_to: date | None = None,
    page: int = Query(default=1, ge=1),
    size: int = Query(default=10, ge=1, le=100),
):
    return execute(
        svc.list_documents,
        "invoice",
        locals_filter(q, status, client_id, date_from, date_to, page, size),
    )


@router.post("/invoices", status_code=201)
def create_invoice(payload: InvoiceDraft, svc: Service):
    return execute(svc.save_invoice, payload.model_dump())


@router.get("/invoices/{invoice_id}")
def invoice_detail(invoice_id: int, svc: Service):
    return execute(svc.detail, "invoice", invoice_id)


@router.put("/invoices/{invoice_id}")
def edit_invoice(invoice_id: int, payload: InvoiceDraft, svc: Service):
    return execute(svc.save_invoice, payload.model_dump(), invoice_id)


@router.post("/invoices/{invoice_id}/issue")
def issue_invoice(invoice_id: int, payload: SalesRequest, svc: Service):
    return execute(svc.invoice_action, invoice_id, payload.model_dump(), "issue")


@router.delete("/invoices/{invoice_id}")
def delete_invoice(invoice_id: int, payload: SalesRequest, svc: Service):
    return execute(svc.invoice_action, invoice_id, payload.model_dump(), "delete")


@router.post("/invoices/{invoice_id}/void")
def void_invoice(invoice_id: int, payload: ReasonRequest, svc: Service):
    return execute(svc.invoice_action, invoice_id, payload.model_dump(), "void")
