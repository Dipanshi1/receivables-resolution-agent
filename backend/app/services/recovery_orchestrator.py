"""Recovery Orchestrator — Phase 5A.

Coordinates the full AI-to-deterministic pipeline for a recovery case:

    Triage (AI, advisory)
        ↓
    Evidence Analysis (AI, advisory)
        ↓
    Financial Calculation (deterministic, authoritative)
        ↓
    Resolution (AI, advisory)
        ↓
    Policy Evaluation (deterministic, authoritative)
        ↓
    State Machine Transition (deterministic, authoritative)
        ↓
    Human Approval Check / Gate (deterministic, authoritative)
        ↓
    OrchestratorResult  ← structured result with auditability metadata

Key invariants preserved:

  - AI agents are advisory only: they never authorize, compute, or transition.
  - Financial Calculation is the sole source of authoritative amounts.
  - Policy Engine is the sole gate over execution authority.
  - State Machine controls all state transitions.
  - Human Approval Service controls approval validity.
  - The orchestrator does NOT execute payments, does NOT call Razorpay.
  - The orchestrator does NOT persist AuditEvents (Phase 8 responsibility).
  - All failure paths fail closed — never guess, never silently recover.
  - Idempotency: the same case_id + fingerprint combination is rejected
    on duplicate orchestration calls within the same run.

Reference: docs/02-engineering/state-machine.md
           docs/02-engineering/policy-engine.md
           docs/02-engineering/ai-contracts.md
           docs/02-engineering/financial-calculation.md
"""

from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from app.ai.evidence_agent import EvidenceAgent
from app.ai.evidence_contracts import (
    EvidenceAgentResult,
    EvidenceFindingStatus,
    EvidenceInput,
    EvidenceOutcomeStatus,
    EvidenceOutput,
)
from app.ai.resolution_agent import ResolutionAgent
from app.ai.resolution_contracts import (
    ResolutionAgentResult,
    ResolutionInput,
    ResolutionOutcomeStatus,
    ResolutionOutput,
)
from app.ai.triage_agent import TriageAgent
from app.ai.triage_contracts import (
    TriageAgentResult,
    TriageInput,
    TriageOutcomeStatus,
    TriageOutput,
    TriageRiskFlag,
)
from app.domain.enums import (
    PolicyDecisionResult,
    RecoveryActionType,
    RecoveryCaseStatus,
    ResolutionProposalAction,
)
from app.services.financial_calculation import (
    FinancialAssessmentStatus,
    FinancialCalculationInput,
    FinancialCalculationResult,
    calculate_financial_position,
)
from app.services.human_approval import (
    ApprovalRecord,
    HumanApprovalService,
)
from app.services.policy_engine import (
    FinancialAssessmentSnapshot,
    MerchantPolicySnapshot,
    PolicyDecision,
    PolicyEngineService,
    PolicyEvaluationInput,
)
from app.services.state_machine import (
    InvalidTransitionError,
    RecoveryEvent,
    StateMachineService,
    TransitionContext,
    TransitionGuardError,
    TransitionResult,
)

# ---------------------------------------------------------------------------
# Orchestration outcome classification
# ---------------------------------------------------------------------------


class OrchestratorStatus(StrEnum):
    """Top-level outcome of one orchestration run.

    The orchestrator produces ONE of these outcomes per run.  Recovery
    execution is NEVER initiated inside the orchestrator — that is the
    executor's responsibility (Phase 7/8).
    """

    # Happy paths
    APPROVED = "APPROVED"
    """Policy approved autonomous recovery (amount ≤ auto-authority)."""

    HUMAN_APPROVAL_REQUIRED = "HUMAN_APPROVAL_REQUIRED"
    """Policy requires human approval; case moved to HUMAN_REVIEW."""

    DEFERRED = "DEFERRED"
    """Policy deferred the action (e.g., quiet hours)."""

    # Human-in-the-loop / safe paths
    HUMAN_REVIEW = "HUMAN_REVIEW"
    """Case routed to human review for reasons other than approval threshold."""

    LEGAL_ESCALATION = "LEGAL_ESCALATION"
    """Legal / safety lock detected; automation stopped."""

    # Failure paths
    BLOCKED = "BLOCKED"
    """Policy blocked the action (e.g., amount exceeds collectible)."""

    STOPPED = "STOPPED"
    """Automation stopped (e.g., legal lock)."""

    EVIDENCE_INSUFFICIENT = "EVIDENCE_INSUFFICIENT"
    """Evidence is insufficient for safe resolution; routed to human review."""

    EVIDENCE_CONFLICT = "EVIDENCE_CONFLICT"
    """Evidence conflict detected; routed to human review."""

    AI_FAILURE = "AI_FAILURE"
    """One or more AI agents failed or returned NEEDS_HUMAN_REVIEW."""

    INVALID_STATE = "INVALID_STATE"
    """The case is in a state that does not permit orchestration."""

    INVALID_TRANSITION = "INVALID_TRANSITION"
    """The computed state transition was rejected by the State Machine."""

    DUPLICATE_RUN = "DUPLICATE_RUN"
    """An identical orchestration for this case has already been processed."""


# ---------------------------------------------------------------------------
# Orchestration input
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class OrchestratorInput:
    """All data required to run one orchestration pass.

    The orchestrator assembles AI inputs from these fields.  All monetary
    values are integer minor units (paise).  The caller is responsible for
    assembling authoritative values from the database before calling the
    orchestrator.

    IMPORTANT: This dataclass contains NO secrets and NO Razorpay credentials.
    """

    # --- Case identifiers ---
    case_id: str
    customer_id: str
    invoice_id: str

    # --- Current case state (authoritative, from DB) ---
    current_state: RecoveryCaseStatus

    # --- Financial inputs (supplied from DB, for Financial Calculation) ---
    gross_invoice_amount_minor: int
    valid_adjustments_minor: int = 0
    verified_payments_minor: int = 0
    claimed_disputed_amount_minor: int = 0
    verified_disputed_amount_minor: int | None = None
    verified_recovered_amount_minor: int = 0
    currency: str = "INR"

    # --- Merchant policy (supplied by caller from merchant config) ---
    merchant_policy: MerchantPolicySnapshot | None = None

    # --- Evidence flags (may be set from prior evidence analysis) ---
    is_legal_locked: bool = False
    is_automation_locked: bool = False
    is_safety_violation: bool = False

    # --- Outreach history ---
    touchpoints_in_window: int = 0

    # --- Triage context (for TriageAgent input) ---
    triage_input: TriageInput | None = None

    # --- Evidence context (for EvidenceAgent input) ---
    evidence_input: EvidenceInput | None = None

    # --- Existing approval (for re-check, may be None) ---
    existing_approval: ApprovalRecord | None = None

    # --- Idempotency / run tracking ---
    run_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    requested_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    # --- Metadata ---
    metadata: dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Orchestration result
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class OrchestratorResult:
    """Structured result of one orchestration run.

    Carries full auditability metadata but does NOT persist AuditEvents
    (that is Phase 8's responsibility).  The orchestrator never initiates
    payment execution or calls Razorpay.
    """

    # --- Run identity ---
    run_id: str
    case_id: str
    status: OrchestratorStatus
    status_detail: str

    # --- State transition result (may be None if no transition attempted) ---
    state_before: RecoveryCaseStatus | None
    state_after: RecoveryCaseStatus | None
    transition_result: TransitionResult | None = None

    # --- Financial calculation result (authoritative) ---
    financial_result: FinancialCalculationResult | None = None

    # --- Policy decision (deterministic) ---
    policy_decision: PolicyDecision | None = None

    # --- AI agent results (advisory, untrusted) ---
    triage_result: TriageAgentResult | None = None
    evidence_result: EvidenceAgentResult | None = None
    resolution_result: ResolutionAgentResult | None = None

    # --- Authoritative amount determined by Financial Calculation ---
    authoritative_recovery_amount_minor: int | None = None

    # --- Human approval requirement ---
    approval_required: bool = False
    approval_request_id: str | None = None

    # --- Legal / safety flags ---
    is_legal_locked: bool = False
    is_automation_locked: bool = False

    # --- Auditability metadata ---
    orchestrated_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    metadata: dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Idempotency registry (in-process; caller may replace with persistent store)
# ---------------------------------------------------------------------------


class _InProcessIdempotencyStore:
    """Minimal in-process idempotency store for orchestration runs.

    Tracks (case_id, fingerprint) pairs that have already been processed
    within this process lifetime.  For production, swap with a persistent
    implementation backed by the ``orchestration_runs`` table.

    This is intentionally lightweight: the orchestrator accepts an injected
    store so tests can control idempotency behavior.
    """

    def __init__(self) -> None:
        self._seen: dict[str, str] = {}  # {key → run_id}

    def check_and_register(self, case_id: str, fingerprint: str, run_id: str) -> str | None:
        """Register a run and return the prior run_id if already processed.

        Returns:
            The run_id of the prior run if this (case_id, fingerprint) pair
            was already seen, or None if this is the first occurrence.
        """
        key = f"{case_id}:{fingerprint}"
        if key in self._seen:
            return self._seen[key]
        self._seen[key] = run_id
        return None

    def clear(self) -> None:
        """Clear all registered runs (useful in tests)."""
        self._seen.clear()


# ---------------------------------------------------------------------------
# Fingerprint helpers
# ---------------------------------------------------------------------------


def _compute_orchestration_fingerprint(inputs: OrchestratorInput) -> str:
    """Compute a deterministic fingerprint for an orchestration run.

    Used for idempotency detection.  The fingerprint is based on the case
    state and financial snapshot — not the run_id (which changes each call).
    """
    payload = json.dumps(
        {
            "case_id": inputs.case_id,
            "current_state": inputs.current_state.value,
            "gross_invoice_amount_minor": inputs.gross_invoice_amount_minor,
            "valid_adjustments_minor": inputs.valid_adjustments_minor,
            "verified_payments_minor": inputs.verified_payments_minor,
            "claimed_disputed_amount_minor": inputs.claimed_disputed_amount_minor,
            "verified_disputed_amount_minor": inputs.verified_disputed_amount_minor,
            "verified_recovered_amount_minor": inputs.verified_recovered_amount_minor,
            "is_legal_locked": inputs.is_legal_locked,
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# States from which the orchestrator may initiate a new run
# ---------------------------------------------------------------------------

_ORCHESTRATABLE_STATES: frozenset[RecoveryCaseStatus] = frozenset({
    RecoveryCaseStatus.OVERDUE,
    RecoveryCaseStatus.TRIAGING,
    RecoveryCaseStatus.ISSUE_IDENTIFIED,
    RecoveryCaseStatus.EVIDENCE_ANALYSIS,
    RecoveryCaseStatus.RESOLUTION_READY,
    RecoveryCaseStatus.POLICY_REVIEW,
})

# States that require no further autonomous AI work — fail-fast guard
_BLOCKED_ENTRY_STATES: frozenset[RecoveryCaseStatus] = frozenset({
    RecoveryCaseStatus.LEGAL_ESCALATION,
    RecoveryCaseStatus.AUTOMATION_LOCKED,
    RecoveryCaseStatus.CLOSED,
    RecoveryCaseStatus.FULLY_RECOVERED,
    RecoveryCaseStatus.RECOVERY_INITIATED,
    RecoveryCaseStatus.PAYMENT_PENDING,
})

# Map from ResolutionProposalAction to RecoveryActionType for policy evaluation
_PROPOSAL_TO_ACTION_TYPE: dict[ResolutionProposalAction, RecoveryActionType] = {
    ResolutionProposalAction.CREATE_FULL_RECOVERY: RecoveryActionType.CREATE_PAYMENT_LINK,
    ResolutionProposalAction.CREATE_PARTIAL_RECOVERY: RecoveryActionType.CREATE_PARTIAL_RECOVERY,
    ResolutionProposalAction.REQUEST_DOCUMENT: RecoveryActionType.SEND_REMINDER,
    ResolutionProposalAction.REQUEST_CORRECTION: RecoveryActionType.SEND_REMINDER,
    ResolutionProposalAction.WAIT_FOR_PROMISE: RecoveryActionType.SEND_REMINDER,
    ResolutionProposalAction.STOP_OUTREACH: RecoveryActionType.ESCALATE_TO_HUMAN,
    ResolutionProposalAction.ESCALATE_HUMAN: RecoveryActionType.ESCALATE_TO_HUMAN,
    ResolutionProposalAction.ESCALATE_LEGAL: RecoveryActionType.ESCALATE_TO_HUMAN,
}


def _map_proposal_action(action: ResolutionProposalAction) -> RecoveryActionType:
    return _PROPOSAL_TO_ACTION_TYPE.get(action, RecoveryActionType.ESCALATE_TO_HUMAN)


# ---------------------------------------------------------------------------
# RecoveryOrchestrator
# ---------------------------------------------------------------------------


class RecoveryOrchestrator:
    """Deterministic coordinator for the full recovery pipeline.

    Coordinates AI advisory agents, Financial Calculation, Policy Engine,
    State Machine, and Human Approval Service into one structured workflow.

    This class:
      - accepts injected AI agents, deterministic services, and an optional
        idempotency store (dependency injection for testability);
      - runs each stage in the documented order;
      - fails closed on any unexpected failure;
      - produces a structured OrchestratorResult with auditability metadata;
      - NEVER calls Razorpay or any payment provider;
      - NEVER persists AuditEvents (Phase 8);
      - NEVER executes a payment;
      - NEVER treats AI output as financial authority.
    """

    def __init__(
        self,
        *,
        triage_agent: TriageAgent,
        evidence_agent: EvidenceAgent,
        resolution_agent: ResolutionAgent,
        policy_engine: PolicyEngineService | None = None,
        state_machine: StateMachineService | None = None,
        approval_service: HumanApprovalService | None = None,
        idempotency_store: _InProcessIdempotencyStore | None = None,
    ) -> None:
        self._triage = triage_agent
        self._evidence = evidence_agent
        self._resolution = resolution_agent
        self._policy = policy_engine or PolicyEngineService()
        self._state_machine = state_machine or StateMachineService()
        self._approval_svc = approval_service or HumanApprovalService()
        self._idempotency = idempotency_store or _InProcessIdempotencyStore()

    # -----------------------------------------------------------------------
    # Main entry point
    # -----------------------------------------------------------------------

    def run(self, inputs: OrchestratorInput) -> OrchestratorResult:
        """Execute one full orchestration pass for a recovery case.

        Returns an OrchestratorResult describing the pipeline outcome.
        Raises no exceptions — all failures are captured in the result.
        """
        run_id = inputs.run_id
        case_id = inputs.case_id

        # --- 0. Idempotency check ---
        fingerprint = _compute_orchestration_fingerprint(inputs)
        prior_run_id = self._idempotency.check_and_register(case_id, fingerprint, run_id)
        if prior_run_id is not None:
            return OrchestratorResult(
                run_id=run_id,
                case_id=case_id,
                status=OrchestratorStatus.DUPLICATE_RUN,
                status_detail=(
                    f"Duplicate orchestration: case {case_id} with identical "
                    f"state fingerprint was already processed by run {prior_run_id}"
                ),
                state_before=inputs.current_state,
                state_after=inputs.current_state,
                metadata={"prior_run_id": prior_run_id, "fingerprint": fingerprint},
            )

        # --- 1. State guard — fail closed on prohibited entry states ---
        if inputs.current_state in _BLOCKED_ENTRY_STATES:
            return self._result_invalid_state(inputs, run_id)

        # --- 2. Legal / safety interrupt — highest priority ---
        if inputs.is_legal_locked or inputs.is_safety_violation:
            return self._handle_legal_lock(inputs, run_id)

        if inputs.is_automation_locked:
            return self._result(
                run_id=run_id,
                inputs=inputs,
                status=OrchestratorStatus.STOPPED,
                detail=(
                    "Case is automation-locked; all autonomous execution forbidden. "
                    "No state transition attempted."
                ),
                is_automation_locked=True,
            )

        # --- 3. Triage stage ---
        triage_result = self._run_triage(inputs)
        if triage_result.status != TriageOutcomeStatus.SUCCESS or triage_result.output is None:
            return self._result(
                run_id=run_id,
                inputs=inputs,
                status=OrchestratorStatus.AI_FAILURE,
                detail=(
                    f"Triage agent failed or returned NEEDS_HUMAN_REVIEW: "
                    f"{triage_result.failure_detail}"
                ),
                triage_result=triage_result,
                transition_result=self._try_transition(
                    inputs, RecoveryEvent.REVIEW_COMPLETED, triage_result=triage_result
                ),
            )

        triage_output: TriageOutput = triage_result.output

        # Legal risk detected via triage semantic reading
        if TriageRiskFlag.LEGAL_ESCALATION in triage_output.risk_flags:
            transition = self._try_transition(
                inputs, RecoveryEvent.LEGAL_RISK_DETECTED, triage_result=triage_result
            )
            return OrchestratorResult(
                run_id=run_id,
                case_id=case_id,
                status=OrchestratorStatus.LEGAL_ESCALATION,
                status_detail=(
                    "Triage detected legal risk; automation locked. "
                    "Case escalated to LEGAL_ESCALATION."
                ),
                state_before=inputs.current_state,
                state_after=(
                    transition.state_after if transition and transition.allowed
                    else inputs.current_state
                ),
                transition_result=transition,
                triage_result=triage_result,
                is_legal_locked=True,
                metadata={"triggered_by": "triage_legal_risk_flag"},
            )

        # --- 4. Transition: OVERDUE → TRIAGING → ISSUE_IDENTIFIED ---
        current_state = inputs.current_state
        if current_state == RecoveryCaseStatus.OVERDUE:
            t = self._try_transition(inputs, RecoveryEvent.START_TRIAGE, from_state=current_state)
            if t and t.allowed:
                current_state = t.state_after

        if current_state == RecoveryCaseStatus.TRIAGING:
            t = self._try_transition(
                inputs, RecoveryEvent.TRIAGE_COMPLETED, from_state=current_state
            )
            if t and t.allowed:
                current_state = t.state_after

        # --- 5. Evidence Analysis ---
        if not triage_output.requires_evidence_analysis and not inputs.evidence_input:
            # No evidence analysis needed — advance state through evidence transitions
            # so the state machine is in RESOLUTION_READY before policy evaluation.
            evidence_result: EvidenceAgentResult | None = None
            evidence_output: EvidenceOutput | None = None
            evidence_conflict = False
            evidence_sufficient = True
            # Still need to advance through ISSUE_IDENTIFIED → EVIDENCE_ANALYSIS → RESOLUTION_READY
            if current_state == RecoveryCaseStatus.ISSUE_IDENTIFIED:
                t = self._try_transition(
                    inputs, RecoveryEvent.START_EVIDENCE_ANALYSIS, from_state=current_state
                )
                if t and t.allowed:
                    current_state = t.state_after
            if current_state == RecoveryCaseStatus.EVIDENCE_ANALYSIS:
                t = self._try_transition(
                    inputs, RecoveryEvent.EVIDENCE_SUFFICIENT, from_state=current_state
                )
                if t and t.allowed:
                    current_state = t.state_after

        else:
            # Transition to EVIDENCE_ANALYSIS if appropriate
            if current_state == RecoveryCaseStatus.ISSUE_IDENTIFIED:
                t = self._try_transition(
                    inputs, RecoveryEvent.START_EVIDENCE_ANALYSIS, from_state=current_state
                )
                if t and t.allowed:
                    current_state = t.state_after

            evidence_result = self._run_evidence(inputs)
            if (
                evidence_result.status != EvidenceOutcomeStatus.SUCCESS
                or evidence_result.output is None
            ):
                # Evidence agent failed — route to human review
                tr = self._try_transition(
                    inputs, RecoveryEvent.EVIDENCE_INSUFFICIENT, from_state=current_state
                )
                return OrchestratorResult(
                    run_id=run_id,
                    case_id=case_id,
                    status=OrchestratorStatus.AI_FAILURE,
                    status_detail=(
                        f"Evidence agent failed or returned NEEDS_HUMAN_REVIEW: "
                        f"{evidence_result.failure_detail}"
                    ),
                    state_before=inputs.current_state,
                    state_after=tr.state_after if tr and tr.allowed else current_state,
                    transition_result=tr,
                    triage_result=triage_result,
                    evidence_result=evidence_result,
                )

            evidence_output = evidence_result.output

            # Check for evidence conflicts
            evidence_conflict = (
                evidence_output.finding == EvidenceFindingStatus.CONFLICTING
                or bool(evidence_output.conflicts)
            )
            evidence_insufficient = (
                evidence_output.finding == EvidenceFindingStatus.INSUFFICIENT_EVIDENCE
                or evidence_output.requires_human_review
            )
            evidence_sufficient = not (evidence_conflict or evidence_insufficient)

            if evidence_conflict:
                tr = self._try_transition(
                    inputs, RecoveryEvent.EVIDENCE_CONFLICT, from_state=current_state
                )
                return OrchestratorResult(
                    run_id=run_id,
                    case_id=case_id,
                    status=OrchestratorStatus.EVIDENCE_CONFLICT,
                    status_detail=(
                        "Evidence agent detected material conflicts; "
                        "autonomous resolution forbidden. Routed to human review."
                    ),
                    state_before=inputs.current_state,
                    state_after=tr.state_after if tr and tr.allowed else current_state,
                    transition_result=tr,
                    triage_result=triage_result,
                    evidence_result=evidence_result,
                    metadata={"evidence_finding": evidence_output.finding},
                )

            if evidence_insufficient:
                tr = self._try_transition(
                    inputs, RecoveryEvent.EVIDENCE_INSUFFICIENT, from_state=current_state
                )
                return OrchestratorResult(
                    run_id=run_id,
                    case_id=case_id,
                    status=OrchestratorStatus.EVIDENCE_INSUFFICIENT,
                    status_detail=(
                        "Evidence is insufficient for safe autonomous resolution. "
                        "Routed to human review."
                    ),
                    state_before=inputs.current_state,
                    state_after=tr.state_after if tr and tr.allowed else current_state,
                    transition_result=tr,
                    triage_result=triage_result,
                    evidence_result=evidence_result,
                    metadata={"evidence_finding": evidence_output.finding},
                )

            # Sufficient evidence → RESOLUTION_READY
            if current_state == RecoveryCaseStatus.EVIDENCE_ANALYSIS:
                t = self._try_transition(
                    inputs, RecoveryEvent.EVIDENCE_SUFFICIENT, from_state=current_state
                )
                if t and t.allowed:
                    current_state = t.state_after

        # --- 6. Financial Calculation (authoritative) ---
        fin_result = self._run_financial_calculation(inputs)

        if fin_result.status in (
            FinancialAssessmentStatus.INSUFFICIENT,
            FinancialAssessmentStatus.CONFLICTING,
            FinancialAssessmentStatus.INVALID,
        ):
            return OrchestratorResult(
                run_id=run_id,
                case_id=case_id,
                status=OrchestratorStatus.EVIDENCE_INSUFFICIENT,
                status_detail=(
                    f"Financial calculation returned {fin_result.status}; "
                    "cannot determine safe recovery amount. Routed to human review."
                ),
                state_before=inputs.current_state,
                state_after=current_state,
                financial_result=fin_result,
                triage_result=triage_result,
                evidence_result=evidence_result,  # type: ignore[arg-type]
            )

        # Authoritative collectible amount (NOT from AI)
        authoritative_amount = fin_result.collectible_amount_minor
        if authoritative_amount <= 0:
            return OrchestratorResult(
                run_id=run_id,
                case_id=case_id,
                status=OrchestratorStatus.BLOCKED,
                status_detail=(
                    "Authoritative collectible amount is zero or negative; "
                    "no recovery action possible."
                ),
                state_before=inputs.current_state,
                state_after=current_state,
                financial_result=fin_result,
                triage_result=triage_result,
                evidence_result=evidence_result,  # type: ignore[arg-type]
                authoritative_recovery_amount_minor=0,
            )

        # --- 7. Resolution Agent (AI, advisory) ---
        resolution_result = self._run_resolution(inputs, triage_output, evidence_output, fin_result)
        if (
            resolution_result.status != ResolutionOutcomeStatus.SUCCESS
            or resolution_result.output is None
        ):
            return OrchestratorResult(
                run_id=run_id,
                case_id=case_id,
                status=OrchestratorStatus.AI_FAILURE,
                status_detail=(
                    f"Resolution agent failed or returned NEEDS_HUMAN_REVIEW: "
                    f"{resolution_result.failure_detail}"
                ),
                state_before=inputs.current_state,
                state_after=current_state,
                financial_result=fin_result,
                triage_result=triage_result,
                evidence_result=evidence_result,  # type: ignore[arg-type]
                resolution_result=resolution_result,
                authoritative_recovery_amount_minor=authoritative_amount,
            )

        resolution_output: ResolutionOutput = resolution_result.output

        # AI confidence guard — low confidence escalates to human review
        if resolution_output.confidence < 0.3:
            return OrchestratorResult(
                run_id=run_id,
                case_id=case_id,
                status=OrchestratorStatus.HUMAN_REVIEW,
                status_detail=(
                    f"Resolution agent confidence ({resolution_output.confidence:.2f}) "
                    "is below threshold (0.30); routing to human review."
                ),
                state_before=inputs.current_state,
                state_after=current_state,
                financial_result=fin_result,
                triage_result=triage_result,
                evidence_result=evidence_result,  # type: ignore[arg-type]
                resolution_result=resolution_result,
                authoritative_recovery_amount_minor=authoritative_amount,
                metadata={"ai_confidence": resolution_output.confidence},
            )

        # --- 8. Map AI recommendation to policy input ---
        # CRITICAL: The authoritative amount comes from Financial Calculation,
        # NOT from the AI recommendation. The AI amount is advisory only.
        action_type = _map_proposal_action(resolution_output.action)
        is_monetary = resolution_output.action in (
            ResolutionProposalAction.CREATE_FULL_RECOVERY,
            ResolutionProposalAction.CREATE_PARTIAL_RECOVERY,
        )

        # For monetary actions, use authoritative amount (never AI amount)
        policy_amount = authoritative_amount if is_monetary else 0

        # --- 9. Transition to POLICY_REVIEW ---
        if current_state == RecoveryCaseStatus.RESOLUTION_READY:
            t = self._try_transition(
                inputs, RecoveryEvent.SUBMIT_RESOLUTION_FOR_POLICY, from_state=current_state
            )
            if t and t.allowed:
                current_state = t.state_after

        # --- 10. Policy Evaluation (deterministic, authoritative) ---
        policy_input = PolicyEvaluationInput(
            case_id=case_id,
            current_state=current_state,
            action_type=action_type,
            proposed_amount=policy_amount,
            financial_assessment=FinancialAssessmentSnapshot(
                status=fin_result.status.value,
                gross_invoice_amount_minor=fin_result.gross_invoice_amount_minor,
                collectible_amount_minor=fin_result.collectible_amount_minor,
                safely_recoverable_amount_minor=fin_result.safely_recoverable_amount_minor,
                verified_recovered_amount_minor=fin_result.verified_recovered_amount_minor,
                remaining_amount_minor=fin_result.remaining_amount_minor,
            ),
            merchant_policy=inputs.merchant_policy,
            evidence_sufficient=evidence_sufficient,  # type: ignore[possibly-undefined]
            evidence_conflict=evidence_conflict,  # type: ignore[possibly-undefined]
            is_legal_locked=inputs.is_legal_locked,
            is_automation_locked=inputs.is_automation_locked,
            is_safety_violation=inputs.is_safety_violation,
            touchpoints_in_window=inputs.touchpoints_in_window,
            invoice_amount=fin_result.gross_invoice_amount_minor,
        )
        policy_decision: PolicyDecision = self._policy.evaluate(policy_input)

        # --- 11. Route based on policy decision ---
        return self._route_policy_decision(
            inputs=inputs,
            run_id=run_id,
            current_state=current_state,
            policy_decision=policy_decision,
            fin_result=fin_result,
            authoritative_amount=authoritative_amount if is_monetary else None,
            triage_result=triage_result,
            evidence_result=evidence_result,  # type: ignore[arg-type]
            resolution_result=resolution_result,
            evidence_conflict=evidence_conflict,  # type: ignore[possibly-undefined]
            evidence_sufficient=evidence_sufficient,  # type: ignore[possibly-undefined]
        )

    # -----------------------------------------------------------------------
    # Policy decision router
    # -----------------------------------------------------------------------

    def _route_policy_decision(
        self,
        *,
        inputs: OrchestratorInput,
        run_id: str,
        current_state: RecoveryCaseStatus,
        policy_decision: PolicyDecision,
        fin_result: FinancialCalculationResult,
        authoritative_amount: int | None,
        triage_result: TriageAgentResult,
        evidence_result: EvidenceAgentResult | None,
        resolution_result: ResolutionAgentResult,
        evidence_conflict: bool,
        evidence_sufficient: bool,
    ) -> OrchestratorResult:
        """Route the orchestration result based on the deterministic policy decision."""
        case_id = inputs.case_id
        decision = policy_decision.decision

        if decision == PolicyDecisionResult.APPROVED:
            # Transition POLICY_REVIEW → RECOVERY_INITIATED
            ctx = TransitionContext(
                policy_decision=decision.value,
                has_valid_proposal=True,
                has_valid_financial_assessment=True,
                has_valid_policy_approval=True,
                is_legal_locked=inputs.is_legal_locked,
                is_automation_locked=inputs.is_automation_locked,
            )
            try:
                tr = self._state_machine.transition(
                    current_state, RecoveryEvent.POLICY_APPROVED, ctx
                )
            except (InvalidTransitionError, TransitionGuardError) as exc:
                return OrchestratorResult(
                    run_id=run_id,
                    case_id=case_id,
                    status=OrchestratorStatus.INVALID_TRANSITION,
                    status_detail=f"State transition rejected: {exc}",
                    state_before=inputs.current_state,
                    state_after=current_state,
                    policy_decision=policy_decision,
                    financial_result=fin_result,
                    triage_result=triage_result,
                    evidence_result=evidence_result,
                    resolution_result=resolution_result,
                    authoritative_recovery_amount_minor=authoritative_amount,
                )
            return OrchestratorResult(
                run_id=run_id,
                case_id=case_id,
                status=OrchestratorStatus.APPROVED,
                status_detail=(
                    f"Policy APPROVED. Authoritative recovery amount: "
                    f"{authoritative_amount} paise. "
                    f"State: {tr.state_before} → {tr.state_after}."
                ),
                state_before=inputs.current_state,
                state_after=tr.state_after,
                transition_result=tr,
                financial_result=fin_result,
                policy_decision=policy_decision,
                triage_result=triage_result,
                evidence_result=evidence_result,
                resolution_result=resolution_result,
                authoritative_recovery_amount_minor=authoritative_amount,
            )

        elif decision == PolicyDecisionResult.HUMAN_APPROVAL_REQUIRED:
            # Transition POLICY_REVIEW → HUMAN_REVIEW
            try:
                tr = self._state_machine.transition(
                    current_state, RecoveryEvent.HUMAN_APPROVAL_REQUIRED
                )
            except (InvalidTransitionError, TransitionGuardError) as exc:
                tr = None  # type: ignore[assignment]
                detail_suffix = f" [transition failed: {exc}]"
            else:
                detail_suffix = ""

            # Create an approval request identifier for traceability
            approval_request_id = str(uuid.uuid4())

            return OrchestratorResult(
                run_id=run_id,
                case_id=case_id,
                status=OrchestratorStatus.HUMAN_APPROVAL_REQUIRED,
                status_detail=(
                    f"Policy requires human approval "
                    f"(reason: {policy_decision.reason_code}). "
                    f"Authoritative amount: {authoritative_amount} paise. "
                    f"Approval request ID: {approval_request_id}.{detail_suffix}"
                ),
                state_before=inputs.current_state,
                state_after=tr.state_after if tr and tr.allowed else current_state,
                transition_result=tr,
                financial_result=fin_result,
                policy_decision=policy_decision,
                triage_result=triage_result,
                evidence_result=evidence_result,
                resolution_result=resolution_result,
                authoritative_recovery_amount_minor=authoritative_amount,
                approval_required=True,
                approval_request_id=approval_request_id,
            )

        elif decision == PolicyDecisionResult.DEFERRED:
            # Transition POLICY_REVIEW → RESOLUTION_READY (deferred)
            try:
                tr = self._state_machine.transition(
                    current_state, RecoveryEvent.POLICY_DEFERRED
                )
            except (InvalidTransitionError, TransitionGuardError):
                tr = None  # type: ignore[assignment]
            return OrchestratorResult(
                run_id=run_id,
                case_id=case_id,
                status=OrchestratorStatus.DEFERRED,
                status_detail=(
                    f"Policy DEFERRED (reason: {policy_decision.reason_code}). "
                    "Case returned to RESOLUTION_READY for retry."
                ),
                state_before=inputs.current_state,
                state_after=tr.state_after if tr and tr.allowed else current_state,
                transition_result=tr,
                financial_result=fin_result,
                policy_decision=policy_decision,
                triage_result=triage_result,
                evidence_result=evidence_result,
                resolution_result=resolution_result,
                authoritative_recovery_amount_minor=authoritative_amount,
            )

        elif decision == PolicyDecisionResult.BLOCKED:
            # Transition POLICY_REVIEW → HUMAN_REVIEW
            try:
                tr = self._state_machine.transition(
                    current_state, RecoveryEvent.POLICY_BLOCKED
                )
            except (InvalidTransitionError, TransitionGuardError):
                tr = None  # type: ignore[assignment]
            return OrchestratorResult(
                run_id=run_id,
                case_id=case_id,
                status=OrchestratorStatus.BLOCKED,
                status_detail=(
                    f"Policy BLOCKED (reason: {policy_decision.reason_code}): "
                    f"{policy_decision.blocking_reason}"
                ),
                state_before=inputs.current_state,
                state_after=tr.state_after if tr and tr.allowed else current_state,
                transition_result=tr,
                financial_result=fin_result,
                policy_decision=policy_decision,
                triage_result=triage_result,
                evidence_result=evidence_result,
                resolution_result=resolution_result,
                authoritative_recovery_amount_minor=authoritative_amount,
            )

        elif decision == PolicyDecisionResult.STOPPED:
            # Transition POLICY_REVIEW → AUTOMATION_LOCKED
            try:
                tr = self._state_machine.transition(
                    current_state, RecoveryEvent.POLICY_STOPPED
                )
            except (InvalidTransitionError, TransitionGuardError):
                tr = None  # type: ignore[assignment]
            return OrchestratorResult(
                run_id=run_id,
                case_id=case_id,
                status=OrchestratorStatus.STOPPED,
                status_detail=(
                    f"Policy STOPPED (reason: {policy_decision.reason_code}): "
                    f"{policy_decision.blocking_reason}"
                ),
                state_before=inputs.current_state,
                state_after=tr.state_after if tr and tr.allowed else current_state,
                transition_result=tr,
                financial_result=fin_result,
                policy_decision=policy_decision,
                triage_result=triage_result,
                evidence_result=evidence_result,
                resolution_result=resolution_result,
                authoritative_recovery_amount_minor=authoritative_amount,
                is_automation_locked=True,
            )

        # Fallback (should not occur with valid PolicyDecisionResult)
        return OrchestratorResult(
            run_id=run_id,
            case_id=case_id,
            status=OrchestratorStatus.BLOCKED,
            status_detail=f"Unexpected policy decision: {decision}",
            state_before=inputs.current_state,
            state_after=current_state,
            policy_decision=policy_decision,
            financial_result=fin_result,
            triage_result=triage_result,
            evidence_result=evidence_result,
            resolution_result=resolution_result,
        )

    # -----------------------------------------------------------------------
    # AI stage runners
    # -----------------------------------------------------------------------

    def _run_triage(self, inputs: OrchestratorInput) -> TriageAgentResult:
        """Run the Triage Agent if a TriageInput is available."""
        if inputs.triage_input is None:
            # Build a minimal triage input from the case context
            from app.ai.triage_contracts import TriageInput as _TriageInput

            triage_input = _TriageInput(
                case_id=inputs.case_id,
                case_summary=f"Recovery case for invoice {inputs.invoice_id}",
            )
        else:
            triage_input = inputs.triage_input
        return self._triage.run(triage_input)

    def _run_evidence(self, inputs: OrchestratorInput) -> EvidenceAgentResult:
        """Run the Evidence Agent if an EvidenceInput is available."""
        if inputs.evidence_input is None:
            from app.ai.evidence_contracts import EvidenceInput as _EvidenceInput

            evidence_input = _EvidenceInput(case_id=inputs.case_id)
        else:
            evidence_input = inputs.evidence_input
        return self._evidence.run(evidence_input)

    def _run_resolution(
        self,
        inputs: OrchestratorInput,
        triage_output: TriageOutput,
        evidence_output: EvidenceOutput | None,
        fin_result: FinancialCalculationResult,
    ) -> ResolutionAgentResult:
        """Run the Resolution Agent with advisory financial context.

        IMPORTANT: The amounts passed to the Resolution Agent are for
        observational context only.  The Resolution Agent's recommended
        amount is NEVER used as the authoritative recovery amount.
        The authoritative amount comes solely from Financial Calculation.
        """
        resolution_input = ResolutionInput(
            case_id=inputs.case_id,
            triage_issue_type=triage_output.issue_type.value,
            triage_summary=triage_output.summary,
            evidence_finding=evidence_output.finding.value if evidence_output else None,
            evidence_summary=evidence_output.summary if evidence_output else None,
            # Advisory-only context — amounts are from authoritative calc for
            # AI observability, but the AI output amount is NEVER authoritative
            verified_collectible_amount_minor=fin_result.collectible_amount_minor,
            verified_disputed_amount_minor=fin_result.verified_disputed_amount_minor,
            current_outstanding_amount_minor=fin_result.current_outstanding_amount_minor,
            current_case_state=inputs.current_state.value,
            available_evidence_ids=tuple(inputs.evidence_input.known_evidence_ids)
            if inputs.evidence_input
            else (),
            communications=inputs.evidence_input.communications
            if inputs.evidence_input
            else (),
        )
        return self._resolution.run(resolution_input)

    # -----------------------------------------------------------------------
    # Financial calculation (authoritative)
    # -----------------------------------------------------------------------

    def _run_financial_calculation(
        self, inputs: OrchestratorInput
    ) -> FinancialCalculationResult:
        """Run the deterministic Financial Calculation Service.

        This is the SOLE source of authoritative financial amounts.
        No AI output may override this result.
        """
        fin_input = FinancialCalculationInput(
            gross_invoice_amount_minor=inputs.gross_invoice_amount_minor,
            valid_adjustments_minor=inputs.valid_adjustments_minor,
            verified_payments_minor=inputs.verified_payments_minor,
            claimed_disputed_amount_minor=inputs.claimed_disputed_amount_minor,
            verified_disputed_amount_minor=inputs.verified_disputed_amount_minor,
            verified_recovered_amount_minor=inputs.verified_recovered_amount_minor,
            currency=inputs.currency,
        )
        return calculate_financial_position(fin_input)

    # -----------------------------------------------------------------------
    # State machine helpers
    # -----------------------------------------------------------------------

    def _try_transition(
        self,
        inputs: OrchestratorInput,
        event: RecoveryEvent,
        *,
        from_state: RecoveryCaseStatus | None = None,
        triage_result: TriageAgentResult | None = None,
        ctx: TransitionContext | None = None,
    ) -> TransitionResult | None:
        """Attempt a state transition; return None on invalid transition.

        Args:
            inputs: Orchestration inputs (used for lock flags and fallback state).
            event: The domain event to fire.
            from_state: The state to transition FROM.  If not specified, falls
                back to ``inputs.current_state`` (the original entry state).
                Pass the evolving local ``current_state`` variable for
                intermediate transitions within a single orchestration run.
            triage_result: Unused — kept for future guard context extension.
            ctx: Optional explicit TransitionContext.  Built from lock flags if None.
        """
        state = from_state if from_state is not None else inputs.current_state
        if ctx is None:
            ctx = TransitionContext(
                is_legal_locked=inputs.is_legal_locked,
                is_automation_locked=inputs.is_automation_locked,
            )
        try:
            return self._state_machine.transition(state, event, ctx)
        except (InvalidTransitionError, TransitionGuardError):
            return None

    # -----------------------------------------------------------------------
    # Result builders
    # -----------------------------------------------------------------------

    def _result_invalid_state(self, inputs: OrchestratorInput, run_id: str) -> OrchestratorResult:
        return OrchestratorResult(
            run_id=run_id,
            case_id=inputs.case_id,
            status=OrchestratorStatus.INVALID_STATE,
            status_detail=(
                f"Case is in state {inputs.current_state} which does not permit "
                "orchestration. Orchestration aborted without side effects."
            ),
            state_before=inputs.current_state,
            state_after=inputs.current_state,
        )

    def _handle_legal_lock(self, inputs: OrchestratorInput, run_id: str) -> OrchestratorResult:
        """Handle legal / safety lock at the earliest point."""
        ctx = TransitionContext(is_legal_locked=True)
        try:
            tr = self._state_machine.transition(
                inputs.current_state, RecoveryEvent.LEGAL_RISK_DETECTED, ctx
            )
        except (InvalidTransitionError, TransitionGuardError):
            tr = None
        return OrchestratorResult(
            run_id=run_id,
            case_id=inputs.case_id,
            status=OrchestratorStatus.LEGAL_ESCALATION,
            status_detail=(
                "Legal lock or safety violation detected on case input. "
                "All autonomous execution forbidden."
            ),
            state_before=inputs.current_state,
            state_after=tr.state_after if tr and tr.allowed else inputs.current_state,
            transition_result=tr,
            is_legal_locked=inputs.is_legal_locked,
            is_automation_locked=True,
        )

    def _result(
        self,
        *,
        run_id: str,
        inputs: OrchestratorInput,
        status: OrchestratorStatus,
        detail: str,
        triage_result: TriageAgentResult | None = None,
        evidence_result: EvidenceAgentResult | None = None,
        resolution_result: ResolutionAgentResult | None = None,
        financial_result: FinancialCalculationResult | None = None,
        policy_decision: PolicyDecision | None = None,
        transition_result: TransitionResult | None = None,
        authoritative_recovery_amount_minor: int | None = None,
        is_legal_locked: bool = False,
        is_automation_locked: bool = False,
        metadata: dict[str, Any] | None = None,
    ) -> OrchestratorResult:
        state_after = (
            transition_result.state_after
            if transition_result and transition_result.allowed
            else inputs.current_state
        )
        return OrchestratorResult(
            run_id=run_id,
            case_id=inputs.case_id,
            status=status,
            status_detail=detail,
            state_before=inputs.current_state,
            state_after=state_after,
            transition_result=transition_result,
            financial_result=financial_result,
            policy_decision=policy_decision,
            triage_result=triage_result,
            evidence_result=evidence_result,
            resolution_result=resolution_result,
            authoritative_recovery_amount_minor=authoritative_recovery_amount_minor,
            is_legal_locked=is_legal_locked,
            is_automation_locked=is_automation_locked,
            metadata=metadata or {},
        )
