"""SQLAlchemy ORM models for Customer, Invoice, and InvoiceLine.

Customers are merchant-scoped. Invoices belong to both a merchant and a
customer. InvoiceLines decompose an invoice into line items. All
authoritative monetary amounts use BIGINT (integer minor units, paise).

TYPE_CHECKING imports are used for relationship type hints to avoid
circular imports at runtime. All models are collected in domain/models.py.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import (
    CHAR,
    BigInteger,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base
from .enums import InvoiceStatus

if TYPE_CHECKING:
    from .merchant import Merchant
    from .recovery import Payment, RecoveryCase


class Customer(Base):
    """Stores the merchant's B2B customers."""

    __tablename__ = "customers"

    __table_args__ = (
        Index("ix_customers_merchant_id", "merchant_id"),
        Index("ix_customers_merchant_external_id", "merchant_id", "external_customer_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        nullable=False,
    )
    merchant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("merchants.id", ondelete="RESTRICT"),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str | None] = mapped_column(String(320), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(32), nullable=True)
    gstin: Mapped[str | None] = mapped_column(String(32), nullable=True)
    external_customer_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    updated_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )

    # Relationships
    merchant: Mapped[Merchant] = relationship("Merchant", back_populates="customers")
    invoices: Mapped[list[Invoice]] = relationship(
        "Invoice", back_populates="customer", passive_deletes=True
    )
    recovery_cases: Mapped[list[RecoveryCase]] = relationship(
        "RecoveryCase", back_populates="customer", passive_deletes=True
    )


class Invoice(Base):
    """Stores customer financial obligations.

    All monetary amounts (total_amount, amount_paid) are stored in integer
    minor units (paise) using BIGINT. Do not use float.
    """

    __tablename__ = "invoices"

    __table_args__ = (
        UniqueConstraint(
            "merchant_id", "invoice_number", name="uq_invoices_merchant_invoice_number"
        ),
        CheckConstraint("total_amount >= 0", name="ck_invoices_total_amount"),
        CheckConstraint("amount_paid >= 0", name="ck_invoices_amount_paid_nonneg"),
        CheckConstraint(
            "amount_paid <= total_amount", name="ck_invoices_amount_paid_limit"
        ),
        Index("ix_invoices_merchant_id", "merchant_id"),
        Index("ix_invoices_customer_id", "customer_id"),
        Index("ix_invoices_due_date", "due_date"),
        Index("ix_invoices_status", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        nullable=False,
    )
    merchant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("merchants.id", ondelete="RESTRICT"),
        nullable=False,
    )
    customer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("customers.id", ondelete="RESTRICT"),
        nullable=False,
    )
    invoice_number: Mapped[str] = mapped_column(String(100), nullable=False)
    currency: Mapped[str] = mapped_column(CHAR(3), nullable=False)
    # BIGINT paise — do not use float
    total_amount: Mapped[int] = mapped_column(BigInteger, nullable=False)
    amount_paid: Mapped[int] = mapped_column(
        BigInteger, nullable=False, server_default="0"
    )
    issue_date: Mapped[Date] = mapped_column(Date, nullable=False)
    due_date: Mapped[Date] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default=InvoiceStatus.OUTSTANDING.value
    )
    external_reference: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    updated_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )

    # Relationships
    merchant: Mapped[Merchant] = relationship("Merchant", back_populates="invoices")
    customer: Mapped[Customer] = relationship("Customer", back_populates="invoices")
    lines: Mapped[list[InvoiceLine]] = relationship(
        "InvoiceLine", back_populates="invoice", passive_deletes=True
    )
    recovery_cases: Mapped[list[RecoveryCase]] = relationship(
        "RecoveryCase", back_populates="invoice", passive_deletes=True
    )
    payments: Mapped[list[Payment]] = relationship(
        "Payment", back_populates="invoice", passive_deletes=True
    )


class InvoiceLine(Base):
    """Stores invoice-level line items.

    unit_price, tax_amount, and line_total are all BIGINT paise.
    """

    __tablename__ = "invoice_lines"

    __table_args__ = (
        UniqueConstraint(
            "invoice_id", "line_number", name="uq_invoice_lines_invoice_line_number"
        ),
        CheckConstraint("quantity >= 0", name="ck_invoice_lines_quantity"),
        CheckConstraint("unit_price >= 0", name="ck_invoice_lines_unit_price"),
        CheckConstraint("tax_amount >= 0", name="ck_invoice_lines_tax_amount"),
        CheckConstraint("line_total >= 0", name="ck_invoice_lines_line_total"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        nullable=False,
    )
    invoice_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("invoices.id", ondelete="RESTRICT"),
        nullable=False,
    )
    line_number: Mapped[int] = mapped_column(Integer, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    product_code: Mapped[str | None] = mapped_column(String(100), nullable=True)
    quantity: Mapped[float] = mapped_column(Numeric(18, 4), nullable=False)
    # BIGINT paise — do not use float
    unit_price: Mapped[int] = mapped_column(BigInteger, nullable=False)
    tax_amount: Mapped[int] = mapped_column(
        BigInteger, nullable=False, server_default="0"
    )
    line_total: Mapped[int] = mapped_column(BigInteger, nullable=False)
    created_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )

    # Relationships
    invoice: Mapped[Invoice] = relationship("Invoice", back_populates="lines")
