"""Domain enumerations used across the receivables resolution models.

All enums use string values that map cleanly to VARCHAR columns in PostgreSQL.
"""

from enum import Enum


class InvoiceStatus(str, Enum):
    """Status of a customer invoice."""

    OUTSTANDING = "outstanding"
    PARTIALLY_PAID = "partially_paid"
    PAID = "paid"
    DISPUTED = "disputed"
    WRITTEN_OFF = "written_off"
    CANCELLED = "cancelled"


class RecoveryCaseStatus(str, Enum):
    """State machine states for a recovery case."""

    OPENED = "opened"
    DIAGNOSING = "diagnosing"
    EVIDENCE_REVIEW = "evidence_review"
    FINANCIAL_ASSESSMENT = "financial_assessment"
    PROPOSAL_GENERATED = "proposal_generated"
    POLICY_EVALUATED = "policy_evaluated"
    PENDING_APPROVAL = "pending_approval"
    EXECUTING = "executing"
    PARTIALLY_RECOVERED = "partially_recovered"
    RECOVERED = "recovered"
    ESCALATED = "escalated"
    CLOSED = "closed"
    AUTOMATION_LOCKED = "automation_locked"


class DisputeType(str, Enum):
    """Category of a commercial dispute."""

    PRICE_DISCREPANCY = "price_discrepancy"
    QUALITY_ISSUE = "quality_issue"
    DELIVERY_ISSUE = "delivery_issue"
    SERVICE_FAILURE = "service_failure"
    DUPLICATE_CHARGE = "duplicate_charge"
    INCORRECT_QUANTITY = "incorrect_quantity"
    TAX_DISCREPANCY = "tax_discrepancy"
    CREDIT_NOTE_PENDING = "credit_note_pending"
    CONTRACT_DISPUTE = "contract_dispute"
    OTHER = "other"


class DisputeStatus(str, Enum):
    """Status of a dispute record."""

    OPEN = "open"
    UNDER_REVIEW = "under_review"
    RESOLVED = "resolved"
    ESCALATED = "escalated"


class EvidenceType(str, Enum):
    """Type of evidence artifact."""

    INVOICE = "invoice"
    PURCHASE_ORDER = "purchase_order"
    DELIVERY_RECEIPT = "delivery_receipt"
    EMAIL_COMMUNICATION = "email_communication"
    CONTRACT = "contract"
    CREDIT_NOTE = "credit_note"
    PAYMENT_RECEIPT = "payment_receipt"
    BANK_STATEMENT = "bank_statement"
    DISPUTE_CLAIM = "dispute_claim"
    CUSTOMER_STATEMENT = "customer_statement"
    OTHER = "other"


class AgentType(str, Enum):
    """Type of AI agent run."""

    TRIAGE = "triage"
    EVIDENCE = "evidence"
    RESOLUTION = "resolution"


class ResolutionProposalStatus(str, Enum):
    """Lifecycle status of an AI resolution proposal."""

    PENDING = "pending"
    POLICY_APPROVED = "policy_approved"
    POLICY_REJECTED = "policy_rejected"
    HUMAN_APPROVAL_REQUIRED = "human_approval_required"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    SUPERSEDED = "superseded"


class PolicyDecisionResult(str, Enum):
    """Outcome of a deterministic Policy Engine evaluation."""

    APPROVED = "approved"
    REJECTED = "rejected"
    HUMAN_APPROVAL_REQUIRED = "human_approval_required"


class RecoveryActionType(str, Enum):
    """Type of recovery action to be executed."""

    CREATE_PAYMENT_LINK = "create_payment_link"
    CREATE_PARTIAL_RECOVERY = "create_partial_recovery"
    APPLY_CONCESSION = "apply_concession"
    SEND_REMINDER = "send_reminder"
    ESCALATE_TO_HUMAN = "escalate_to_human"
    WRITE_OFF = "write_off"


class RecoveryActionStatus(str, Enum):
    """Lifecycle status of a recovery action."""

    PENDING_APPROVAL = "pending_approval"
    AUTHORIZED = "authorized"
    EXECUTING = "executing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class PaymentStatus(str, Enum):
    """Status of a payment record."""

    CREATED = "created"
    PENDING = "pending"
    CAPTURED = "captured"
    FAILED = "failed"
    REFUNDED = "refunded"
    EXPIRED = "expired"


class OutreachChannel(str, Enum):
    """Communication channel for outreach."""

    EMAIL = "email"
    SMS = "sms"
    WHATSAPP = "whatsapp"
    PHONE = "phone"
    PORTAL = "portal"


class OutreachDirection(str, Enum):
    """Direction of outreach communication."""

    INBOUND = "inbound"
    OUTBOUND = "outbound"


class OutreachStatus(str, Enum):
    """Delivery / processing status of an outreach record."""

    SENT = "sent"
    DELIVERED = "delivered"
    FAILED = "failed"
    RECEIVED = "received"


class HumanApprovalDecision(str, Enum):
    """Decision on a human approval request."""

    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXPIRED = "expired"
    INVALIDATED = "invalidated"


class RiskLevel(str, Enum):
    """Risk classification of a recovery case."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"
