"""SQLAlchemy ORM models for the core recovery workflow entities.

Covers: RecoveryCase, Dispute, Evidence, AgentRun, ResolutionProposal,
PolicyDecision, RecoveryAction, Payment, Outreach, HumanApproval, AuditEvent.

All authoritative monetary fields use BIGINT (integer paise). No float.

TYPE_CHECKING imports are used for relationship type hints to avoid
circular imports at runtime. All models are collected in domain/models.py.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import (
    CHAR,
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base
from .enums import (
    DisputeStatus,
    HumanApprovalDecision,
    PaymentStatus,
    RecoveryActionStatus,
    RecoveryCaseStatus,
    ResolutionProposalStatus,
)

if TYPE_CHECKING:
    from .invoice import Customer, Invoice
    from .merchant import Merchant


class RecoveryCase(Base):
    """Represents the operational recovery workflow for an invoice.

    Tracks all monetary decomposition fields (claimed, verified, collectible,
    safely recoverable, recovered, remaining) as BIGINT paise. The locked flag
    enforces AUTOMATION_LOCKED state to prevent automated execution when legal
    or high-risk conditions are present.
    """

    __tablename__ = "recovery_cases"

    __table_args__ = (
        CheckConstraint(
            "claimed_disputed_amount >= 0", name="ck_rc_claimed_disputed_nonneg"
        ),
        CheckConstraint(
            "verified_disputed_amount IS NULL OR verified_disputed_amount >= 0",
            name="ck_rc_verified_disputed_nonneg",
        ),
        CheckConstraint(
            "collectible_amount IS NULL OR collectible_amount >= 0",
            name="ck_rc_collectible_nonneg",
        ),
        CheckConstraint(
            "safely_recoverable_amount IS NULL OR safely_recoverable_amount >= 0",
            name="ck_rc_safely_recoverable_nonneg",
        ),
        CheckConstraint("recovered_amount >= 0", name="ck_rc_recovered_nonneg"),
        CheckConstraint("remaining_amount >= 0", name="ck_rc_remaining_nonneg"),
        CheckConstraint("touchpoint_count >= 0", name="ck_rc_touchpoint_count_nonneg"),
        Index("ix_recovery_cases_merchant_id", "merchant_id"),
        Index("ix_recovery_cases_merchant_status", "merchant_id", "status"),
        Index("ix_recovery_cases_invoice_id", "invoice_id"),
        Index("ix_recovery_cases_status", "status"),
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
    invoice_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("invoices.id", ondelete="RESTRICT"),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(
        String(40), nullable=False, default=RecoveryCaseStatus.OPENED.value
    )
    issue_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    risk_level: Mapped[str | None] = mapped_column(String(32), nullable=True)
    # All monetary values are BIGINT paise — do not use float
    claimed_disputed_amount: Mapped[int] = mapped_column(
        BigInteger, nullable=False, server_default="0"
    )
    verified_disputed_amount: Mapped[int | None] = mapped_column(
        BigInteger, nullable=True
    )
    collectible_amount: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    safely_recoverable_amount: Mapped[int | None] = mapped_column(
        BigInteger, nullable=True
    )
    recovered_amount: Mapped[int] = mapped_column(
        BigInteger, nullable=False, server_default="0"
    )
    remaining_amount: Mapped[int] = mapped_column(
        BigInteger, nullable=False, server_default="0"
    )
    resolution_confidence: Mapped[float | None] = mapped_column(
        Numeric(5, 4), nullable=True
    )
    touchpoint_count: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="0"
    )
    locked: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="false"
    )
    lock_reason: Mapped[str | None] = mapped_column(String(128), nullable=True)
    created_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    updated_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )

    # Relationships
    merchant: Mapped[Merchant] = relationship(
        "Merchant", back_populates="recovery_cases"
    )
    customer: Mapped[Customer] = relationship(
        "Customer", back_populates="recovery_cases"
    )
    invoice: Mapped[Invoice] = relationship(
        "Invoice", back_populates="recovery_cases"
    )
    disputes: Mapped[list[Dispute]] = relationship(
        "Dispute", back_populates="case", passive_deletes=True
    )
    evidence: Mapped[list[Evidence]] = relationship(
        "Evidence", back_populates="case", passive_deletes=True
    )
    agent_runs: Mapped[list[AgentRun]] = relationship(
        "AgentRun", back_populates="case", passive_deletes=True
    )
    resolution_proposals: Mapped[list[ResolutionProposal]] = relationship(
        "ResolutionProposal", back_populates="case", passive_deletes=True
    )
    policy_decisions: Mapped[list[PolicyDecision]] = relationship(
        "PolicyDecision", back_populates="case", passive_deletes=True
    )
    recovery_actions: Mapped[list[RecoveryAction]] = relationship(
        "RecoveryAction", back_populates="case", passive_deletes=True
    )
    payments: Mapped[list[Payment]] = relationship(
        "Payment", back_populates="case", passive_deletes=True
    )
    outreach: Mapped[list[Outreach]] = relationship(
        "Outreach", back_populates="case", passive_deletes=True
    )
    human_approvals: Mapped[list[HumanApproval]] = relationship(
        "HumanApproval", back_populates="case", passive_deletes=True
    )
    audit_events: Mapped[list[AuditEvent]] = relationship(
        "AuditEvent", back_populates="case", passive_deletes=True
    )


class Dispute(Base):
    """Stores commercial invoice disputes.

    Separates customer_claim (untrusted) from verified_amount (evidence-backed).
    Do not collapse these concepts into a single field.
    """

    __tablename__ = "disputes"

    __table_args__ = (Index("ix_disputes_case_id", "case_id"),)

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        nullable=False,
    )
    case_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("recovery_cases.id", ondelete="RESTRICT"),
        nullable=False,
    )
    type: Mapped[str] = mapped_column(String(64), nullable=False)
    customer_claim: Mapped[str] = mapped_column(Text, nullable=False)
    # BIGINT paise — customer-stated, not verified
    claimed_amount: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    # BIGINT paise — evidence-supported
    verified_amount: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default=DisputeStatus.OPEN.value
    )
    opened_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), nullable=False)
    resolved_at: Mapped[DateTime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Relationships
    case: Mapped[RecoveryCase] = relationship("RecoveryCase", back_populates="disputes")


class Evidence(Base):
    """Stores business evidence used during the recovery process.

    All external business content (emails, documents, descriptions) is treated
    as untrusted data. Evidence is classified and structured by AI but
    authority over financial amounts belongs to deterministic application logic.
    """

    __tablename__ = "evidence"

    __table_args__ = (
        Index("ix_evidence_case_id", "case_id"),
        Index("ix_evidence_type", "type"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        nullable=False,
    )
    case_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("recovery_cases.id", ondelete="RESTRICT"),
        nullable=False,
    )
    type: Mapped[str] = mapped_column(String(64), nullable=False)
    source: Mapped[str] = mapped_column(String(128), nullable=False)
    external_reference: Mapped[str | None] = mapped_column(String(255), nullable=True)
    content: Mapped[str | None] = mapped_column(Text, nullable=True)
    structured_data: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )

    # Relationships
    case: Mapped[RecoveryCase] = relationship("RecoveryCase", back_populates="evidence")


class AgentRun(Base):
    """Stores metadata about AI reasoning executions.

    Records model invocation details for auditability. Must not expose
    private model chain-of-thought; only structured output and metadata.
    """

    __tablename__ = "agent_runs"

    __table_args__ = (Index("ix_agent_runs_case_id", "case_id"),)

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        nullable=False,
    )
    case_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("recovery_cases.id", ondelete="RESTRICT"),
        nullable=False,
    )
    agent_type: Mapped[str] = mapped_column(String(64), nullable=False)
    model_name: Mapped[str] = mapped_column(String(128), nullable=False)
    prompt_version: Mapped[str] = mapped_column(String(64), nullable=False)
    input_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    output_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    token_usage: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    success: Mapped[bool] = mapped_column(Boolean, nullable=False)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )

    # Relationships
    case: Mapped[RecoveryCase] = relationship(
        "RecoveryCase", back_populates="agent_runs"
    )
    resolution_proposals: Mapped[list[ResolutionProposal]] = relationship(
        "ResolutionProposal", back_populates="agent_run", passive_deletes=True
    )


class ResolutionProposal(Base):
    """Stores AI-generated recovery recommendations before execution.

    The proposed_amount is BIGINT paise. The proposal is only an AI
    recommendation; it does not authorize recovery. Policy Engine evaluation
    is required before any action can proceed.
    """

    __tablename__ = "resolution_proposals"

    __table_args__ = (
        CheckConstraint(
            "proposed_amount IS NULL OR proposed_amount >= 0",
            name="ck_proposals_proposed_amount_nonneg",
        ),
        CheckConstraint(
            "confidence >= 0 AND confidence <= 1", name="ck_proposals_confidence_range"
        ),
        Index("ix_resolution_proposals_case_id", "case_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        nullable=False,
    )
    case_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("recovery_cases.id", ondelete="RESTRICT"),
        nullable=False,
    )
    agent_run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("agent_runs.id", ondelete="RESTRICT"),
        nullable=False,
    )
    action_type: Mapped[str] = mapped_column(String(64), nullable=False)
    # BIGINT paise — AI proposed amount, not yet authorized
    proposed_amount: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    reason_code: Mapped[str] = mapped_column(String(128), nullable=False)
    confidence: Mapped[float] = mapped_column(Numeric(5, 4), nullable=False)
    evidence_ids: Mapped[dict] = mapped_column(JSONB, nullable=False)
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default=ResolutionProposalStatus.PENDING.value
    )
    created_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )

    # Relationships
    case: Mapped[RecoveryCase] = relationship(
        "RecoveryCase", back_populates="resolution_proposals"
    )
    agent_run: Mapped[AgentRun] = relationship(
        "AgentRun", back_populates="resolution_proposals"
    )
    policy_decisions: Mapped[list[PolicyDecision]] = relationship(
        "PolicyDecision", back_populates="proposal", passive_deletes=True
    )
    recovery_actions: Mapped[list[RecoveryAction]] = relationship(
        "RecoveryAction", back_populates="proposal", passive_deletes=True
    )


class PolicyDecision(Base):
    """Stores the deterministic Policy Engine result.

    Every executable recovery action must be preceded by a PolicyDecision.
    The policy_version field enables historical reconstruction without relying
    on the merchant's current (possibly updated) policy.
    """

    __tablename__ = "policy_decisions"

    __table_args__ = (Index("ix_policy_decisions_case_id", "case_id"),)

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        nullable=False,
    )
    case_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("recovery_cases.id", ondelete="RESTRICT"),
        nullable=False,
    )
    proposal_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("resolution_proposals.id", ondelete="RESTRICT"),
        nullable=False,
    )
    decision: Mapped[str] = mapped_column(String(40), nullable=False)
    policy_version: Mapped[str] = mapped_column(String(64), nullable=False)
    checks_json: Mapped[dict] = mapped_column(JSONB, nullable=False)
    blocking_reason: Mapped[str | None] = mapped_column(String(128), nullable=True)
    created_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )

    # Relationships
    case: Mapped[RecoveryCase] = relationship(
        "RecoveryCase", back_populates="policy_decisions"
    )
    proposal: Mapped[ResolutionProposal] = relationship(
        "ResolutionProposal", back_populates="policy_decisions"
    )
    recovery_actions: Mapped[list[RecoveryAction]] = relationship(
        "RecoveryAction", back_populates="policy_decision", passive_deletes=True
    )


class RecoveryAction(Base):
    """Stores recovery actions proposed for controlled execution.

    A RecoveryAction may only be created after applicable policy and state
    checks have been evaluated. If the PolicyDecision is
    HUMAN_APPROVAL_REQUIRED, the action must be created with status
    PENDING_APPROVAL. Execution must not proceed until all authorization
    conditions (including human approval where required) are satisfied.
    """

    __tablename__ = "recovery_actions"

    __table_args__ = (
        CheckConstraint(
            "amount IS NULL OR amount >= 0", name="ck_recovery_actions_amount_nonneg"
        ),
        Index("ix_recovery_actions_case_id", "case_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        nullable=False,
    )
    case_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("recovery_cases.id", ondelete="RESTRICT"),
        nullable=False,
    )
    proposal_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("resolution_proposals.id", ondelete="RESTRICT"),
        nullable=False,
    )
    policy_decision_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("policy_decisions.id", ondelete="RESTRICT"),
        nullable=False,
    )
    type: Mapped[str] = mapped_column(String(64), nullable=False)
    # BIGINT paise — action amount, must satisfy policy constraints
    amount: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    status: Mapped[str] = mapped_column(
        String(40), nullable=False, default=RecoveryActionStatus.PENDING_APPROVAL.value
    )
    external_provider: Mapped[str | None] = mapped_column(String(64), nullable=True)
    external_reference: Mapped[str | None] = mapped_column(String(255), nullable=True)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    executed_at: Mapped[DateTime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Relationships
    case: Mapped[RecoveryCase] = relationship(
        "RecoveryCase", back_populates="recovery_actions"
    )
    proposal: Mapped[ResolutionProposal] = relationship(
        "ResolutionProposal", back_populates="recovery_actions"
    )
    policy_decision: Mapped[PolicyDecision] = relationship(
        "PolicyDecision", back_populates="recovery_actions"
    )
    payments: Mapped[list[Payment]] = relationship(
        "Payment", back_populates="recovery_action", passive_deletes=True
    )
    human_approvals: Mapped[list[HumanApproval]] = relationship(
        "HumanApproval", back_populates="action", passive_deletes=True
    )


class Payment(Base):
    """Represents actual payment state associated with a recovery action.

    A payment request being created (status=CREATED) does NOT imply
    successful payment. Payment completion requires verified external
    provider evidence (webhook-confirmed status=CAPTURED).
    Amount is BIGINT paise.
    """

    __tablename__ = "payments"

    __table_args__ = (
        CheckConstraint("amount > 0", name="ck_payments_amount_positive"),
        Index("ix_payments_case_id", "case_id"),
        Index("ix_payments_invoice_id", "invoice_id"),
        Index("ix_payments_razorpay_payment_id", "razorpay_payment_id"),
        Index("ix_payments_razorpay_link_id", "razorpay_payment_link_id"),
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
    case_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("recovery_cases.id", ondelete="RESTRICT"),
        nullable=False,
    )
    recovery_action_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("recovery_actions.id", ondelete="RESTRICT"),
        nullable=False,
    )
    razorpay_payment_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    razorpay_payment_link_id: Mapped[str | None] = mapped_column(
        String(128), nullable=True
    )
    # BIGINT paise — provider-confirmed amount
    amount: Mapped[int] = mapped_column(BigInteger, nullable=False)
    currency: Mapped[str] = mapped_column(CHAR(3), nullable=False)
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default=PaymentStatus.CREATED.value
    )
    paid_at: Mapped[DateTime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    updated_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )

    # Relationships
    invoice: Mapped[Invoice] = relationship("Invoice", back_populates="payments")
    case: Mapped[RecoveryCase] = relationship("RecoveryCase", back_populates="payments")
    recovery_action: Mapped[RecoveryAction] = relationship(
        "RecoveryAction", back_populates="payments"
    )


class Outreach(Base):
    """Stores customer-contact attempts for touchpoint enforcement.

    Used to determine how many automated touchpoints occurred within a
    policy-defined window (e.g., last 14 days).
    """

    __tablename__ = "outreach"

    __table_args__ = (
        Index("ix_outreach_case_id_sent_at", "case_id", "sent_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        nullable=False,
    )
    case_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("recovery_cases.id", ondelete="RESTRICT"),
        nullable=False,
    )
    channel: Mapped[str] = mapped_column(String(32), nullable=False)
    direction: Mapped[str] = mapped_column(String(16), nullable=False)
    purpose: Mapped[str] = mapped_column(String(64), nullable=False)
    message_reference: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    sent_at: Mapped[DateTime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Relationships
    case: Mapped[RecoveryCase] = relationship("RecoveryCase", back_populates="outreach")


class HumanApproval(Base):
    """Stores explicit human authorization for restricted recovery actions.

    Approval is bound to the exact RecoveryAction via action_fingerprint.
    Any change to action type, amount, or execution parameters invalidates
    the prior authorization.

    PENDING → APPROVED authorizes exactly the action represented by
    action_fingerprint. Approval must not be replayable across cases
    or modified proposals.
    """

    __tablename__ = "human_approvals"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        nullable=False,
    )
    case_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("recovery_cases.id", ondelete="RESTRICT"),
        nullable=False,
    )
    action_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("recovery_actions.id", ondelete="RESTRICT"),
        nullable=False,
    )
    # BIGINT paise — amount at time of approval request
    requested_amount: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    decision: Mapped[str] = mapped_column(
        String(32), nullable=False, default=HumanApprovalDecision.PENDING.value
    )
    approved_by: Mapped[str | None] = mapped_column(String(128), nullable=True)
    # Cryptographic or structural fingerprint binding approval to exact action
    action_fingerprint: Mapped[str] = mapped_column(String(128), nullable=False)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    resolved_at: Mapped[DateTime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Relationships
    case: Mapped[RecoveryCase] = relationship(
        "RecoveryCase", back_populates="human_approvals"
    )
    action: Mapped[RecoveryAction] = relationship(
        "RecoveryAction", back_populates="human_approvals"
    )


class AuditEvent(Base):
    """Append-only operational history of each recovery case.

    Records every state transition, financial event, and human action.
    External event IDs (e.g., Razorpay webhook event IDs) support
    idempotent webhook processing — duplicate events must be ignored.
    """

    __tablename__ = "audit_events"

    __table_args__ = (
        Index("ix_audit_events_case_id_created_at", "case_id", "created_at"),
        Index("ix_audit_events_external_event_id", "external_event_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        nullable=False,
    )
    case_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("recovery_cases.id", ondelete="RESTRICT"),
        nullable=False,
    )
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    actor_type: Mapped[str] = mapped_column(String(64), nullable=False)
    actor_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    state_before: Mapped[str | None] = mapped_column(String(40), nullable=True)
    state_after: Mapped[str | None] = mapped_column(String(40), nullable=True)
    payload_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    policy_version: Mapped[str | None] = mapped_column(String(64), nullable=True)
    # External idempotency key (e.g., Razorpay webhook event ID)
    external_event_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )

    # Relationships
    case: Mapped[RecoveryCase] = relationship(
        "RecoveryCase", back_populates="audit_events"
    )
