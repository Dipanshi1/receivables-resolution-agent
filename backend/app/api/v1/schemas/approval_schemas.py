"""Schemas for human approval API endpoints."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class CreateApprovalRequest(BaseModel):
    """Request to create a human approval decision."""

    proposal_id: UUID
    recovery_action_id: UUID
    decision: str  # "APPROVED" | "REJECTED"
    reason: str | None = None
    approved_by: str | None = None  # Reviewer identity; falls back to merchant_id in MVP


class ApprovalResponse(BaseModel):
    """Response returned after recording an approval decision."""

    id: UUID
    case_id: UUID
    action_id: UUID
    decision: str
    requested_amount_minor: int | None
    action_fingerprint: str
    justification: str | None
    approved_by: str | None
    created_at: datetime
    resolved_at: datetime | None
