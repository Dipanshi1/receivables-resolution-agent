"""Typed request/response schemas for recovery case endpoints."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel

# ---------------------------------------------------------------------------
# Create recovery case
# ---------------------------------------------------------------------------


class CreateRecoveryCaseRequest(BaseModel):
    invoice_id: UUID
    trigger: str = "INVOICE_OVERDUE"


class RecoveryCaseSummary(BaseModel):
    id: UUID
    merchant_id: UUID
    invoice_id: UUID
    customer_id: UUID
    status: str
    claimed_disputed_amount_minor: int
    verified_disputed_amount_minor: int | None
    collectible_amount_minor: int | None
    safely_recoverable_amount_minor: int | None
    recovered_amount_minor: int
    remaining_amount_minor: int
    created_at: datetime
    updated_at: datetime


class RecoveryCaseDetailResponse(RecoveryCaseSummary):
    pass


class PaginatedCasesResponse(BaseModel):
    data: list[RecoveryCaseSummary]
    total: int
    page: int
    page_size: int


# ---------------------------------------------------------------------------
# Triage
# ---------------------------------------------------------------------------


class TriageRequest(BaseModel):
    force: bool = False


class TriageResponse(BaseModel):
    case_id: UUID
    issue_type: str
    state_before: str
    state_after: str


# ---------------------------------------------------------------------------
# Evidence
# ---------------------------------------------------------------------------


class EvidenceRequest(BaseModel):
    scope: str = "AUTO"


class EvidenceResponse(BaseModel):
    case_id: UUID
    finding: str
    state_before: str
    state_after: str


# ---------------------------------------------------------------------------
# Resolve
# ---------------------------------------------------------------------------


class ResolveRequest(BaseModel):
    force: bool = False


class ResolveResponse(BaseModel):
    case_id: UUID
    proposal_id: UUID
    action: str
    proposed_amount_minor: int
    collectible_amount_minor: int
    safely_recoverable_amount_minor: int
    state_before: str
    state_after: str


# ---------------------------------------------------------------------------
# Policy check
# ---------------------------------------------------------------------------


class PolicyCheckRequest(BaseModel):
    proposal_id: UUID


class PolicyCheckResponse(BaseModel):
    policy_decision_id: UUID
    recovery_action_id: UUID | None = None
    decision: str
    policy_version: str
    reason_code: str | None
    state_before: str
    state_after: str


# ---------------------------------------------------------------------------
# Execute recovery
# ---------------------------------------------------------------------------


class ExecuteRecoveryRequest(BaseModel):
    proposal_id: UUID
    human_approval_id: UUID | None = None
    idempotency_key: str | None = None


class ExecuteRecoveryResponse(BaseModel):
    recovery_action_id: UUID
    status: str
    amount_minor: int | None
    state_before: str
    state_after: str


# ---------------------------------------------------------------------------
# Escalate
# ---------------------------------------------------------------------------


class EscalateRequest(BaseModel):
    type: str = "HUMAN_REVIEW"
    reason_code: str | None = None
    notes: str | None = None


class EscalateResponse(BaseModel):
    escalation_type: str
    state_after: str
