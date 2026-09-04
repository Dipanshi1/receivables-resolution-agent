"""Domain layer — exports Base, metadata, all enums, and all domain models.

Import `from app.domain import models` or individual model classes before
accessing Base.metadata for schema generation or Alembic migrations.
"""

from .base import Base, metadata
from .enums import (
    AgentType,
    DisputeStatus,
    DisputeType,
    EvidenceType,
    HumanApprovalDecision,
    InvoiceStatus,
    IssueType,
    OutreachChannel,
    OutreachDirection,
    OutreachStatus,
    PaymentStatus,
    PolicyDecisionResult,
    RecoveryActionStatus,
    RecoveryActionType,
    RecoveryCaseStatus,
    ResolutionProposalAction,
    ResolutionProposalStatus,
    RiskLevel,
)
from .models import (
    AgentRun,
    AuditEvent,
    Customer,
    Dispute,
    Evidence,
    HumanApproval,
    Invoice,
    InvoiceLine,
    Merchant,
    MerchantPolicy,
    Outreach,
    Payment,
    PolicyDecision,
    RecoveryAction,
    RecoveryCase,
    ResolutionProposal,
)

__all__ = [
    # Core infrastructure
    "Base",
    "metadata",
    # Enums
    "AgentType",
    "DisputeStatus",
    "DisputeType",
    "EvidenceType",
    "HumanApprovalDecision",
    "InvoiceStatus",
    "IssueType",
    "OutreachChannel",
    "OutreachDirection",
    "OutreachStatus",
    "PaymentStatus",
    "PolicyDecisionResult",
    "RecoveryActionStatus",
    "RecoveryActionType",
    "RecoveryCaseStatus",
    "ResolutionProposalAction",
    "ResolutionProposalStatus",
    "RiskLevel",
    # Domain models
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
