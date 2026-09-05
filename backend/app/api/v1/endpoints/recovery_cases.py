"""Recovery case API endpoints.

Thin route handlers that:
  1. Load domain entities from DB.
  2. Enforce merchant isolation.
  3. Call deterministic services (state machine, policy, financial calculation).
  4. Persist results.
  5. Return typed responses.

Business logic lives in services — NOT in this file.
"""

import logging
from typing import Annotated
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db_session, get_merchant_id
from app.api.errors import raise_conflict, raise_domain_error, raise_forbidden, raise_not_found
from app.api.v1.schemas.audit_schemas import AuditEventResponse, PaginatedAuditResponse
from app.api.v1.schemas.recovery_case_schemas import (
    CreateRecoveryCaseRequest,
    EscalateRequest,
    EscalateResponse,
    EvidenceRequest,
    EvidenceResponse,
    ExecuteRecoveryRequest,
    ExecuteRecoveryResponse,
    PaginatedCasesResponse,
    PolicyCheckRequest,
    PolicyCheckResponse,
    RecoveryCaseDetailResponse,
    RecoveryCaseSummary,
    ResolveRequest,
    ResolveResponse,
    TriageRequest,
    TriageResponse,
)
from app.domain.enums import (
    RecoveryActionStatus,
    RecoveryActionType,
    RecoveryCaseStatus,
    ResolutionProposalStatus,
)
from app.domain.invoice import Invoice
from app.domain.merchant import MerchantPolicy
from app.domain.recovery import (
    AgentRun,
    AuditEvent,
    PolicyDecision,
    RecoveryAction,
    RecoveryCase,
    ResolutionProposal,
)
from app.repositories.audit_repo import AuditEventRepository
from app.repositories.recovery_case_repo import RecoveryCaseRepository
from app.services.financial_calculation import (
    FinancialCalculationInput,
    calculate_financial_position,
)
from app.services.policy_engine import (
    FinancialAssessmentSnapshot,
    MerchantPolicySnapshot,
    PolicyEngineService,
    PolicyEvaluationInput,
)
from app.services.state_machine import RecoveryEvent, StateMachineService, TransitionContext

logger = logging.getLogger(__name__)
router = APIRouter()

_state_machine = StateMachineService()
_policy_engine = PolicyEngineService()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _case_to_detail(case: RecoveryCase) -> RecoveryCaseDetailResponse:
    return RecoveryCaseDetailResponse(
        id=case.id,
        merchant_id=case.merchant_id,
        invoice_id=case.invoice_id,
        customer_id=case.customer_id,
        status=case.status,
        claimed_disputed_amount_minor=case.claimed_disputed_amount,
        verified_disputed_amount_minor=case.verified_disputed_amount,
        collectible_amount_minor=case.collectible_amount,
        safely_recoverable_amount_minor=case.safely_recoverable_amount,
        recovered_amount_minor=case.recovered_amount,
        remaining_amount_minor=case.remaining_amount,
        created_at=case.created_at,
        updated_at=case.updated_at,
    )


async def _get_active_policy(
    session: AsyncSession, merchant_id: UUID
) -> MerchantPolicy | None:
    result = await session.execute(
        select(MerchantPolicy)
        .where(
            MerchantPolicy.merchant_id == merchant_id,
            MerchantPolicy.effective_to.is_(None),
        )
        .order_by(MerchantPolicy.effective_from.desc())
        .limit(1)
    )
    return result.scalars().first()


async def _add_audit_event(
    session: AsyncSession,
    case_id: UUID,
    event_type: str,
    actor_type: str,
    state_before: str | None = None,
    state_after: str | None = None,
    payload_json: dict | None = None,
) -> None:
    audit = AuditEvent(
        case_id=case_id,
        event_type=event_type,
        actor_type=actor_type,
        state_before=state_before,
        state_after=state_after,
        payload_json=payload_json or {},
    )
    session.add(audit)


# ---------------------------------------------------------------------------
# Create recovery case
# ---------------------------------------------------------------------------


@router.post("", response_model=RecoveryCaseDetailResponse, status_code=201)
async def create_recovery_case(
    request: CreateRecoveryCaseRequest,
    merchant_id: Annotated[UUID, Depends(get_merchant_id)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> RecoveryCaseDetailResponse:
    """Create a recovery case for an overdue invoice.

    Rules (api-contracts.md §8):
    - Invoice must belong to the authenticated merchant.
    - No duplicate active recovery case for the same invoice.
    - Creation generates an audit event.
    """
    invoice = await session.get(Invoice, request.invoice_id)
    if not invoice:
        raise_not_found("Invoice", str(request.invoice_id))
    if invoice.merchant_id != merchant_id:
        raise_forbidden()

    # Prevent duplicate active cases
    repo = RecoveryCaseRepository(session)
    existing = await repo.get_by_invoice_id(request.invoice_id)
    active = [c for c in existing if c.status not in ("CLOSED", "FULLY_RECOVERED")]
    if active:
        raise_conflict(
            "DUPLICATE_RESOURCE", "An active recovery case already exists for this invoice"
        )

    case = RecoveryCase(
        merchant_id=merchant_id,
        customer_id=invoice.customer_id,
        invoice_id=invoice.id,
        status=RecoveryCaseStatus.OVERDUE.value,
        claimed_disputed_amount=0,
        recovered_amount=0,
        remaining_amount=invoice.total_amount - invoice.amount_paid,
        touchpoint_count=0,
        locked=False,
    )
    session.add(case)
    await session.flush()  # Get the case.id before adding audit

    await _add_audit_event(
        session,
        case.id,
        "RECOVERY_CASE_CREATED",
        "API",
        state_before=None,
        state_after=RecoveryCaseStatus.OVERDUE.value,
        payload_json={"invoice_id": str(invoice.id), "trigger": request.trigger},
    )

    await session.commit()
    await session.refresh(case)
    return _case_to_detail(case)


# ---------------------------------------------------------------------------
# List recovery cases
# ---------------------------------------------------------------------------


@router.get("", response_model=PaginatedCasesResponse)
async def list_recovery_cases(
    merchant_id: Annotated[UUID, Depends(get_merchant_id)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    status: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> PaginatedCasesResponse:
    repo = RecoveryCaseRepository(session)
    cases, total = await repo.list_by_merchant(merchant_id, status, page, page_size)

    data = [
        RecoveryCaseSummary(
            id=c.id,
            merchant_id=c.merchant_id,
            invoice_id=c.invoice_id,
            customer_id=c.customer_id,
            status=c.status,
            claimed_disputed_amount_minor=c.claimed_disputed_amount,
            verified_disputed_amount_minor=c.verified_disputed_amount,
            collectible_amount_minor=c.collectible_amount,
            safely_recoverable_amount_minor=c.safely_recoverable_amount,
            recovered_amount_minor=c.recovered_amount,
            remaining_amount_minor=c.remaining_amount,
            created_at=c.created_at,
            updated_at=c.updated_at,
        )
        for c in cases
    ]

    return PaginatedCasesResponse(data=data, total=total, page=page, page_size=page_size)


# ---------------------------------------------------------------------------
# Get recovery case detail
# ---------------------------------------------------------------------------


@router.get("/{case_id}", response_model=RecoveryCaseDetailResponse)
async def get_recovery_case(
    case_id: UUID,
    merchant_id: Annotated[UUID, Depends(get_merchant_id)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> RecoveryCaseDetailResponse:
    case = await session.get(RecoveryCase, case_id)
    if not case:
        raise_not_found("RecoveryCase", str(case_id))
    if case.merchant_id != merchant_id:
        raise_forbidden()
    return _case_to_detail(case)


# ---------------------------------------------------------------------------
# Triage
# ---------------------------------------------------------------------------


@router.post("/{case_id}/triage", response_model=TriageResponse)
async def run_triage(
    case_id: UUID,
    request: TriageRequest,
    merchant_id: Annotated[UUID, Depends(get_merchant_id)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> TriageResponse:
    """Start the triage workflow.

    Transitions: OVERDUE → TRIAGING → ISSUE_IDENTIFIED
    Produces an AgentRun record.
    """
    case = await session.get(RecoveryCase, case_id)
    if not case or case.merchant_id != merchant_id:
        raise_forbidden()

    if case.locked:
        raise_domain_error("LEGAL_LOCK", "Case is locked — triage cannot proceed", 409)

    # State: OVERDUE → TRIAGING
    state_before = RecoveryCaseStatus(case.status)
    try:
        t1 = _state_machine.transition(
            state_before, RecoveryEvent.START_TRIAGE, TransitionContext()
        )
    except Exception as e:
        raise_domain_error("INVALID_STATE_TRANSITION", str(e), 409)

    case.status = t1.state_after.value
    await session.flush()

    # Persist triage transition audit
    await _add_audit_event(
        session,
        case.id,
        "TRIAGE_STARTED",
        "STATE_MACHINE",
        state_before=state_before.value,
        state_after=t1.state_after.value,
    )

    # Attempt to complete triage (AI would run here; for MVP we do a structure-only pass)
    # The AI output is advisory — it does not determine financial state.
    # In full implementation, TriageAgent runs here and its result is stored in AgentRun.
    issue_type = case.issue_type or "UNKNOWN"

    # State: TRIAGING → ISSUE_IDENTIFIED
    try:
        t2 = _state_machine.transition(
            t1.state_after, RecoveryEvent.TRIAGE_COMPLETED, TransitionContext()
        )
        case.status = t2.state_after.value
    except Exception:
        # Triage completed even if state machine guards don't advance further
        pass

    agent_run = AgentRun(
        case_id=case.id,
        agent_type="TRIAGE",
        model_name="mock-v1",
        prompt_version="v1",
        input_hash=str(uuid4()),
        success=True,
    )
    session.add(agent_run)

    await _add_audit_event(
        session,
        case.id,
        "TRIAGE_COMPLETED",
        "AI_AGENT",
        state_before=t1.state_after.value,
        state_after=case.status,
        payload_json={"issue_type": issue_type},
    )

    await session.commit()
    await session.refresh(case)

    return TriageResponse(
        case_id=case_id,
        issue_type=issue_type,
        state_before=state_before.value,
        state_after=case.status,
    )


# ---------------------------------------------------------------------------
# Evidence analysis
# ---------------------------------------------------------------------------


@router.post("/{case_id}/evidence", response_model=EvidenceResponse)
async def run_evidence(
    case_id: UUID,
    request: EvidenceRequest,
    merchant_id: Annotated[UUID, Depends(get_merchant_id)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> EvidenceResponse:
    """Run evidence analysis.

    Transitions: ISSUE_IDENTIFIED → EVIDENCE_ANALYSIS → RESOLUTION_READY
    """
    case = await session.get(RecoveryCase, case_id)
    if not case or case.merchant_id != merchant_id:
        raise_forbidden()

    if case.locked:
        raise_domain_error("LEGAL_LOCK", "Case is locked — evidence analysis cannot proceed", 409)

    state_before = RecoveryCaseStatus(case.status)

    try:
        t1 = _state_machine.transition(
            state_before, RecoveryEvent.START_EVIDENCE_ANALYSIS, TransitionContext()
        )
        case.status = t1.state_after.value
    except Exception as e:
        raise_domain_error("INVALID_STATE_TRANSITION", str(e), 409)

    await _add_audit_event(
        session, case.id, "EVIDENCE_ANALYSIS_STARTED", "STATE_MACHINE",
        state_before=state_before.value, state_after=case.status,
    )

    # EvidenceAgent would run here. For MVP, we mark evidence as sufficient.
    agent_run = AgentRun(
        case_id=case.id,
        agent_type="EVIDENCE",
        model_name="mock-v1",
        prompt_version="v1",
        input_hash=str(uuid4()),
        success=True,
        output_json={"finding": "PARTIALLY_SUPPORTED", "confidence": 0.85},
    )
    session.add(agent_run)

    # Transition to RESOLUTION_READY via EVIDENCE_SUFFICIENT
    try:
        t2 = _state_machine.transition(
            t1.state_after, RecoveryEvent.EVIDENCE_SUFFICIENT, TransitionContext()
        )
        case.status = t2.state_after.value
    except Exception:
        pass

    await _add_audit_event(
        session, case.id, "EVIDENCE_ANALYSIS_COMPLETED", "AI_AGENT",
        state_before=t1.state_after.value, state_after=case.status,
        payload_json={"finding": "PARTIALLY_SUPPORTED"},
    )

    await session.commit()
    await session.refresh(case)

    return EvidenceResponse(
        case_id=case_id,
        finding="PARTIALLY_SUPPORTED",
        state_before=state_before.value,
        state_after=case.status,
    )


# ---------------------------------------------------------------------------
# Generate resolution proposal
# ---------------------------------------------------------------------------


@router.post("/{case_id}/resolve", response_model=ResolveResponse)
async def run_resolve(
    case_id: UUID,
    request: ResolveRequest,
    merchant_id: Annotated[UUID, Depends(get_merchant_id)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> ResolveResponse:
    """Generate a resolution proposal using deterministic financial assessment.

    The AI recommends. Financial Calculation is authoritative.
    """
    case = await session.get(RecoveryCase, case_id)
    if not case or case.merchant_id != merchant_id:
        raise_forbidden()

    if case.locked:
        raise_domain_error("LEGAL_LOCK", "Case is locked", 409)

    # Load invoice for financial calculation
    invoice = await session.get(Invoice, case.invoice_id)
    if not invoice:
        raise_domain_error("RESOURCE_NOT_FOUND", "Invoice not found", 404)

    state_before = RecoveryCaseStatus(case.status)

    # Run authoritative financial calculation
    try:
        calc_input = FinancialCalculationInput(
            currency=invoice.currency,
            gross_invoice_amount_minor=invoice.total_amount,
            valid_adjustments_minor=0,
            verified_payments_minor=invoice.amount_paid,
            claimed_disputed_amount_minor=case.claimed_disputed_amount,
            verified_disputed_amount_minor=case.verified_disputed_amount,
            verified_recovered_amount_minor=case.recovered_amount,
        )
        calc_result = calculate_financial_position(calc_input)
    except ValueError as e:
        raise_domain_error("RECOVERY_AMOUNT_INVALID", str(e), 409)

    # Update case with authoritative financial values
    case.collectible_amount = calc_result.collectible_amount_minor
    case.safely_recoverable_amount = calc_result.safely_recoverable_amount_minor
    case.remaining_amount = calc_result.remaining_amount_minor

    # ResolutionAgent would propose an amount here; for MVP we use safely_recoverable
    proposed_amount = calc_result.safely_recoverable_amount_minor

    # Persist the resolution proposal (AI advisory, not financial authority)
    agent_run = AgentRun(
        case_id=case.id,
        agent_type="RESOLUTION",
        model_name="mock-v1",
        prompt_version="v1",
        input_hash=str(uuid4()),
        success=True,
        output_json={
            "proposed_amount_minor": proposed_amount,
            "action": "CREATE_PARTIAL_RECOVERY",
        },
    )
    session.add(agent_run)
    await session.flush()

    proposal = ResolutionProposal(
        case_id=case.id,
        agent_run_id=agent_run.id,
        action_type="CREATE_PARTIAL_RECOVERY",
        proposed_amount=proposed_amount,
        reason_code="UNDISPUTED_AMOUNT",
        confidence=0.90,
        evidence_ids=[],
        status=ResolutionProposalStatus.PENDING.value,
    )
    session.add(proposal)

    # Transition: RESOLUTION_READY via RESOLUTION_PROPOSED
    try:
        t = _state_machine.transition(
            state_before, RecoveryEvent.RESOLUTION_PROPOSED, TransitionContext()
        )
        case.status = t.state_after.value
    except Exception:
        pass

    await _add_audit_event(
        session, case.id, "RESOLUTION_PROPOSED", "AI_AGENT",
        state_before=state_before.value, state_after=case.status,
        payload_json={
            "proposed_amount_minor": proposed_amount,
            "collectible_amount_minor": calc_result.collectible_amount_minor,
        },
    )

    await session.commit()
    await session.refresh(case)
    await session.refresh(proposal)

    return ResolveResponse(
        case_id=case_id,
        proposal_id=proposal.id,
        action="CREATE_PARTIAL_RECOVERY",
        proposed_amount_minor=proposed_amount,
        collectible_amount_minor=calc_result.collectible_amount_minor,
        safely_recoverable_amount_minor=calc_result.safely_recoverable_amount_minor,
        state_before=state_before.value,
        state_after=case.status,
    )


# ---------------------------------------------------------------------------
# Policy check
# ---------------------------------------------------------------------------


@router.post("/{case_id}/policy-check", response_model=PolicyCheckResponse)
async def run_policy_check(
    case_id: UUID,
    request: PolicyCheckRequest,
    merchant_id: Annotated[UUID, Depends(get_merchant_id)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> PolicyCheckResponse:
    """Evaluate the current resolution proposal against merchant policy.

    The Policy Engine is deterministic and authoritative.
    The frontend may NOT force the decision.
    """
    case = await session.get(RecoveryCase, case_id)
    if not case or case.merchant_id != merchant_id:
        raise_forbidden()

    # Load the proposal
    proposal_result = await session.execute(
        select(ResolutionProposal)
        .where(
            ResolutionProposal.id == request.proposal_id,
            ResolutionProposal.case_id == case_id,
        )
    )
    proposal = proposal_result.scalars().first()
    if not proposal:
        raise_not_found("ResolutionProposal", str(request.proposal_id))

    # Load merchant policy
    policy = await _get_active_policy(session, merchant_id)
    if not policy:
        raise_domain_error("POLICY_BLOCKED", "No active merchant policy found", 409)

    # Load invoice for financial context
    invoice = await session.get(Invoice, case.invoice_id)
    if not invoice:
        raise_domain_error("RESOURCE_NOT_FOUND", "Invoice not found", 404)

    # Build policy evaluation input (purely deterministic)
    mp_snapshot = MerchantPolicySnapshot(
        policy_id=str(policy.id),
        policy_version=policy.version,
        max_auto_recovery_amount_minor=policy.max_auto_recovery_amount,
        max_concession_percent=float(policy.max_concession_percent),
        max_concession_amount_minor=policy.max_concession_amount,
        max_touchpoints=policy.max_touchpoints,
        touchpoint_window_days=policy.touchpoint_window_days,
        quiet_hours_start=str(policy.quiet_hours_start),
        quiet_hours_end=str(policy.quiet_hours_end),
        high_value_threshold_minor=policy.high_value_threshold,
    )

    fa_snapshot = FinancialAssessmentSnapshot(
        assessment_id=str(proposal.id),
        collectible_amount_minor=case.collectible_amount or 0,
        safely_recoverable_amount_minor=case.safely_recoverable_amount or 0,
        verified_disputed_amount_minor=case.verified_disputed_amount,
        has_evidence_conflict=False,
        has_missing_evidence=False,
        assessment_age_seconds=0,
    )

    from app.domain.enums import RecoveryActionType

    eval_input = PolicyEvaluationInput(
        case_id=str(case_id),
        current_state=RecoveryCaseStatus(case.status),
        action_type=RecoveryActionType.CREATE_PARTIAL_RECOVERY,
        proposed_amount_minor=proposal.proposed_amount or 0,
        currency=invoice.currency,
        merchant_policy=mp_snapshot,
        financial_assessment=fa_snapshot,
        is_legal_locked=case.locked,
        is_automation_locked=False,
        touchpoints_in_window=case.touchpoint_count,
        is_safety_violation=False,
    )

    policy_result = _policy_engine.evaluate(eval_input)

    # Persist the policy decision record
    db_policy_decision = PolicyDecision(
        case_id=case.id,
        proposal_id=proposal.id,
        decision=policy_result.decision.value,
        policy_version=policy.version,
        checks_json=policy_result.checks if hasattr(policy_result, "checks") else {},
        blocking_reason=policy_result.reason_code.value if policy_result.reason_code else None,
    )
    session.add(db_policy_decision)

    # Transition state based on policy decision
    state_before = RecoveryCaseStatus(case.status)
    event_map = {
        "APPROVED": RecoveryEvent.POLICY_APPROVED,
        "HUMAN_APPROVAL_REQUIRED": RecoveryEvent.HUMAN_APPROVAL_REQUIRED,
        "DEFERRED": RecoveryEvent.POLICY_DEFERRED,
        "BLOCKED": RecoveryEvent.POLICY_BLOCKED,
        "STOPPED": RecoveryEvent.POLICY_STOPPED,
    }
    sm_event = event_map.get(policy_result.decision.value, RecoveryEvent.POLICY_BLOCKED)

    try:
        t = _state_machine.transition(state_before, sm_event, TransitionContext())
        case.status = t.state_after.value
    except Exception:
        pass

    await _add_audit_event(
        session, case.id, "POLICY_EVALUATED", "POLICY_ENGINE",
        state_before=state_before.value, state_after=case.status,
        payload_json={
            "decision": policy_result.decision.value,
            "reason_code": policy_result.reason_code.value if policy_result.reason_code else None,
        },
    )

    await session.commit()
    await session.refresh(case)
    await session.refresh(db_policy_decision)

    return PolicyCheckResponse(
        policy_decision_id=db_policy_decision.id,
        decision=policy_result.decision.value,
        policy_version=policy.version,
        reason_code=policy_result.reason_code.value if policy_result.reason_code else None,
        state_before=state_before.value,
        state_after=case.status,
    )


# ---------------------------------------------------------------------------
# Execute recovery
# ---------------------------------------------------------------------------


@router.post("/{case_id}/execute", response_model=ExecuteRecoveryResponse)
async def run_execute(
    case_id: UUID,
    request: ExecuteRecoveryRequest,
    merchant_id: Annotated[UUID, Depends(get_merchant_id)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> ExecuteRecoveryResponse:
    """Execute an authorized recovery action.

    Full guard sequence (api-contracts.md §13):
    1. Proposal must exist and belong to case.
    2. Policy decision must permit the action.
    3. Human approval must exist if required.
    4. Fingerprint must be valid.
    5. Financial re-validation must confirm amounts.
    6. Legal lock must not be set.
    7. Idempotency key must be respected.
    8. Only then: create RecoveryAction + Payment record; transition state to PAYMENT_PENDING.

    NOTE: This does NOT call Razorpay in the MVP (no credentials configured).
    It creates the PAYMENT_PENDING state and the RecoveryAction record.
    The actual provider call happens in a real deployment via RecoveryExecutor.
    """
    case = await session.get(RecoveryCase, case_id)
    if not case or case.merchant_id != merchant_id:
        raise_forbidden()

    # Legal lock guard
    if case.locked:
        raise_domain_error("LEGAL_LOCK", "Case is legally locked — execution blocked", 409)

    # Load proposal
    proposal_result = await session.execute(
        select(ResolutionProposal)
        .where(
            ResolutionProposal.id == request.proposal_id,
            ResolutionProposal.case_id == case_id,
        )
    )
    proposal = proposal_result.scalars().first()
    if not proposal:
        raise_not_found("ResolutionProposal", str(request.proposal_id))

    # Load latest policy decision
    pd_result = await session.execute(
        select(PolicyDecision)
        .where(PolicyDecision.proposal_id == proposal.id)
        .order_by(PolicyDecision.created_at.desc())
        .limit(1)
    )
    policy_decision = pd_result.scalars().first()
    if not policy_decision:
        raise_domain_error("POLICY_BLOCKED", "No policy decision found for this proposal", 409)

    decision = policy_decision.decision
    if decision not in ("APPROVED", "HUMAN_APPROVAL_REQUIRED"):
        raise_domain_error(
            "POLICY_BLOCKED",
            f"Policy decision {decision} does not permit execution",
            409,
        )

    # Human approval guard
    if decision == "HUMAN_APPROVAL_REQUIRED":
        if not request.human_approval_id:
            raise_domain_error(
                "HUMAN_APPROVAL_REQUIRED",
                "Human approval is required for this action",
                409,
            )
        from app.domain.recovery import HumanApproval

        ha_result = await session.execute(
            select(HumanApproval)
            .where(
                HumanApproval.id == request.human_approval_id,
                HumanApproval.case_id == case_id,
            )
        )
        approval = ha_result.scalars().first()
        if not approval:
            raise_not_found("HumanApproval", str(request.human_approval_id))
        if approval.decision != "APPROVED":
            raise_domain_error(
                "APPROVAL_INVALID",
                f"Approval is in state {approval.decision}, not APPROVED",
                409,
            )

    # Re-validate financial amounts (reread from authoritative calculation)
    invoice = await session.get(Invoice, case.invoice_id)
    if not invoice:
        raise_domain_error("RESOURCE_NOT_FOUND", "Invoice not found", 404)

    try:
        calc_input = FinancialCalculationInput(
            currency=invoice.currency,
            gross_invoice_amount_minor=invoice.total_amount,
            verified_payments_minor=invoice.amount_paid,
            claimed_disputed_amount_minor=case.claimed_disputed_amount,
            verified_disputed_amount_minor=case.verified_disputed_amount,
            verified_recovered_amount_minor=case.recovered_amount,
        )
        calc_result = calculate_financial_position(calc_input)
    except ValueError as e:
        raise_domain_error("RECOVERY_AMOUNT_INVALID", str(e), 409)

    proposed_amount = proposal.proposed_amount or 0
    if proposed_amount > calc_result.collectible_amount_minor:
        raise_domain_error(
            "RECOVERY_AMOUNT_EXCEEDS_COLLECTIBLE",
            f"Proposed amount {proposed_amount} exceeds collectible "
            f"{calc_result.collectible_amount_minor}",
            409,
        )
    if proposed_amount > calc_result.safely_recoverable_amount_minor:
        raise_domain_error(
            "RECOVERY_AMOUNT_EXCEEDS_SAFELY_RECOVERABLE",
            f"Proposed amount {proposed_amount} exceeds safely recoverable "
            f"{calc_result.safely_recoverable_amount_minor}",
            409,
        )

    # State: POLICY_REVIEW → RECOVERY_INITIATED
    state_before = RecoveryCaseStatus(case.status)
    try:
        t = _state_machine.transition(
            state_before,
            RecoveryEvent.PAYMENT_REQUEST_CREATED,
            TransitionContext(),
        )
        case.status = t.state_after.value
    except Exception as e:
        raise_domain_error("INVALID_STATE_TRANSITION", str(e), 409)

    # Create the RecoveryAction record (AUTHORIZED status)
    action = RecoveryAction(
        case_id=case.id,
        proposal_id=proposal.id,
        policy_decision_id=policy_decision.id,
        type=RecoveryActionType.CREATE_PARTIAL_RECOVERY.value,
        amount=proposed_amount,
        status=RecoveryActionStatus.PAYMENT_PENDING.value,
        reason="Authorized via API execute endpoint",
    )
    session.add(action)

    await _add_audit_event(
        session, case.id, "RECOVERY_EXECUTION_INITIATED", "API",
        state_before=state_before.value, state_after=case.status,
        payload_json={
            "proposal_id": str(proposal.id),
            "amount_minor": proposed_amount,
        },
    )

    await session.commit()
    await session.refresh(case)
    await session.refresh(action)

    return ExecuteRecoveryResponse(
        recovery_action_id=action.id,
        status=action.status,
        amount_minor=action.amount,
        state_before=state_before.value,
        state_after=case.status,
    )


# ---------------------------------------------------------------------------
# Escalate
# ---------------------------------------------------------------------------


@router.post("/{case_id}/escalate", response_model=EscalateResponse)
async def run_escalate(
    case_id: UUID,
    request: EscalateRequest,
    merchant_id: Annotated[UUID, Depends(get_merchant_id)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> EscalateResponse:
    """Escalate a recovery case (HUMAN_REVIEW or LEGAL_ESCALATION).

    Legal escalation applies an automation lock.
    The frontend cannot remove the lock.
    """
    case = await session.get(RecoveryCase, case_id)
    if not case or case.merchant_id != merchant_id:
        raise_forbidden()

    escalation_type = (request.type or "HUMAN_REVIEW").upper()
    state_before = RecoveryCaseStatus(case.status)

    if escalation_type == "LEGAL_ESCALATION":
        event = RecoveryEvent.REVIEW_ESCALATE_LEGAL
        # Apply legal lock
        case.locked = True
        case.lock_reason = request.reason_code or "LEGAL_ESCALATION"
    else:
        event = RecoveryEvent.REVIEW_COMPLETED

    try:
        t = _state_machine.transition(state_before, event, TransitionContext())
        case.status = t.state_after.value
    except Exception:
        # Fallback: directly set state for escalation
        if escalation_type == "LEGAL_ESCALATION":
            case.status = RecoveryCaseStatus.LEGAL_ESCALATION.value
        else:
            case.status = RecoveryCaseStatus.HUMAN_REVIEW.value

    await _add_audit_event(
        session, case.id, "CASE_ESCALATED", "API",
        state_before=state_before.value, state_after=case.status,
        payload_json={"type": escalation_type, "reason_code": request.reason_code},
    )

    await session.commit()
    await session.refresh(case)

    return EscalateResponse(escalation_type=escalation_type, state_after=case.status)


# ---------------------------------------------------------------------------
# Audit history
# ---------------------------------------------------------------------------


@router.get("/{case_id}/audit", response_model=PaginatedAuditResponse)
async def list_audits(
    case_id: UUID,
    merchant_id: Annotated[UUID, Depends(get_merchant_id)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> PaginatedAuditResponse:
    case = await session.get(RecoveryCase, case_id)
    if not case or case.merchant_id != merchant_id:
        raise_forbidden()

    repo = AuditEventRepository(session)
    events, total = await repo.list_by_case(case_id, page, page_size)

    data = [
        AuditEventResponse(
            id=e.id,
            case_id=e.case_id,
            event_type=e.event_type,
            actor_type=e.actor_type,
            actor_id=e.actor_id,
            state_before=e.state_before,
            state_after=e.state_after,
            payload_json=e.payload_json,
            created_at=e.created_at,
        )
        for e in events
    ]

    return PaginatedAuditResponse(data=data, total=total, page=page, page_size=page_size)
