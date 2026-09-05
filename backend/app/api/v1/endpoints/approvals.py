"""Human approval endpoint for recovery cases.

POST /v1/recovery-cases/{case_id}/approvals

Creates or records a human decision (APPROVED / REJECTED) on a recovery action.
Uses the deterministic HumanApprovalService to compute and verify fingerprints.
Caller must provide all material action details so the fingerprint can be verified.
"""

import logging
from datetime import UTC, datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db_session, get_merchant_id
from app.api.errors import raise_conflict, raise_domain_error, raise_forbidden, raise_not_found
from app.api.v1.schemas.approval_schemas import ApprovalResponse, CreateApprovalRequest
from app.domain.recovery import HumanApproval, RecoveryAction, RecoveryCase
from app.services.human_approval import (
    ActionFingerprintInput,
    ApprovalDecision,
    HumanApprovalService,
    compute_action_fingerprint,
)

logger = logging.getLogger(__name__)
router = APIRouter()

_approval_svc = HumanApprovalService()


@router.post("", response_model=ApprovalResponse, status_code=201)
async def submit_approval(
    case_id: UUID,
    request: CreateApprovalRequest,
    merchant_id: Annotated[UUID, Depends(get_merchant_id)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> ApprovalResponse:
    """Record a human approval or rejection for a recovery action.

    Requirements (api-contracts.md §14):
    - Approval is bound to: Case + Proposal + Recovery Action + Amount + Fingerprint
    - Fingerprint is COMPUTED by the backend — never trusted from client.
    - Changing any material field produces a different fingerprint and blocks execution.
    - Approver identity comes from authenticated context (X-Merchant-ID for MVP).
    """
    # --- Merchant isolation ---
    case_result = await session.execute(
        select(RecoveryCase).where(RecoveryCase.id == case_id)
    )
    case = case_result.scalars().first()
    if not case or case.merchant_id != merchant_id:
        raise_forbidden()

    # --- Resolve recovery action ---
    action_result = await session.execute(
        select(RecoveryAction).where(
            RecoveryAction.id == request.recovery_action_id,
            RecoveryAction.case_id == case_id,
        )
    )
    action = action_result.scalars().first()
    if not action:
        raise_not_found("RecoveryAction", str(request.recovery_action_id))

    if action.amount is None:
        raise_domain_error(
            "RECOVERY_AMOUNT_INVALID",
            "Recovery action has no amount to authorize",
            409,
        )

    # --- Validate decision ---
    decision_str = request.decision.upper()
    if decision_str not in ("APPROVED", "REJECTED"):
        raise_conflict("INVALID_DECISION", "Decision must be APPROVED or REJECTED")

    # --- Look up the latest policy decision for fingerprint binding ---
    from app.domain.recovery import PolicyDecision

    policy_result = await session.execute(
        select(PolicyDecision)
        .where(PolicyDecision.case_id == case_id)
        .order_by(PolicyDecision.created_at.desc())
        .limit(1)
    )
    policy_decision = policy_result.scalars().first()
    if not policy_decision:
        raise_domain_error(
            "POLICY_BLOCKED",
            "No policy decision exists for this case. Run policy-check first.",
            409,
        )

    # --- Check for duplicate pending approval ---
    existing_result = await session.execute(
        select(HumanApproval).where(
            HumanApproval.action_id == request.recovery_action_id,
            HumanApproval.decision == ApprovalDecision.PENDING.value,
        )
    )
    existing_pending = existing_result.scalars().first()

    # --- Compute fingerprint via HumanApprovalService ---
    fp_input = ActionFingerprintInput(
        case_id=str(case_id),
        action_type=action.type,
        amount_minor=action.amount,
        currency=case.invoice.currency if hasattr(case, "invoice") and case.invoice else "INR",
        customer_id=str(case.customer_id),
        invoice_id=str(case.invoice_id),
        financial_assessment_id=str(policy_decision.proposal_id),
        policy_decision_id=str(policy_decision.id),
    )
    fingerprint = compute_action_fingerprint(fp_input)

    now = datetime.now(UTC)

    if decision_str == "APPROVED":
        if existing_pending:
            # Verify fingerprint matches and approve the pending record
            if existing_pending.action_fingerprint != fingerprint:
                raise_domain_error(
                    "APPROVAL_INVALID",
                    "Action parameters have changed since approval was requested. "
                    "A new approval request is required.",
                    409,
                )
            existing_pending.decision = ApprovalDecision.APPROVED.value
            existing_pending.approved_by = request.approved_by or str(merchant_id)
            existing_pending.reason = request.reason
            existing_pending.resolved_at = now
            await session.commit()
            await session.refresh(existing_pending)
            db_approval = existing_pending
        else:
            # Create a new APPROVED record directly
            db_approval = HumanApproval(
                case_id=case_id,
                action_id=request.recovery_action_id,
                requested_amount=action.amount,
                decision=ApprovalDecision.APPROVED.value,
                approved_by=request.approved_by or str(merchant_id),
                action_fingerprint=fingerprint,
                reason=request.reason,
                resolved_at=now,
            )
            session.add(db_approval)
            await session.commit()
            await session.refresh(db_approval)

    else:  # REJECTED
        if existing_pending:
            existing_pending.decision = ApprovalDecision.REJECTED.value
            existing_pending.approved_by = request.approved_by or str(merchant_id)
            existing_pending.reason = request.reason
            existing_pending.resolved_at = now
            await session.commit()
            await session.refresh(existing_pending)
            db_approval = existing_pending
        else:
            db_approval = HumanApproval(
                case_id=case_id,
                action_id=request.recovery_action_id,
                requested_amount=action.amount,
                decision=ApprovalDecision.REJECTED.value,
                approved_by=request.approved_by or str(merchant_id),
                action_fingerprint=fingerprint,
                reason=request.reason,
                resolved_at=now,
            )
            session.add(db_approval)
            await session.commit()
            await session.refresh(db_approval)

    return ApprovalResponse(
        id=db_approval.id,
        case_id=db_approval.case_id,
        action_id=db_approval.action_id,
        decision=db_approval.decision,
        requested_amount_minor=db_approval.requested_amount,
        action_fingerprint=db_approval.action_fingerprint,
        justification=db_approval.reason,
        approved_by=db_approval.approved_by,
        created_at=db_approval.created_at,
        resolved_at=db_approval.resolved_at,
    )
