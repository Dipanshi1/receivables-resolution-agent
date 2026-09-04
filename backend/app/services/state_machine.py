"""Deterministic Recovery Case State Machine.

Implements the authoritative state-transition engine for RecoveryCase as specified
in docs/02-engineering/state-machine.md.

Rules:
  - Pure deterministic logic only.
  - No LLM/AI dependencies.
  - No Razorpay/external I/O.
  - No database mutation inside the transition function.
  - No financial calculations — consumes validated financial facts.
  - An LLM must never directly change RecoveryCase state.

The State Machine controls:
  - valid Recovery Case states
  - allowed transitions
  - transition triggers (domain events)
  - transition conditions (guards)
  - exceptional paths / safety interrupts
  - terminal states
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from app.domain.enums import RecoveryCaseStatus

# ---------------------------------------------------------------------------
# Domain Events — these trigger state transitions
# ---------------------------------------------------------------------------

class RecoveryEvent(StrEnum):
    """Domain events that trigger state transitions.

    These are events, NOT states. PAYMENT_CONFIRMED is a verified domain event
    that leads to a recovery-outcome state — it is never a RecoveryCase state.
    """

    # Active Investigation
    INVOICE_OVERDUE = "INVOICE_OVERDUE"
    START_TRIAGE = "START_TRIAGE"
    TRIAGE_COMPLETED = "TRIAGE_COMPLETED"
    START_EVIDENCE_ANALYSIS = "START_EVIDENCE_ANALYSIS"

    # Evidence outcomes
    EVIDENCE_SUFFICIENT = "EVIDENCE_SUFFICIENT"
    EVIDENCE_INSUFFICIENT = "EVIDENCE_INSUFFICIENT"
    EVIDENCE_CONFLICT = "EVIDENCE_CONFLICT"

    # Resolution
    RESOLUTION_PROPOSED = "RESOLUTION_PROPOSED"
    SUBMIT_RESOLUTION_FOR_POLICY = "SUBMIT_RESOLUTION_FOR_POLICY"

    # Policy outcomes (events, not states)
    POLICY_APPROVED = "POLICY_APPROVED"
    POLICY_DEFERRED = "POLICY_DEFERRED"
    POLICY_BLOCKED = "POLICY_BLOCKED"
    POLICY_STOPPED = "POLICY_STOPPED"
    HUMAN_APPROVAL_REQUIRED = "HUMAN_APPROVAL_REQUIRED"

    # Human review
    HUMAN_APPROVAL_GRANTED = "HUMAN_APPROVAL_GRANTED"
    REVIEW_COMPLETED = "REVIEW_COMPLETED"
    REVIEW_ESCALATE_LEGAL = "REVIEW_ESCALATE_LEGAL"
    REVIEW_CLOSED = "REVIEW_CLOSED"
    REVIEW_BACK_TO_RESOLUTION = "REVIEW_BACK_TO_RESOLUTION"
    REVIEW_BACK_TO_POLICY = "REVIEW_BACK_TO_POLICY"

    # Recovery execution
    PAYMENT_REQUEST_CREATED = "PAYMENT_REQUEST_CREATED"
    EXECUTION_ERROR = "EXECUTION_ERROR"

    # Payment verification (domain events — NOT states)
    PAYMENT_CONFIRMED = "PAYMENT_CONFIRMED"
    PAYMENT_FAILED = "PAYMENT_FAILED"

    # Safety interrupts
    LEGAL_RISK_DETECTED = "LEGAL_RISK_DETECTED"
    MANUAL_LOCK = "MANUAL_LOCK"
    SYSTEM_INTEGRITY_FAILURE = "SYSTEM_INTEGRITY_FAILURE"

    # Execution failure handling
    RETRY_APPROVED = "RETRY_APPROVED"
    RETRY_EXHAUSTED = "RETRY_EXHAUSTED"

    # Partial recovery workflow
    INITIATE_REMAINING_RECOVERY = "INITIATE_REMAINING_RECOVERY"

    # Closure
    CASE_CLOSED = "CASE_CLOSED"

    # Legal escalation
    LEGAL_CLOSED = "LEGAL_CLOSED"

    # Automation lock release
    LOCK_RELEASED = "LOCK_RELEASED"
    LOCK_ESCALATE_LEGAL = "LOCK_ESCALATE_LEGAL"


# ---------------------------------------------------------------------------
# Transition context — guards / conditions supplied by the caller
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class TransitionContext:
    """Context supplied to the transition function for guard evaluation.

    The state machine does NOT calculate any financial values. These fields
    are consumed from upstream deterministic services (Financial Calculation
    Service, Policy Engine, Human Approval workflow, etc.).
    """

    # Policy decision result (consumed, not calculated)
    policy_decision: str | None = None

    # Verified financial facts (consumed, not calculated)
    verified_recovered_amount: int | None = None
    applicable_recoverable_balance: int | None = None

    # Recovery execution guards
    has_valid_proposal: bool = False
    has_valid_financial_assessment: bool = False
    has_valid_policy_approval: bool = False
    has_valid_human_approval: bool = False
    is_legal_locked: bool = False
    is_automation_locked: bool = False

    # Retry tracking
    retry_count: int = 0
    max_retries: int = 3

    # Payment verification flag
    payment_verified: bool = False

    # Actor / event identification
    event_id: str | None = None
    actor: str | None = None

    # Arbitrary metadata for audit
    metadata: dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Transition result
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class TransitionResult:
    """Result of a state transition attempt.

    Contains the previous state, event, next state, and reason/metadata.
    The 'allowed' flag indicates whether the transition was valid.
    """

    allowed: bool
    state_before: RecoveryCaseStatus
    state_after: RecoveryCaseStatus
    event: RecoveryEvent
    reason: str
    event_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------

class InvalidTransitionError(Exception):
    """Raised when an invalid state transition is attempted."""

    def __init__(
        self,
        state_before: RecoveryCaseStatus,
        event: RecoveryEvent,
        reason: str,
    ) -> None:
        self.state_before = state_before
        self.event = event
        self.reason = reason
        super().__init__(
            f"Invalid transition: {state_before} + {event} — {reason}"
        )


class TransitionGuardError(Exception):
    """Raised when a transition guard condition is not satisfied."""

    def __init__(
        self,
        state_before: RecoveryCaseStatus,
        event: RecoveryEvent,
        guard: str,
        reason: str,
    ) -> None:
        self.state_before = state_before
        self.event = event
        self.guard = guard
        self.reason = reason
        super().__init__(
            f"Guard failed: {guard} for {state_before} + {event} — {reason}"
        )


# ---------------------------------------------------------------------------
# Terminal and active state sets
# ---------------------------------------------------------------------------

# States from which CLOSED is the only permitted non-safety exit
TERMINAL_STATES: frozenset[RecoveryCaseStatus] = frozenset({
    RecoveryCaseStatus.CLOSED,
})

# States that represent successful recovery outcomes
RECOVERY_OUTCOME_STATES: frozenset[RecoveryCaseStatus] = frozenset({
    RecoveryCaseStatus.PARTIALLY_RECOVERED,
    RecoveryCaseStatus.FULLY_RECOVERED,
})

# States where safety interrupts are applicable (all non-terminal, non-locked states)
SAFETY_INTERRUPTIBLE_STATES: frozenset[RecoveryCaseStatus] = frozenset({
    RecoveryCaseStatus.OVERDUE,
    RecoveryCaseStatus.TRIAGING,
    RecoveryCaseStatus.ISSUE_IDENTIFIED,
    RecoveryCaseStatus.EVIDENCE_ANALYSIS,
    RecoveryCaseStatus.RESOLUTION_READY,
    RecoveryCaseStatus.POLICY_REVIEW,
    RecoveryCaseStatus.RECOVERY_INITIATED,
    RecoveryCaseStatus.PAYMENT_PENDING,
    RecoveryCaseStatus.PARTIALLY_RECOVERED,
    RecoveryCaseStatus.HUMAN_REVIEW,
    RecoveryCaseStatus.EXECUTION_FAILED,
})

# Financial execution states where SYSTEM_INTEGRITY_FAILURE applies
FINANCIAL_EXECUTION_STATES: frozenset[RecoveryCaseStatus] = frozenset({
    RecoveryCaseStatus.RECOVERY_INITIATED,
    RecoveryCaseStatus.PAYMENT_PENDING,
})


# ---------------------------------------------------------------------------
# Transition table — deterministic mapping of (state, event) → target state
# ---------------------------------------------------------------------------

# Each entry: (current_state, event) → target_state
# Guards are evaluated separately in _evaluate_guards()
_TRANSITION_TABLE: dict[
    tuple[RecoveryCaseStatus, RecoveryEvent],
    RecoveryCaseStatus,
] = {
    # --- OVERDUE ---
    (RecoveryCaseStatus.OVERDUE, RecoveryEvent.START_TRIAGE):
        RecoveryCaseStatus.TRIAGING,

    # --- TRIAGING ---
    (RecoveryCaseStatus.TRIAGING, RecoveryEvent.TRIAGE_COMPLETED):
        RecoveryCaseStatus.ISSUE_IDENTIFIED,
    (RecoveryCaseStatus.TRIAGING, RecoveryEvent.REVIEW_COMPLETED):
        RecoveryCaseStatus.HUMAN_REVIEW,

    # --- ISSUE_IDENTIFIED ---
    (RecoveryCaseStatus.ISSUE_IDENTIFIED, RecoveryEvent.START_EVIDENCE_ANALYSIS):
        RecoveryCaseStatus.EVIDENCE_ANALYSIS,
    (RecoveryCaseStatus.ISSUE_IDENTIFIED, RecoveryEvent.REVIEW_COMPLETED):
        RecoveryCaseStatus.HUMAN_REVIEW,

    # --- EVIDENCE_ANALYSIS ---
    (RecoveryCaseStatus.EVIDENCE_ANALYSIS, RecoveryEvent.EVIDENCE_SUFFICIENT):
        RecoveryCaseStatus.RESOLUTION_READY,
    (RecoveryCaseStatus.EVIDENCE_ANALYSIS, RecoveryEvent.EVIDENCE_INSUFFICIENT):
        RecoveryCaseStatus.HUMAN_REVIEW,
    (RecoveryCaseStatus.EVIDENCE_ANALYSIS, RecoveryEvent.EVIDENCE_CONFLICT):
        RecoveryCaseStatus.HUMAN_REVIEW,

    # --- RESOLUTION_READY ---
    (RecoveryCaseStatus.RESOLUTION_READY, RecoveryEvent.SUBMIT_RESOLUTION_FOR_POLICY):
        RecoveryCaseStatus.POLICY_REVIEW,
    (RecoveryCaseStatus.RESOLUTION_READY, RecoveryEvent.REVIEW_COMPLETED):
        RecoveryCaseStatus.HUMAN_REVIEW,

    # --- POLICY_REVIEW (5 outcomes) ---
    (RecoveryCaseStatus.POLICY_REVIEW, RecoveryEvent.POLICY_APPROVED):
        RecoveryCaseStatus.RECOVERY_INITIATED,
    (RecoveryCaseStatus.POLICY_REVIEW, RecoveryEvent.HUMAN_APPROVAL_REQUIRED):
        RecoveryCaseStatus.HUMAN_REVIEW,
    (RecoveryCaseStatus.POLICY_REVIEW, RecoveryEvent.POLICY_DEFERRED):
        RecoveryCaseStatus.RESOLUTION_READY,
    (RecoveryCaseStatus.POLICY_REVIEW, RecoveryEvent.POLICY_BLOCKED):
        RecoveryCaseStatus.HUMAN_REVIEW,
    (RecoveryCaseStatus.POLICY_REVIEW, RecoveryEvent.POLICY_STOPPED):
        RecoveryCaseStatus.AUTOMATION_LOCKED,

    # --- RECOVERY_INITIATED ---
    (RecoveryCaseStatus.RECOVERY_INITIATED, RecoveryEvent.PAYMENT_REQUEST_CREATED):
        RecoveryCaseStatus.PAYMENT_PENDING,
    (RecoveryCaseStatus.RECOVERY_INITIATED, RecoveryEvent.EXECUTION_ERROR):
        RecoveryCaseStatus.EXECUTION_FAILED,

    # --- PAYMENT_PENDING ---
    # PAYMENT_CONFIRMED is a domain event → leads to PARTIALLY or FULLY recovered
    # The target is determined by guard evaluation in _resolve_payment_confirmed()
    (RecoveryCaseStatus.PAYMENT_PENDING, RecoveryEvent.PAYMENT_CONFIRMED):
        RecoveryCaseStatus.FULLY_RECOVERED,  # default; overridden by guard logic
    (RecoveryCaseStatus.PAYMENT_PENDING, RecoveryEvent.PAYMENT_FAILED):
        RecoveryCaseStatus.EXECUTION_FAILED,

    # --- PARTIALLY_RECOVERED ---
    (RecoveryCaseStatus.PARTIALLY_RECOVERED, RecoveryEvent.INITIATE_REMAINING_RECOVERY):
        RecoveryCaseStatus.RESOLUTION_READY,
    (RecoveryCaseStatus.PARTIALLY_RECOVERED, RecoveryEvent.PAYMENT_CONFIRMED):
        RecoveryCaseStatus.FULLY_RECOVERED,  # default; overridden by guard logic
    (RecoveryCaseStatus.PARTIALLY_RECOVERED, RecoveryEvent.REVIEW_COMPLETED):
        RecoveryCaseStatus.HUMAN_REVIEW,
    (RecoveryCaseStatus.PARTIALLY_RECOVERED, RecoveryEvent.CASE_CLOSED):
        RecoveryCaseStatus.CLOSED,

    # --- FULLY_RECOVERED ---
    (RecoveryCaseStatus.FULLY_RECOVERED, RecoveryEvent.CASE_CLOSED):
        RecoveryCaseStatus.CLOSED,

    # --- HUMAN_REVIEW ---
    (RecoveryCaseStatus.HUMAN_REVIEW, RecoveryEvent.HUMAN_APPROVAL_GRANTED):
        RecoveryCaseStatus.RECOVERY_INITIATED,
    (RecoveryCaseStatus.HUMAN_REVIEW, RecoveryEvent.REVIEW_BACK_TO_RESOLUTION):
        RecoveryCaseStatus.RESOLUTION_READY,
    (RecoveryCaseStatus.HUMAN_REVIEW, RecoveryEvent.REVIEW_BACK_TO_POLICY):
        RecoveryCaseStatus.POLICY_REVIEW,
    (RecoveryCaseStatus.HUMAN_REVIEW, RecoveryEvent.REVIEW_ESCALATE_LEGAL):
        RecoveryCaseStatus.LEGAL_ESCALATION,
    (RecoveryCaseStatus.HUMAN_REVIEW, RecoveryEvent.REVIEW_CLOSED):
        RecoveryCaseStatus.CLOSED,

    # --- LEGAL_ESCALATION ---
    (RecoveryCaseStatus.LEGAL_ESCALATION, RecoveryEvent.LEGAL_CLOSED):
        RecoveryCaseStatus.CLOSED,

    # --- AUTOMATION_LOCKED ---
    (RecoveryCaseStatus.AUTOMATION_LOCKED, RecoveryEvent.LOCK_RELEASED):
        RecoveryCaseStatus.HUMAN_REVIEW,
    (RecoveryCaseStatus.AUTOMATION_LOCKED, RecoveryEvent.LOCK_ESCALATE_LEGAL):
        RecoveryCaseStatus.LEGAL_ESCALATION,

    # --- EXECUTION_FAILED ---
    (RecoveryCaseStatus.EXECUTION_FAILED, RecoveryEvent.RETRY_APPROVED):
        RecoveryCaseStatus.RECOVERY_INITIATED,
    (RecoveryCaseStatus.EXECUTION_FAILED, RecoveryEvent.RETRY_EXHAUSTED):
        RecoveryCaseStatus.HUMAN_REVIEW,
    (RecoveryCaseStatus.EXECUTION_FAILED, RecoveryEvent.CASE_CLOSED):
        RecoveryCaseStatus.CLOSED,

    # --- CLOSED --- (terminal: no exits)
}


# ---------------------------------------------------------------------------
# Safety interrupt transitions — these override normal transitions
# ---------------------------------------------------------------------------

_SAFETY_INTERRUPTS: dict[
    RecoveryEvent,
    RecoveryCaseStatus,
] = {
    RecoveryEvent.LEGAL_RISK_DETECTED: RecoveryCaseStatus.AUTOMATION_LOCKED,
    RecoveryEvent.MANUAL_LOCK: RecoveryCaseStatus.AUTOMATION_LOCKED,
    RecoveryEvent.SYSTEM_INTEGRITY_FAILURE: RecoveryCaseStatus.AUTOMATION_LOCKED,
}


# ---------------------------------------------------------------------------
# State Machine Service
# ---------------------------------------------------------------------------

class StateMachineService:
    """Deterministic Recovery Case State Machine.

    Pure function-oriented service. Does not mutate database state.
    Does not call any AI/LLM. Does not call Razorpay or any external service.
    Does not calculate financial amounts.

    Usage:
        service = StateMachineService()
        result = service.transition(current_state, event, context)
    """

    def transition(
        self,
        current_state: RecoveryCaseStatus,
        event: RecoveryEvent,
        context: TransitionContext | None = None,
    ) -> TransitionResult:
        """Attempt a state transition.

        Args:
            current_state: The current RecoveryCaseStatus.
            event: The domain event triggering the transition.
            context: Optional transition context with guard values.

        Returns:
            TransitionResult with allowed=True on success.

        Raises:
            InvalidTransitionError: If the transition is not allowed.
            TransitionGuardError: If a required guard condition is not met.
        """
        if context is None:
            context = TransitionContext()

        # 1. Check terminal state
        if current_state in TERMINAL_STATES:
            raise InvalidTransitionError(
                current_state,
                event,
                f"State {current_state} is terminal; no transitions allowed",
            )

        # 2. Check safety interrupts (highest priority)
        if event in _SAFETY_INTERRUPTS:
            return self._handle_safety_interrupt(current_state, event, context)

        # 3. Look up transition in table
        key = (current_state, event)
        if key not in _TRANSITION_TABLE:
            raise InvalidTransitionError(
                current_state,
                event,
                f"No valid transition from {current_state} on event {event}",
            )

        target_state = _TRANSITION_TABLE[key]

        # 4. Apply guard logic
        target_state = self._evaluate_guards(
            current_state, event, target_state, context
        )

        # 5. Build successful result
        return TransitionResult(
            allowed=True,
            state_before=current_state,
            state_after=target_state,
            event=event,
            reason=self._build_reason(current_state, event, target_state, context),
            event_id=context.event_id,
            metadata=context.metadata,
        )

    def validate_transition(
        self,
        current_state: RecoveryCaseStatus,
        event: RecoveryEvent,
        context: TransitionContext | None = None,
    ) -> TransitionResult:
        """Check if a transition would be allowed, without raising exceptions.

        Returns a TransitionResult with allowed=False on failure instead of
        raising an exception. Useful for validation checks.
        """
        try:
            return self.transition(current_state, event, context)
        except (InvalidTransitionError, TransitionGuardError) as exc:
            return TransitionResult(
                allowed=False,
                state_before=current_state,
                state_after=current_state,  # No change
                event=event,
                reason=str(exc),
                event_id=context.event_id if context else None,
                metadata=context.metadata if context else {},
            )

    def get_allowed_events(
        self,
        current_state: RecoveryCaseStatus,
    ) -> list[RecoveryEvent]:
        """Return all events that have a defined transition from current_state.

        Does not evaluate guards — returns structurally valid events only.
        """
        if current_state in TERMINAL_STATES:
            return []

        events: list[RecoveryEvent] = []
        for (state, event), _target in _TRANSITION_TABLE.items():
            if state == current_state:
                events.append(event)

        # Safety interrupts are always available for interruptible states
        if current_state in SAFETY_INTERRUPTIBLE_STATES:
            for safety_event in _SAFETY_INTERRUPTS:
                if safety_event == RecoveryEvent.SYSTEM_INTEGRITY_FAILURE:
                    # Only for financial execution states
                    if current_state in FINANCIAL_EXECUTION_STATES:
                        events.append(safety_event)
                else:
                    events.append(safety_event)

        return events

    # -------------------------------------------------------------------
    # Internal guard evaluation
    # -------------------------------------------------------------------

    def _evaluate_guards(
        self,
        current_state: RecoveryCaseStatus,
        event: RecoveryEvent,
        target_state: RecoveryCaseStatus,
        context: TransitionContext,
    ) -> RecoveryCaseStatus:
        """Evaluate transition guards and return the (possibly adjusted) target state.

        Raises TransitionGuardError if a mandatory guard fails.
        """
        # Guard: automation-locked cases cannot enter autonomous recovery
        if context.is_automation_locked and target_state in {
            RecoveryCaseStatus.RECOVERY_INITIATED,
            RecoveryCaseStatus.PAYMENT_PENDING,
        }:
            raise TransitionGuardError(
                current_state,
                event,
                "automation_lock",
                "Case is automation locked; cannot enter autonomous recovery",
            )

        # Guard: legal-locked cases cannot enter autonomous recovery
        if context.is_legal_locked and target_state in {
            RecoveryCaseStatus.RECOVERY_INITIATED,
            RecoveryCaseStatus.PAYMENT_PENDING,
        }:
            raise TransitionGuardError(
                current_state,
                event,
                "legal_lock",
                "Case has legal lock; cannot enter autonomous recovery",
            )

        # Guard: POLICY_APPROVED requires valid guards
        if event == RecoveryEvent.POLICY_APPROVED:
            self._guard_policy_approved(current_state, event, context)

        # Guard: HUMAN_APPROVAL_GRANTED requires valid approval
        if event == RecoveryEvent.HUMAN_APPROVAL_GRANTED:
            self._guard_human_approval(current_state, event, context)

        # Guard: PAYMENT_CONFIRMED requires verified payment
        if event == RecoveryEvent.PAYMENT_CONFIRMED:
            target_state = self._guard_payment_confirmed(
                current_state, event, context
            )

        # Guard: RETRY_APPROVED must check retry bounds
        if event == RecoveryEvent.RETRY_APPROVED:
            self._guard_retry(current_state, event, context)

        return target_state

    def _guard_policy_approved(
        self,
        current_state: RecoveryCaseStatus,
        event: RecoveryEvent,
        context: TransitionContext,
    ) -> None:
        """Guards for POLICY_APPROVED → RECOVERY_INITIATED."""
        if not context.has_valid_proposal:
            raise TransitionGuardError(
                current_state, event,
                "valid_proposal",
                "No valid proposal exists for policy approval",
            )
        if not context.has_valid_financial_assessment:
            raise TransitionGuardError(
                current_state, event,
                "valid_financial_assessment",
                "Financial assessment is missing or stale",
            )
        if context.is_legal_locked:
            raise TransitionGuardError(
                current_state, event,
                "legal_lock",
                "Case has legal lock; policy approval cannot proceed",
            )

    def _guard_human_approval(
        self,
        current_state: RecoveryCaseStatus,
        event: RecoveryEvent,
        context: TransitionContext,
    ) -> None:
        """Guards for HUMAN_APPROVAL_GRANTED → RECOVERY_INITIATED."""
        if not context.has_valid_human_approval:
            raise TransitionGuardError(
                current_state, event,
                "valid_human_approval",
                "No valid human approval exists for this action",
            )
        if not context.has_valid_financial_assessment:
            raise TransitionGuardError(
                current_state, event,
                "valid_financial_assessment",
                "Financial assessment is missing or stale",
            )
        if context.is_legal_locked:
            raise TransitionGuardError(
                current_state, event,
                "legal_lock",
                "Case has legal lock; human approval cannot authorize recovery",
            )

    def _guard_payment_confirmed(
        self,
        current_state: RecoveryCaseStatus,
        event: RecoveryEvent,
        context: TransitionContext,
    ) -> RecoveryCaseStatus:
        """Guards for PAYMENT_CONFIRMED event.

        PAYMENT_CONFIRMED is a verified domain event, not a state.
        The post-payment state depends on verified payment/reconciliation data.

        Returns the correct target state (PARTIALLY_RECOVERED or FULLY_RECOVERED).
        """
        if not context.payment_verified:
            raise TransitionGuardError(
                current_state, event,
                "payment_verified",
                "Payment has not been verified through external payment evidence",
            )

        if context.verified_recovered_amount is None:
            raise TransitionGuardError(
                current_state, event,
                "verified_recovered_amount",
                "Verified recovered amount is required for payment confirmation",
            )

        if context.applicable_recoverable_balance is None:
            raise TransitionGuardError(
                current_state, event,
                "applicable_recoverable_balance",
                "Applicable recoverable balance is required for payment confirmation",
            )

        if context.verified_recovered_amount <= 0:
            raise TransitionGuardError(
                current_state, event,
                "positive_recovery",
                "Verified recovered amount must be positive",
            )

        # Determine target: partial vs full recovery
        if context.verified_recovered_amount >= context.applicable_recoverable_balance:
            return RecoveryCaseStatus.FULLY_RECOVERED
        else:
            return RecoveryCaseStatus.PARTIALLY_RECOVERED

    def _guard_retry(
        self,
        current_state: RecoveryCaseStatus,
        event: RecoveryEvent,
        context: TransitionContext,
    ) -> None:
        """Guards for RETRY_APPROVED in EXECUTION_FAILED state."""
        if context.retry_count >= context.max_retries:
            raise TransitionGuardError(
                current_state, event,
                "retry_limit",
                f"Retry count ({context.retry_count}) has reached or exceeded "
                f"maximum ({context.max_retries})",
            )

    # -------------------------------------------------------------------
    # Safety interrupt handling
    # -------------------------------------------------------------------

    def _handle_safety_interrupt(
        self,
        current_state: RecoveryCaseStatus,
        event: RecoveryEvent,
        context: TransitionContext,
    ) -> TransitionResult:
        """Handle safety interrupt events.

        Safety interrupts have priority over ordinary recovery transitions.
        They apply to all active (non-terminal, non-locked) states.
        SYSTEM_INTEGRITY_FAILURE is restricted to financial execution states.
        """
        target_state = _SAFETY_INTERRUPTS[event]

        # Already in the target locked state — idempotent
        if current_state == target_state:
            return TransitionResult(
                allowed=True,
                state_before=current_state,
                state_after=current_state,
                event=event,
                reason=f"Case already in {current_state}; safety interrupt is idempotent",
                event_id=context.event_id,
                metadata=context.metadata,
            )

        # CLOSED cannot be interrupted
        if current_state in TERMINAL_STATES:
            raise InvalidTransitionError(
                current_state,
                event,
                f"State {current_state} is terminal; safety interrupt cannot apply",
            )

        # LEGAL_ESCALATION cannot be further interrupted to AUTOMATION_LOCKED
        if current_state == RecoveryCaseStatus.LEGAL_ESCALATION:
            raise InvalidTransitionError(
                current_state,
                event,
                "LEGAL_ESCALATION already provides maximum safety handling",
            )

        # SYSTEM_INTEGRITY_FAILURE only applies to financial execution states
        if event == RecoveryEvent.SYSTEM_INTEGRITY_FAILURE:
            if current_state not in FINANCIAL_EXECUTION_STATES:
                raise InvalidTransitionError(
                    current_state,
                    event,
                    f"SYSTEM_INTEGRITY_FAILURE only applies to financial execution "
                    f"states {sorted(s.value for s in FINANCIAL_EXECUTION_STATES)}, "
                    f"not {current_state}",
                )

        return TransitionResult(
            allowed=True,
            state_before=current_state,
            state_after=target_state,
            event=event,
            reason=f"Safety interrupt: {event} applied from {current_state}",
            event_id=context.event_id,
            metadata=context.metadata,
        )

    # -------------------------------------------------------------------
    # Reason builder
    # -------------------------------------------------------------------

    @staticmethod
    def _build_reason(
        current_state: RecoveryCaseStatus,
        event: RecoveryEvent,
        target_state: RecoveryCaseStatus,
        context: TransitionContext,
    ) -> str:
        """Build a human-readable reason string for the transition."""
        reason_parts = [f"Transition {current_state} → {target_state} on {event}"]

        if event == RecoveryEvent.POLICY_APPROVED:
            reason_parts.append("Policy approved and all execution guards passed")
        elif event == RecoveryEvent.HUMAN_APPROVAL_REQUIRED:
            reason_parts.append("Policy requires human approval before execution")
        elif event == RecoveryEvent.POLICY_DEFERRED:
            reason_parts.append("Policy deferred; returning to resolution")
        elif event == RecoveryEvent.POLICY_BLOCKED:
            reason_parts.append("Policy blocked; requires human review")
        elif event == RecoveryEvent.POLICY_STOPPED:
            reason_parts.append("Policy stopped; automation locked")
        elif event == RecoveryEvent.PAYMENT_CONFIRMED:
            if target_state == RecoveryCaseStatus.FULLY_RECOVERED:
                reason_parts.append("Verified payment satisfies recoverable balance")
            else:
                reason_parts.append(
                    "Verified payment received; remaining balance unresolved"
                )
        elif event == RecoveryEvent.EVIDENCE_INSUFFICIENT:
            reason_parts.append("Evidence insufficient for safe recovery decision")
        elif event == RecoveryEvent.EVIDENCE_CONFLICT:
            reason_parts.append("Material evidence conflicts detected")

        return "; ".join(reason_parts)
