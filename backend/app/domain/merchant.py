"""SQLAlchemy ORM model for merchants and merchant-scoped policies.

Merchant is the root ownership entity. MerchantPolicy stores versioned,
immutable recovery rule configurations. Policy records must never be
overwritten; each change creates a new version record to allow reconstruction
of historical decisions.

TYPE_CHECKING imports are used for relationship type hints to avoid
circular imports at runtime. All models are collected in domain/models.py.
"""

from __future__ import annotations

import uuid
from datetime import time
from typing import TYPE_CHECKING

from sqlalchemy import (
    CHAR,
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Time,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base

if TYPE_CHECKING:
    from .invoice import Customer, Invoice
    from .recovery import RecoveryCase


class Merchant(Base):
    """Stores the business using the Receivables Resolution Agent."""

    __tablename__ = "merchants"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    currency: Mapped[str] = mapped_column(CHAR(3), nullable=False)
    created_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    updated_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )

    # Relationships
    customers: Mapped[list[Customer]] = relationship(
        "Customer", back_populates="merchant", passive_deletes=True
    )
    policies: Mapped[list[MerchantPolicy]] = relationship(
        "MerchantPolicy", back_populates="merchant", passive_deletes=True
    )
    invoices: Mapped[list[Invoice]] = relationship(
        "Invoice", back_populates="merchant", passive_deletes=True
    )
    recovery_cases: Mapped[list[RecoveryCase]] = relationship(
        "RecoveryCase", back_populates="merchant", passive_deletes=True
    )


class MerchantPolicy(Base):
    """Versioned, immutable merchant-specific recovery rules.

    Historical policy records must never be overwritten; each policy
    change must create a new version record to allow reconstruction
    of historical decisions.
    """

    __tablename__ = "merchant_policies"

    __table_args__ = (
        UniqueConstraint("merchant_id", "version", name="uq_merchant_policies_version"),
        CheckConstraint("max_auto_recovery_amount >= 0", name="ck_policy_max_auto_recovery"),
        CheckConstraint(
            "max_concession_percent >= 0 AND max_concession_percent <= 100",
            name="ck_policy_concession_percent",
        ),
        CheckConstraint("max_concession_amount >= 0", name="ck_policy_concession_amount"),
        CheckConstraint("max_touchpoints >= 0", name="ck_policy_max_touchpoints"),
        CheckConstraint("touchpoint_window_days > 0", name="ck_policy_touchpoint_window"),
        CheckConstraint("high_value_threshold >= 0", name="ck_policy_high_value_threshold"),
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
    version: Mapped[str] = mapped_column(String(32), nullable=False)
    # Integer minor units (paise) for monetary amounts
    max_auto_recovery_amount: Mapped[int] = mapped_column(BigInteger, nullable=False)
    max_concession_percent: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False)
    max_concession_amount: Mapped[int] = mapped_column(BigInteger, nullable=False)
    max_touchpoints: Mapped[int] = mapped_column(Integer, nullable=False)
    touchpoint_window_days: Mapped[int] = mapped_column(Integer, nullable=False)
    quiet_hours_start: Mapped[time] = mapped_column(Time, nullable=False)
    quiet_hours_end: Mapped[time] = mapped_column(Time, nullable=False)
    high_value_threshold: Mapped[int] = mapped_column(BigInteger, nullable=False)
    effective_from: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    effective_to: Mapped[DateTime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )

    # Relationships
    merchant: Mapped[Merchant] = relationship("Merchant", back_populates="policies")
