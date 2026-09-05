from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db_session, get_merchant_id
from app.api.errors import raise_forbidden, raise_not_found
from app.api.v1.schemas.invoice_schemas import CreateInvoiceRequest, InvoiceResponse
from app.domain.invoice import Customer, Invoice

router = APIRouter()


@router.post("", response_model=InvoiceResponse, status_code=201)
async def create_invoice(
    request: CreateInvoiceRequest,
    merchant_id: Annotated[UUID, Depends(get_merchant_id)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
):
    # Verify customer belongs to merchant
    customer = await session.get(Customer, request.customer_id)
    if not customer or customer.merchant_id != merchant_id:
        raise_forbidden()

    invoice = Invoice(
        merchant_id=merchant_id,
        customer_id=request.customer_id,
        invoice_number=request.invoice_number,
        currency=request.currency,
        total_amount=request.total_amount,
        amount_paid=request.amount_paid,
        issue_date=request.issue_date,
        due_date=request.due_date,
    )
    session.add(invoice)
    await session.commit()
    await session.refresh(invoice)

    return InvoiceResponse(
        id=invoice.id,
        merchant_id=invoice.merchant_id,
        customer_id=invoice.customer_id,
        invoice_number=invoice.invoice_number,
        currency=invoice.currency,
        total_amount_minor=invoice.total_amount,
        amount_paid_minor=invoice.amount_paid,
        issue_date=invoice.issue_date,
        due_date=invoice.due_date,
        status=invoice.status,
        created_at=invoice.created_at,
        updated_at=invoice.updated_at,
    )


@router.get("/{invoice_id}", response_model=InvoiceResponse)
async def get_invoice(
    invoice_id: UUID,
    merchant_id: Annotated[UUID, Depends(get_merchant_id)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
):
    invoice = await session.get(Invoice, invoice_id)
    if not invoice:
        raise_not_found("Invoice", str(invoice_id))
    if invoice.merchant_id != merchant_id:
        raise_forbidden()

    return InvoiceResponse(
        id=invoice.id,
        merchant_id=invoice.merchant_id,
        customer_id=invoice.customer_id,
        invoice_number=invoice.invoice_number,
        currency=invoice.currency,
        total_amount_minor=invoice.total_amount,
        amount_paid_minor=invoice.amount_paid,
        issue_date=invoice.issue_date,
        due_date=invoice.due_date,
        status=invoice.status,
        created_at=invoice.created_at,
        updated_at=invoice.updated_at,
    )
