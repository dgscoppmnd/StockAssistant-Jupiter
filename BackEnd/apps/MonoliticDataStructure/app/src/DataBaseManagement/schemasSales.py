"""Contracts for operational sales; quantities use the selected unit on drafts."""
from datetime import date
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class SalesRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    operation_key: str = Field(min_length=8, max_length=120)


class SalesLine(BaseModel):
    model_config = ConfigDict(extra="forbid")
    product_id: int = Field(gt=0)
    quantity: Decimal = Field(gt=0, max_digits=18, decimal_places=4)
    unit_code: str = Field(min_length=1, max_length=20)
    unit_price: Decimal = Field(ge=0, max_digits=18, decimal_places=4)
    discount_percent: Decimal = Field(default=Decimal("0"), ge=0, le=100, decimal_places=4)
    tax_percent: Decimal = Field(default=Decimal("0"), ge=0, le=100, decimal_places=4)


class OrderDraft(SalesRequest):
    client_id: int = Field(gt=0)
    warehouse_id: int = Field(gt=0)
    address_association_id: int | None = Field(default=None, gt=0)
    order_date: date = Field(default_factory=date.today)
    currency_code: str = Field(min_length=3, max_length=3, pattern="^[A-Z]{3}$")
    reference: str | None = Field(default=None, max_length=200)
    notes: str | None = Field(default=None, max_length=2000)
    lines: list[SalesLine] = Field(min_length=1, max_length=200)

    @model_validator(mode="after")
    def distinct_products(self):
        ids = [line.product_id for line in self.lines]
        if len(ids) != len(set(ids)):
            raise ValueError("No repitas productos en un pedido; reúne su cantidad en una línea.")
        return self


class OperationLine(BaseModel):
    model_config = ConfigDict(extra="forbid")
    line_id: int = Field(gt=0)
    quantity: Decimal = Field(gt=0, max_digits=18, decimal_places=4)


class OrderOperation(SalesRequest):
    lines: list[OperationLine] = Field(min_length=1, max_length=200)
    reason: str = Field(default="Operación de ventas", min_length=1, max_length=500)

    @model_validator(mode="after")
    def distinct_lines(self):
        ids = [line.line_id for line in self.lines]
        if len(ids) != len(set(ids)):
            raise ValueError("No repitas líneas en una operación.")
        return self


class ReasonRequest(SalesRequest):
    reason: str = Field(min_length=3, max_length=500)


class InvoiceDraft(SalesRequest):
    sales_order_id: int = Field(gt=0)
    invoice_date: date = Field(default_factory=date.today)
    due_date: date | None = None
    reference: str | None = Field(default=None, max_length=200)
    notes: str | None = Field(default=None, max_length=2000)
    lines: list[OperationLine] = Field(min_length=1, max_length=200)

    @model_validator(mode="after")
    def valid_dates_and_lines(self):
        if self.due_date and self.due_date < self.invoice_date:
            raise ValueError("El vencimiento no puede preceder a la fecha de factura.")
        ids = [line.line_id for line in self.lines]
        if len(ids) != len(set(ids)):
            raise ValueError("No repitas líneas en una factura.")
        return self
