"""Central model registry — imports all domain models in dependency order.

This module is the single place that triggers SQLAlchemy mapper configuration
for all domain entities. Import this module (or the domain package) before
using Base.metadata for migrations or table creation.

Import order matters for FK resolution: parent tables before child tables.
"""

# Root entity (no FK dependencies)
from .merchant import Merchant, MerchantPolicy  # noqa: F401

# Customer depends on Merchant
from .invoice import Customer  # noqa: F401

# Invoice depends on Merchant + Customer; InvoiceLine depends on Invoice
from .invoice import Invoice, InvoiceLine  # noqa: F401

# RecoveryCase depends on Merchant + Customer + Invoice
from .recovery import RecoveryCase  # noqa: F401

# All remaining recovery entities depend on RecoveryCase
from .recovery import (  # noqa: F401
    AgentRun,
    AuditEvent,
    Dispute,
    Evidence,
    HumanApproval,
    Outreach,
    Payment,
    PolicyDecision,
    RecoveryAction,
    ResolutionProposal,
)

__all__ = [
    "Merchant",
    "MerchantPolicy",
    "Customer",
    "Invoice",
    "InvoiceLine",
    "RecoveryCase",
    "Dispute",
    "Evidence",
    "AgentRun",
    "ResolutionProposal",
    "PolicyDecision",
    "RecoveryAction",
    "Payment",
    "Outreach",
    "HumanApproval",
    "AuditEvent",
]
