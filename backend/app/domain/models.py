"""Central model registry — imports all domain models in dependency order.

This module is the single place that triggers SQLAlchemy mapper configuration
for all domain entities. Import this module (or the domain package) before
using Base.metadata for migrations or table creation.
"""

from .invoice import (
    Customer,  # noqa: F401
    Invoice,  # noqa: F401
    InvoiceLine,  # noqa: F401
)
from .merchant import (
    Merchant,  # noqa: F401
    MerchantPolicy,  # noqa: F401
)
from .recovery import (
    AgentRun,  # noqa: F401
    AuditEvent,  # noqa: F401
    Dispute,  # noqa: F401
    Evidence,  # noqa: F401
    HumanApproval,  # noqa: F401
    Outreach,  # noqa: F401
    Payment,  # noqa: F401
    PolicyDecision,  # noqa: F401
    RecoveryAction,  # noqa: F401
    RecoveryCase,  # noqa: F401
    ResolutionProposal,  # noqa: F401
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
