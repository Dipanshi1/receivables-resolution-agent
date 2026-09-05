from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel


class InvoiceLineItemRequest(BaseModel):
    line_number: int
    description: str
    quantity: float
    unit_price: int
    tax_amount: int = 0
    line_total: int


class CreateInvoiceRequest(BaseModel):
    customer_id: UUID
    invoice_number: str
    currency: str = "INR"
    total_amount: int
    amount_paid: int = 0
    issue_date: date
    due_date: date
    lines: list[InvoiceLineItemRequest] = []


class InvoiceResponse(BaseModel):
    id: UUID
    merchant_id: UUID
    customer_id: UUID
    invoice_number: str
    currency: str
    total_amount_minor: int
    amount_paid_minor: int
    issue_date: date
    due_date: date
    status: str
    created_at: datetime
    updated_at: datetime
