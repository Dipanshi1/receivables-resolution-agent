"""Domain enumerations used across the receivables resolution models.

All enums inherit from StrEnum to provide string value compatibility
and clean mapping to VARCHAR columns in PostgreSQL.
"""

from enum import StrEnum


class InvoiceStatus(StrEnum):
    """Status of a customer invoice."""

    OUTSTANDING = "OUTSTANDING"
    PARTIALLY_PAID = "PARTIALLY_PAID"
    PAID = "PAID"
    DISPUTED = "DISPUTED"
    WRITTEN_OFF = "WRITTEN_OFF"
    CANCELLED = "CANCELLED"


class RecoveryCaseStatus(StrEnum):
    """State machine states for a recovery case (docs/02-engineering/state-machine.md)."""

    OVERDUE = "OVERDUE"
    TRIAGING = "TRIAGING"
    ISSUE_IDENTIFIED = "ISSUE_IDENTIFIED"
    EVIDENCE_ANALYSIS = "EVIDENCE_ANALYSIS"
    RESOLUTION_READY = "RESOLUTION_READY"
    POLICY_REVIEW = "POLICY_REVIEW"
    RECOVERY_INITIATED = "RECOVERY_INITIATED"
    PAYMENT_PENDING = "PAYMENT_PENDING"
    PARTIALLY_RECOVERED = "PARTIALLY_RECOVERED"
    FULLY_RECOVERED = "FULLY_RECOVERED"
    HUMAN_REVIEW = "HUMAN_REVIEW"
    LEGAL_ESCALATION = "LEGAL_ESCALATION"
    AUTOMATION_LOCKED = "AUTOMATION_LOCKED"
    EXECUTION_FAILED = "EXECUTION_FAILED"
    CLOSED = "CLOSED"


class IssueType(StrEnum):
    """Primary issue classification for a recovery case."""

    PAYMENT_FAILURE = "PAYMENT_FAILURE"
    QUANTITY_DISPUTE = "QUANTITY_DISPUTE"
    PRICE_DISPUTE = "PRICE_DISPUTE"
    PO_MISMATCH = "PO_MISMATCH"
    GST_DOCUMENTATION = "GST_DOCUMENTATION"
    MILESTONE_PENDING = "MILESTONE_PENDING"
    SERVICE_DELIVERY_DISPUTE = "SERVICE_DELIVERY_DISPUTE"
    CREDIT_NOTE_REQUEST = "CREDIT_NOTE_REQUEST"
    PROMISE_TO_PAY = "PROMISE_TO_PAY"
    LEGAL_RISK = "LEGAL_RISK"
    UNKNOWN = "UNKNOWN"


class DisputeType(StrEnum):
    """Category of a commercial dispute."""

    PRICE_DISCREPANCY = "PRICE_DISCREPANCY"
    QUALITY_ISSUE = "QUALITY_ISSUE"
    DELIVERY_ISSUE = "DELIVERY_ISSUE"
    SERVICE_FAILURE = "SERVICE_FAILURE"
    DUPLICATE_CHARGE = "DUPLICATE_CHARGE"
    INCORRECT_QUANTITY = "INCORRECT_QUANTITY"
    TAX_DISCREPANCY = "TAX_DISCREPANCY"
    CREDIT_NOTE_PENDING = "CREDIT_NOTE_PENDING"
    CONTRACT_DISPUTE = "CONTRACT_DISPUTE"
    OTHER = "OTHER"


class DisputeStatus(StrEnum):
    """Status of a dispute record."""

    OPEN = "OPEN"
    UNDER_REVIEW = "UNDER_REVIEW"
    RESOLVED = "RESOLVED"
    ESCALATED = "ESCALATED"


class EvidenceType(StrEnum):
    """Type of evidence artifact."""

    INVOICE = "INVOICE"
    PURCHASE_ORDER = "PURCHASE_ORDER"
    GRN = "GRN"
    DELIVERY_RECORD = "DELIVERY_RECORD"
    CONTRACT = "CONTRACT"
    MILESTONE_RECORD = "MILESTONE_RECORD"
    CUSTOMER_EMAIL = "CUSTOMER_EMAIL"
    PAYMENT_RECORD = "PAYMENT_RECORD"
    CREDIT_NOTE = "CREDIT_NOTE"
    OTHER = "OTHER"


class AgentType(StrEnum):
    """Type of AI agent run."""

    TRIAGE = "TRIAGE"
    EVIDENCE = "EVIDENCE"
    RESOLUTION = "RESOLUTION"


class ResolutionProposalStatus(StrEnum):
    """Lifecycle status of an AI resolution proposal."""

    PENDING = "PENDING"
    POLICY_APPROVED = "POLICY_APPROVED"
    POLICY_REJECTED = "POLICY_REJECTED"
    HUMAN_APPROVAL_REQUIRED = "HUMAN_APPROVAL_REQUIRED"
    ACCEPTED = "ACCEPTED"
    REJECTED = "REJECTED"
    SUPERSEDED = "SUPERSEDED"


class ResolutionProposalAction(StrEnum):
    """Action recommendation produced by AI resolution agent."""

    CREATE_FULL_RECOVERY = "CREATE_FULL_RECOVERY"
    CREATE_PARTIAL_RECOVERY = "CREATE_PARTIAL_RECOVERY"
    REQUEST_DOCUMENT = "REQUEST_DOCUMENT"
    REQUEST_CORRECTION = "REQUEST_CORRECTION"
    WAIT_FOR_PROMISE = "WAIT_FOR_PROMISE"
    STOP_OUTREACH = "STOP_OUTREACH"
    ESCALATE_HUMAN = "ESCALATE_HUMAN"
    ESCALATE_LEGAL = "ESCALATE_LEGAL"


class PolicyDecisionResult(StrEnum):
    """Outcome of a deterministic Policy Engine evaluation."""

    APPROVED = "APPROVED"
    DEFERRED = "DEFERRED"
    HUMAN_APPROVAL_REQUIRED = "HUMAN_APPROVAL_REQUIRED"
    BLOCKED = "BLOCKED"
    STOPPED = "STOPPED"


class RecoveryActionType(StrEnum):
    """Type of recovery action to be executed."""

    CREATE_PAYMENT_LINK = "CREATE_PAYMENT_LINK"
    CREATE_PARTIAL_RECOVERY = "CREATE_PARTIAL_RECOVERY"
    APPLY_CONCESSION = "APPLY_CONCESSION"
    SEND_REMINDER = "SEND_REMINDER"
    ESCALATE_TO_HUMAN = "ESCALATE_TO_HUMAN"
    WRITE_OFF = "WRITE_OFF"


class RecoveryActionStatus(StrEnum):
    """Lifecycle status of a recovery action."""

    PENDING_APPROVAL = "PENDING_APPROVAL"
    AUTHORIZED = "AUTHORIZED"
    EXECUTING = "EXECUTING"
    PAYMENT_PENDING = "PAYMENT_PENDING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class PaymentStatus(StrEnum):
    """Status of a payment record."""

    CREATED = "CREATED"
    PENDING = "PENDING"
    CAPTURED = "CAPTURED"
    FAILED = "FAILED"
    REFUNDED = "REFUNDED"
    EXPIRED = "EXPIRED"


class OutreachChannel(StrEnum):
    """Communication channel for outreach."""

    EMAIL = "EMAIL"
    WHATSAPP = "WHATSAPP"
    SMS = "SMS"
    VOICE = "VOICE"


class OutreachDirection(StrEnum):
    """Direction of outreach communication."""

    INBOUND = "INBOUND"
    OUTBOUND = "OUTBOUND"


class OutreachStatus(StrEnum):
    """Delivery / processing status of an outreach record."""

    SENT = "SENT"
    DELIVERED = "DELIVERED"
    FAILED = "FAILED"
    RECEIVED = "RECEIVED"


class HumanApprovalDecision(StrEnum):
    """Decision on a human approval request."""

    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"
    INVALIDATED = "INVALIDATED"


class RiskLevel(StrEnum):
    """Risk classification of a recovery case."""

    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"
