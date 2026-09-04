"""Comprehensive tests for the deterministic Recovery Case State Machine.

Covers:
  - Valid happy path transitions
  - Invalid transitions
  - Illegal jumps (e.g., OVERDUE → FULLY_RECOVERED)
  - Required event/condition enforcement
  - All five POLICY_REVIEW outcomes
  - PAYMENT_PENDING cannot become recovered without verified payment
  - PAYMENT_CONFIRMED is an event, not a state
  - Partial vs full recovery
  - Legal escalation
  - Automation lock
  - Execution failure/retry
  - CLOSED behavior (terminal)
  - Missing/invalid transition conditions fail closed
  - No AI/Razorpay dependencies
  - No duplicated financial arithmetic
"""

import pytest

from app.domain.enums import RecoveryCaseStatus
from app.services.state_machine import (
    FINANCIAL_EXECUTION_STATES,
    TERMINAL_STATES,
    InvalidTransitionError,
    RecoveryEvent,
    StateMachineService,
    TransitionContext,
    TransitionGuardError,
    TransitionResult,
)


@pytest.fixture
def sm() -> StateMachineService:
    """Provide a fresh StateMachineService instance."""
    return StateMachineService()


# =========================================================================
# 1. Happy path: canonical full-recovery path
# =========================================================================

class TestHappyPath:
    """Full happy-path traversal: OVERDUE → … → CLOSED."""

    def test_full_happy_path(self, sm: StateMachineService) -> None:
        """Walk the canonical autonomous full-recovery path end-to-end."""
        steps: list[tuple[RecoveryCaseStatus, RecoveryEvent, TransitionContext | None]] = [
            (
                RecoveryCaseStatus.OVERDUE,
                RecoveryEvent.START_TRIAGE,
                None,
            ),
            (
                RecoveryCaseStatus.TRIAGING,
                RecoveryEvent.TRIAGE_COMPLETED,
                None,
            ),
            (
                RecoveryCaseStatus.ISSUE_IDENTIFIED,
                RecoveryEvent.START_EVIDENCE_ANALYSIS,
                None,
            ),
            (
                RecoveryCaseStatus.EVIDENCE_ANALYSIS,
                RecoveryEvent.EVIDENCE_SUFFICIENT,
                None,
            ),
            (
                RecoveryCaseStatus.RESOLUTION_READY,
                RecoveryEvent.SUBMIT_RESOLUTION_FOR_POLICY,
                None,
            ),
            (
                RecoveryCaseStatus.POLICY_REVIEW,
                RecoveryEvent.POLICY_APPROVED,
                TransitionContext(
                    has_valid_proposal=True,
                    has_valid_financial_assessment=True,
                    is_legal_locked=False,
                ),
            ),
            (
                RecoveryCaseStatus.RECOVERY_INITIATED,
                RecoveryEvent.PAYMENT_REQUEST_CREATED,
                None,
            ),
            (
                RecoveryCaseStatus.PAYMENT_PENDING,
                RecoveryEvent.PAYMENT_CONFIRMED,
                TransitionContext(
                    payment_verified=True,
                    verified_recovered_amount=900_000_00,  # ₹9,00,000 in paise
                    applicable_recoverable_balance=900_000_00,
                ),
            ),
            (
                RecoveryCaseStatus.FULLY_RECOVERED,
                RecoveryEvent.CASE_CLOSED,
                None,
            ),
        ]

        expected_states = [
            RecoveryCaseStatus.TRIAGING,
            RecoveryCaseStatus.ISSUE_IDENTIFIED,
            RecoveryCaseStatus.EVIDENCE_ANALYSIS,
            RecoveryCaseStatus.RESOLUTION_READY,
            RecoveryCaseStatus.POLICY_REVIEW,
            RecoveryCaseStatus.RECOVERY_INITIATED,
            RecoveryCaseStatus.PAYMENT_PENDING,
            RecoveryCaseStatus.FULLY_RECOVERED,
            RecoveryCaseStatus.CLOSED,
        ]

        for i, (state, event, ctx) in enumerate(steps):
            result = sm.transition(state, event, ctx)
            assert result.allowed is True
            assert result.state_before == state
            assert result.state_after == expected_states[i]
            assert result.event == event

    def test_overdue_to_triaging(self, sm: StateMachineService) -> None:
        result = sm.transition(RecoveryCaseStatus.OVERDUE, RecoveryEvent.START_TRIAGE)
        assert result.allowed is True
        assert result.state_after == RecoveryCaseStatus.TRIAGING

    def test_triaging_to_issue_identified(self, sm: StateMachineService) -> None:
        result = sm.transition(RecoveryCaseStatus.TRIAGING, RecoveryEvent.TRIAGE_COMPLETED)
        assert result.allowed is True
        assert result.state_after == RecoveryCaseStatus.ISSUE_IDENTIFIED

    def test_issue_identified_to_evidence_analysis(self, sm: StateMachineService) -> None:
        result = sm.transition(
            RecoveryCaseStatus.ISSUE_IDENTIFIED, RecoveryEvent.START_EVIDENCE_ANALYSIS
        )
        assert result.allowed is True
        assert result.state_after == RecoveryCaseStatus.EVIDENCE_ANALYSIS

    def test_evidence_sufficient_to_resolution_ready(self, sm: StateMachineService) -> None:
        result = sm.transition(
            RecoveryCaseStatus.EVIDENCE_ANALYSIS, RecoveryEvent.EVIDENCE_SUFFICIENT
        )
        assert result.allowed is True
        assert result.state_after == RecoveryCaseStatus.RESOLUTION_READY


# =========================================================================
# 2. Invalid transitions
# =========================================================================

class TestInvalidTransitions:
    """Verify that invalid/illegal transitions are rejected."""

    def test_overdue_to_fully_recovered_is_illegal(self, sm: StateMachineService) -> None:
        """Critical: cannot skip the entire workflow."""
        with pytest.raises(InvalidTransitionError):
            sm.transition(
                RecoveryCaseStatus.OVERDUE,
                RecoveryEvent.PAYMENT_CONFIRMED,
                TransitionContext(
                    payment_verified=True,
                    verified_recovered_amount=1_000_000_00,
                    applicable_recoverable_balance=1_000_000_00,
                ),
            )

    def test_triaging_to_payment_pending_is_illegal(self, sm: StateMachineService) -> None:
        with pytest.raises(InvalidTransitionError):
            sm.transition(
                RecoveryCaseStatus.TRIAGING, RecoveryEvent.PAYMENT_REQUEST_CREATED
            )

    def test_evidence_analysis_to_payment_confirmed_is_illegal(
        self, sm: StateMachineService
    ) -> None:
        with pytest.raises(InvalidTransitionError):
            sm.transition(
                RecoveryCaseStatus.EVIDENCE_ANALYSIS,
                RecoveryEvent.PAYMENT_CONFIRMED,
                TransitionContext(
                    payment_verified=True,
                    verified_recovered_amount=1_000_00,
                    applicable_recoverable_balance=1_000_00,
                ),
            )

    def test_legal_escalation_to_recovery_initiated_is_illegal(
        self, sm: StateMachineService
    ) -> None:
        with pytest.raises(InvalidTransitionError):
            sm.transition(
                RecoveryCaseStatus.LEGAL_ESCALATION, RecoveryEvent.POLICY_APPROVED
            )

    def test_automation_locked_to_payment_pending_is_illegal(
        self, sm: StateMachineService
    ) -> None:
        with pytest.raises(InvalidTransitionError):
            sm.transition(
                RecoveryCaseStatus.AUTOMATION_LOCKED,
                RecoveryEvent.PAYMENT_REQUEST_CREATED,
            )

    def test_cannot_skip_evidence(self, sm: StateMachineService) -> None:
        """Cannot go OVERDUE → RESOLUTION_READY."""
        with pytest.raises(InvalidTransitionError):
            sm.transition(
                RecoveryCaseStatus.OVERDUE, RecoveryEvent.EVIDENCE_SUFFICIENT
            )

    def test_cannot_skip_policy(self, sm: StateMachineService) -> None:
        """Cannot go RESOLUTION_READY → RECOVERY_INITIATED directly without policy."""
        with pytest.raises(InvalidTransitionError):
            sm.transition(
                RecoveryCaseStatus.RESOLUTION_READY, RecoveryEvent.POLICY_APPROVED
            )

    def test_overdue_direct_close_is_illegal(self, sm: StateMachineService) -> None:
        with pytest.raises(InvalidTransitionError):
            sm.transition(RecoveryCaseStatus.OVERDUE, RecoveryEvent.CASE_CLOSED)


# =========================================================================
# 3. POLICY_REVIEW — all five outcomes
# =========================================================================

class TestPolicyReviewOutcomes:
    """Test all five POLICY_REVIEW outcomes as specified."""

    def test_policy_approved_to_recovery_initiated(self, sm: StateMachineService) -> None:
        ctx = TransitionContext(
            has_valid_proposal=True,
            has_valid_financial_assessment=True,
            is_legal_locked=False,
        )
        result = sm.transition(RecoveryCaseStatus.POLICY_REVIEW, RecoveryEvent.POLICY_APPROVED, ctx)
        assert result.allowed is True
        assert result.state_after == RecoveryCaseStatus.RECOVERY_INITIATED

    def test_human_approval_required_to_human_review(self, sm: StateMachineService) -> None:
        """Canonical case: ₹9,00,000 collectible, policy HUMAN_APPROVAL_REQUIRED."""
        result = sm.transition(
            RecoveryCaseStatus.POLICY_REVIEW, RecoveryEvent.HUMAN_APPROVAL_REQUIRED
        )
        assert result.allowed is True
        assert result.state_after == RecoveryCaseStatus.HUMAN_REVIEW

    def test_policy_deferred_to_resolution_ready(self, sm: StateMachineService) -> None:
        result = sm.transition(
            RecoveryCaseStatus.POLICY_REVIEW, RecoveryEvent.POLICY_DEFERRED
        )
        assert result.allowed is True
        assert result.state_after == RecoveryCaseStatus.RESOLUTION_READY

    def test_policy_blocked_to_human_review(self, sm: StateMachineService) -> None:
        result = sm.transition(
            RecoveryCaseStatus.POLICY_REVIEW, RecoveryEvent.POLICY_BLOCKED
        )
        assert result.allowed is True
        assert result.state_after == RecoveryCaseStatus.HUMAN_REVIEW

    def test_policy_stopped_to_automation_locked(self, sm: StateMachineService) -> None:
        result = sm.transition(
            RecoveryCaseStatus.POLICY_REVIEW, RecoveryEvent.POLICY_STOPPED
        )
        assert result.allowed is True
        assert result.state_after == RecoveryCaseStatus.AUTOMATION_LOCKED

    def test_canonical_case_high_value_requires_human_approval(
        self, sm: StateMachineService
    ) -> None:
        """₹10L invoice, ₹1L dispute, ₹9L collectible → policy: HUMAN_APPROVAL_REQUIRED.

        The State Machine does NOT apply the ₹5L authority limit.
        It receives HUMAN_APPROVAL_REQUIRED as an event and transitions to HUMAN_REVIEW.
        """
        result = sm.transition(
            RecoveryCaseStatus.POLICY_REVIEW,
            RecoveryEvent.HUMAN_APPROVAL_REQUIRED,
        )
        assert result.allowed is True
        assert result.state_after == RecoveryCaseStatus.HUMAN_REVIEW


# =========================================================================
# 4. Payment rules
# =========================================================================

class TestPaymentRules:
    """Payment verification and state rules."""

    def test_payment_pending_is_not_recovered(self, sm: StateMachineService) -> None:
        """PAYMENT_PENDING cannot become recovered without verified payment."""
        with pytest.raises(TransitionGuardError, match="payment_verified"):
            sm.transition(
                RecoveryCaseStatus.PAYMENT_PENDING,
                RecoveryEvent.PAYMENT_CONFIRMED,
                TransitionContext(payment_verified=False),
            )

    def test_payment_confirmed_without_verification_fails(
        self, sm: StateMachineService
    ) -> None:
        """Default context (no verification) must fail closed."""
        with pytest.raises(TransitionGuardError, match="payment_verified"):
            sm.transition(
                RecoveryCaseStatus.PAYMENT_PENDING,
                RecoveryEvent.PAYMENT_CONFIRMED,
            )

    def test_payment_confirmed_is_event_not_state(self) -> None:
        """PAYMENT_CONFIRMED must not exist as a RecoveryCaseStatus."""
        all_statuses = [s.value for s in RecoveryCaseStatus]
        assert "PAYMENT_CONFIRMED" not in all_statuses

    def test_payment_confirmed_requires_verified_amount(
        self, sm: StateMachineService
    ) -> None:
        with pytest.raises(TransitionGuardError, match="verified_recovered_amount"):
            sm.transition(
                RecoveryCaseStatus.PAYMENT_PENDING,
                RecoveryEvent.PAYMENT_CONFIRMED,
                TransitionContext(
                    payment_verified=True,
                    verified_recovered_amount=None,
                    applicable_recoverable_balance=1_000_00,
                ),
            )

    def test_payment_confirmed_requires_recoverable_balance(
        self, sm: StateMachineService
    ) -> None:
        with pytest.raises(TransitionGuardError, match="applicable_recoverable_balance"):
            sm.transition(
                RecoveryCaseStatus.PAYMENT_PENDING,
                RecoveryEvent.PAYMENT_CONFIRMED,
                TransitionContext(
                    payment_verified=True,
                    verified_recovered_amount=1_000_00,
                    applicable_recoverable_balance=None,
                ),
            )

    def test_payment_confirmed_zero_amount_fails(self, sm: StateMachineService) -> None:
        with pytest.raises(TransitionGuardError, match="positive_recovery"):
            sm.transition(
                RecoveryCaseStatus.PAYMENT_PENDING,
                RecoveryEvent.PAYMENT_CONFIRMED,
                TransitionContext(
                    payment_verified=True,
                    verified_recovered_amount=0,
                    applicable_recoverable_balance=1_000_00,
                ),
            )

    def test_payment_failed_to_execution_failed(self, sm: StateMachineService) -> None:
        result = sm.transition(
            RecoveryCaseStatus.PAYMENT_PENDING, RecoveryEvent.PAYMENT_FAILED
        )
        assert result.allowed is True
        assert result.state_after == RecoveryCaseStatus.EXECUTION_FAILED


# =========================================================================
# 5. Partial vs full recovery
# =========================================================================

class TestPartialVsFullRecovery:
    """Verify correct determination of PARTIALLY_RECOVERED vs FULLY_RECOVERED."""

    def test_full_recovery_when_amount_equals_balance(
        self, sm: StateMachineService
    ) -> None:
        result = sm.transition(
            RecoveryCaseStatus.PAYMENT_PENDING,
            RecoveryEvent.PAYMENT_CONFIRMED,
            TransitionContext(
                payment_verified=True,
                verified_recovered_amount=900_000_00,
                applicable_recoverable_balance=900_000_00,
            ),
        )
        assert result.state_after == RecoveryCaseStatus.FULLY_RECOVERED

    def test_full_recovery_when_amount_exceeds_balance(
        self, sm: StateMachineService
    ) -> None:
        """Edge case: overpayment still counts as fully recovered."""
        result = sm.transition(
            RecoveryCaseStatus.PAYMENT_PENDING,
            RecoveryEvent.PAYMENT_CONFIRMED,
            TransitionContext(
                payment_verified=True,
                verified_recovered_amount=1_000_000_00,
                applicable_recoverable_balance=900_000_00,
            ),
        )
        assert result.state_after == RecoveryCaseStatus.FULLY_RECOVERED

    def test_partial_recovery_when_amount_less_than_balance(
        self, sm: StateMachineService
    ) -> None:
        result = sm.transition(
            RecoveryCaseStatus.PAYMENT_PENDING,
            RecoveryEvent.PAYMENT_CONFIRMED,
            TransitionContext(
                payment_verified=True,
                verified_recovered_amount=500_000_00,
                applicable_recoverable_balance=900_000_00,
            ),
        )
        assert result.state_after == RecoveryCaseStatus.PARTIALLY_RECOVERED

    def test_partially_recovered_can_become_fully_recovered(
        self, sm: StateMachineService
    ) -> None:
        """Additional payment on a partially recovered case."""
        result = sm.transition(
            RecoveryCaseStatus.PARTIALLY_RECOVERED,
            RecoveryEvent.PAYMENT_CONFIRMED,
            TransitionContext(
                payment_verified=True,
                verified_recovered_amount=900_000_00,  # now full
                applicable_recoverable_balance=900_000_00,
            ),
        )
        assert result.state_after == RecoveryCaseStatus.FULLY_RECOVERED

    def test_partially_recovered_can_initiate_remaining_recovery(
        self, sm: StateMachineService
    ) -> None:
        result = sm.transition(
            RecoveryCaseStatus.PARTIALLY_RECOVERED,
            RecoveryEvent.INITIATE_REMAINING_RECOVERY,
        )
        assert result.state_after == RecoveryCaseStatus.RESOLUTION_READY

    def test_partially_recovered_can_close(self, sm: StateMachineService) -> None:
        result = sm.transition(
            RecoveryCaseStatus.PARTIALLY_RECOVERED, RecoveryEvent.CASE_CLOSED
        )
        assert result.state_after == RecoveryCaseStatus.CLOSED


# =========================================================================
# 6. Legal escalation
# =========================================================================

class TestLegalEscalation:
    """Legal escalation and related safety behavior."""

    def test_legal_risk_detected_from_evidence_analysis(
        self, sm: StateMachineService
    ) -> None:
        result = sm.transition(
            RecoveryCaseStatus.EVIDENCE_ANALYSIS, RecoveryEvent.LEGAL_RISK_DETECTED
        )
        assert result.allowed is True
        assert result.state_after == RecoveryCaseStatus.AUTOMATION_LOCKED

    def test_legal_risk_from_overdue(self, sm: StateMachineService) -> None:
        result = sm.transition(
            RecoveryCaseStatus.OVERDUE, RecoveryEvent.LEGAL_RISK_DETECTED
        )
        assert result.state_after == RecoveryCaseStatus.AUTOMATION_LOCKED

    def test_legal_risk_from_triaging(self, sm: StateMachineService) -> None:
        result = sm.transition(
            RecoveryCaseStatus.TRIAGING, RecoveryEvent.LEGAL_RISK_DETECTED
        )
        assert result.state_after == RecoveryCaseStatus.AUTOMATION_LOCKED

    def test_automation_locked_to_legal_escalation(self, sm: StateMachineService) -> None:
        result = sm.transition(
            RecoveryCaseStatus.AUTOMATION_LOCKED, RecoveryEvent.LOCK_ESCALATE_LEGAL
        )
        assert result.state_after == RecoveryCaseStatus.LEGAL_ESCALATION

    def test_legal_escalation_to_closed(self, sm: StateMachineService) -> None:
        result = sm.transition(
            RecoveryCaseStatus.LEGAL_ESCALATION, RecoveryEvent.LEGAL_CLOSED
        )
        assert result.state_after == RecoveryCaseStatus.CLOSED

    def test_legal_escalation_cannot_go_to_recovery(
        self, sm: StateMachineService
    ) -> None:
        with pytest.raises(InvalidTransitionError):
            sm.transition(
                RecoveryCaseStatus.LEGAL_ESCALATION, RecoveryEvent.POLICY_APPROVED
            )

    def test_legal_escalation_cannot_be_safety_interrupted(
        self, sm: StateMachineService
    ) -> None:
        """LEGAL_ESCALATION already provides maximum safety handling."""
        with pytest.raises(InvalidTransitionError):
            sm.transition(
                RecoveryCaseStatus.LEGAL_ESCALATION, RecoveryEvent.LEGAL_RISK_DETECTED
            )

    def test_human_review_to_legal_escalation(self, sm: StateMachineService) -> None:
        result = sm.transition(
            RecoveryCaseStatus.HUMAN_REVIEW, RecoveryEvent.REVIEW_ESCALATE_LEGAL
        )
        assert result.state_after == RecoveryCaseStatus.LEGAL_ESCALATION


# =========================================================================
# 7. Automation lock
# =========================================================================

class TestAutomationLock:
    """AUTOMATION_LOCKED prevents autonomous recovery."""

    def test_manual_lock_from_active_state(self, sm: StateMachineService) -> None:
        result = sm.transition(
            RecoveryCaseStatus.RECOVERY_INITIATED, RecoveryEvent.MANUAL_LOCK
        )
        assert result.state_after == RecoveryCaseStatus.AUTOMATION_LOCKED

    def test_automation_locked_cannot_start_recovery(
        self, sm: StateMachineService
    ) -> None:
        with pytest.raises(InvalidTransitionError):
            sm.transition(
                RecoveryCaseStatus.AUTOMATION_LOCKED,
                RecoveryEvent.POLICY_APPROVED,
            )

    def test_automation_locked_can_release_to_human_review(
        self, sm: StateMachineService
    ) -> None:
        result = sm.transition(
            RecoveryCaseStatus.AUTOMATION_LOCKED, RecoveryEvent.LOCK_RELEASED
        )
        assert result.state_after == RecoveryCaseStatus.HUMAN_REVIEW

    def test_automation_locked_idempotent_lock(self, sm: StateMachineService) -> None:
        """Applying MANUAL_LOCK when already locked is idempotent."""
        result = sm.transition(
            RecoveryCaseStatus.AUTOMATION_LOCKED, RecoveryEvent.MANUAL_LOCK
        )
        assert result.allowed is True
        assert result.state_after == RecoveryCaseStatus.AUTOMATION_LOCKED

    def test_legal_lock_blocks_policy_approved(self, sm: StateMachineService) -> None:
        """Legal lock must prevent POLICY_APPROVED → RECOVERY_INITIATED."""
        with pytest.raises(TransitionGuardError, match="legal_lock"):
            sm.transition(
                RecoveryCaseStatus.POLICY_REVIEW,
                RecoveryEvent.POLICY_APPROVED,
                TransitionContext(
                    has_valid_proposal=True,
                    has_valid_financial_assessment=True,
                    is_legal_locked=True,
                ),
            )

    def test_automation_lock_blocks_human_approval_execution(
        self, sm: StateMachineService
    ) -> None:
        """Automation lock must prevent HUMAN_REVIEW → RECOVERY_INITIATED."""
        with pytest.raises(TransitionGuardError, match="automation_lock"):
            sm.transition(
                RecoveryCaseStatus.HUMAN_REVIEW,
                RecoveryEvent.HUMAN_APPROVAL_GRANTED,
                TransitionContext(
                    has_valid_human_approval=True,
                    has_valid_financial_assessment=True,
                    is_automation_locked=True,
                ),
            )

    def test_system_integrity_failure_from_recovery_initiated(
        self, sm: StateMachineService
    ) -> None:
        result = sm.transition(
            RecoveryCaseStatus.RECOVERY_INITIATED,
            RecoveryEvent.SYSTEM_INTEGRITY_FAILURE,
        )
        assert result.state_after == RecoveryCaseStatus.AUTOMATION_LOCKED

    def test_system_integrity_failure_from_payment_pending(
        self, sm: StateMachineService
    ) -> None:
        result = sm.transition(
            RecoveryCaseStatus.PAYMENT_PENDING,
            RecoveryEvent.SYSTEM_INTEGRITY_FAILURE,
        )
        assert result.state_after == RecoveryCaseStatus.AUTOMATION_LOCKED

    def test_system_integrity_failure_from_non_financial_state_is_invalid(
        self, sm: StateMachineService
    ) -> None:
        """SYSTEM_INTEGRITY_FAILURE only applies to financial execution states."""
        with pytest.raises(InvalidTransitionError, match="financial execution"):
            sm.transition(
                RecoveryCaseStatus.TRIAGING,
                RecoveryEvent.SYSTEM_INTEGRITY_FAILURE,
            )


# =========================================================================
# 8. Execution failure / retry
# =========================================================================

class TestExecutionFailureRetry:
    """EXECUTION_FAILED retry handling."""

    def test_recovery_initiated_to_execution_failed(
        self, sm: StateMachineService
    ) -> None:
        result = sm.transition(
            RecoveryCaseStatus.RECOVERY_INITIATED, RecoveryEvent.EXECUTION_ERROR
        )
        assert result.state_after == RecoveryCaseStatus.EXECUTION_FAILED

    def test_retry_approved_within_bounds(self, sm: StateMachineService) -> None:
        result = sm.transition(
            RecoveryCaseStatus.EXECUTION_FAILED,
            RecoveryEvent.RETRY_APPROVED,
            TransitionContext(retry_count=1, max_retries=3),
        )
        assert result.state_after == RecoveryCaseStatus.RECOVERY_INITIATED

    def test_retry_approved_at_limit_fails(self, sm: StateMachineService) -> None:
        """Retries must be bounded."""
        with pytest.raises(TransitionGuardError, match="retry_limit"):
            sm.transition(
                RecoveryCaseStatus.EXECUTION_FAILED,
                RecoveryEvent.RETRY_APPROVED,
                TransitionContext(retry_count=3, max_retries=3),
            )

    def test_retry_exhausted_to_human_review(self, sm: StateMachineService) -> None:
        result = sm.transition(
            RecoveryCaseStatus.EXECUTION_FAILED, RecoveryEvent.RETRY_EXHAUSTED
        )
        assert result.state_after == RecoveryCaseStatus.HUMAN_REVIEW

    def test_execution_failed_to_closed(self, sm: StateMachineService) -> None:
        result = sm.transition(
            RecoveryCaseStatus.EXECUTION_FAILED, RecoveryEvent.CASE_CLOSED
        )
        assert result.state_after == RecoveryCaseStatus.CLOSED


# =========================================================================
# 9. CLOSED behavior — terminal state
# =========================================================================

class TestClosedBehavior:
    """CLOSED is terminal: no further transitions allowed."""

    def test_closed_is_terminal(self, sm: StateMachineService) -> None:
        with pytest.raises(InvalidTransitionError, match="terminal"):
            sm.transition(RecoveryCaseStatus.CLOSED, RecoveryEvent.START_TRIAGE)

    def test_closed_rejects_policy_approved(self, sm: StateMachineService) -> None:
        with pytest.raises(InvalidTransitionError, match="terminal"):
            sm.transition(RecoveryCaseStatus.CLOSED, RecoveryEvent.POLICY_APPROVED)

    def test_closed_rejects_case_closed(self, sm: StateMachineService) -> None:
        """Cannot close an already-closed case."""
        with pytest.raises(InvalidTransitionError, match="terminal"):
            sm.transition(RecoveryCaseStatus.CLOSED, RecoveryEvent.CASE_CLOSED)

    def test_closed_rejects_safety_interrupt(self, sm: StateMachineService) -> None:
        """Even safety interrupts cannot apply to CLOSED."""
        with pytest.raises(InvalidTransitionError, match="terminal"):
            sm.transition(
                RecoveryCaseStatus.CLOSED, RecoveryEvent.LEGAL_RISK_DETECTED
            )

    def test_closed_has_no_allowed_events(self, sm: StateMachineService) -> None:
        events = sm.get_allowed_events(RecoveryCaseStatus.CLOSED)
        assert events == []

    def test_fully_recovered_to_closed(self, sm: StateMachineService) -> None:
        result = sm.transition(
            RecoveryCaseStatus.FULLY_RECOVERED, RecoveryEvent.CASE_CLOSED
        )
        assert result.state_after == RecoveryCaseStatus.CLOSED


# =========================================================================
# 10. Guard / condition enforcement
# =========================================================================

class TestGuardEnforcement:
    """Missing or invalid transition conditions must fail closed."""

    def test_policy_approved_without_proposal_fails(
        self, sm: StateMachineService
    ) -> None:
        with pytest.raises(TransitionGuardError, match="valid_proposal"):
            sm.transition(
                RecoveryCaseStatus.POLICY_REVIEW,
                RecoveryEvent.POLICY_APPROVED,
                TransitionContext(
                    has_valid_proposal=False,
                    has_valid_financial_assessment=True,
                ),
            )

    def test_policy_approved_without_financial_assessment_fails(
        self, sm: StateMachineService
    ) -> None:
        with pytest.raises(TransitionGuardError, match="valid_financial_assessment"):
            sm.transition(
                RecoveryCaseStatus.POLICY_REVIEW,
                RecoveryEvent.POLICY_APPROVED,
                TransitionContext(
                    has_valid_proposal=True,
                    has_valid_financial_assessment=False,
                ),
            )

    def test_human_approval_without_valid_approval_fails(
        self, sm: StateMachineService
    ) -> None:
        with pytest.raises(TransitionGuardError, match="valid_human_approval"):
            sm.transition(
                RecoveryCaseStatus.HUMAN_REVIEW,
                RecoveryEvent.HUMAN_APPROVAL_GRANTED,
                TransitionContext(
                    has_valid_human_approval=False,
                    has_valid_financial_assessment=True,
                ),
            )

    def test_human_approval_without_financial_assessment_fails(
        self, sm: StateMachineService
    ) -> None:
        with pytest.raises(TransitionGuardError, match="valid_financial_assessment"):
            sm.transition(
                RecoveryCaseStatus.HUMAN_REVIEW,
                RecoveryEvent.HUMAN_APPROVAL_GRANTED,
                TransitionContext(
                    has_valid_human_approval=True,
                    has_valid_financial_assessment=False,
                ),
            )

    def test_default_context_fails_closed_for_policy_approved(
        self, sm: StateMachineService
    ) -> None:
        """Default TransitionContext has no valid proposal/assessment — must fail."""
        with pytest.raises(TransitionGuardError):
            sm.transition(
                RecoveryCaseStatus.POLICY_REVIEW,
                RecoveryEvent.POLICY_APPROVED,
            )

    def test_default_context_fails_closed_for_human_approval(
        self, sm: StateMachineService
    ) -> None:
        with pytest.raises(TransitionGuardError):
            sm.transition(
                RecoveryCaseStatus.HUMAN_REVIEW,
                RecoveryEvent.HUMAN_APPROVAL_GRANTED,
            )

    def test_stale_assessment_blocks_execution(self, sm: StateMachineService) -> None:
        """Stale financial assessment (False) must block POLICY_APPROVED."""
        with pytest.raises(TransitionGuardError, match="valid_financial_assessment"):
            sm.transition(
                RecoveryCaseStatus.POLICY_REVIEW,
                RecoveryEvent.POLICY_APPROVED,
                TransitionContext(
                    has_valid_proposal=True,
                    has_valid_financial_assessment=False,
                ),
            )


# =========================================================================
# 11. Evidence paths
# =========================================================================

class TestEvidencePaths:
    """Evidence-related transitions."""

    def test_evidence_insufficient_to_human_review(
        self, sm: StateMachineService
    ) -> None:
        result = sm.transition(
            RecoveryCaseStatus.EVIDENCE_ANALYSIS, RecoveryEvent.EVIDENCE_INSUFFICIENT
        )
        assert result.state_after == RecoveryCaseStatus.HUMAN_REVIEW

    def test_evidence_conflict_to_human_review(self, sm: StateMachineService) -> None:
        result = sm.transition(
            RecoveryCaseStatus.EVIDENCE_ANALYSIS, RecoveryEvent.EVIDENCE_CONFLICT
        )
        assert result.state_after == RecoveryCaseStatus.HUMAN_REVIEW


# =========================================================================
# 12. Human review flows
# =========================================================================

class TestHumanReview:
    """HUMAN_REVIEW state transitions."""

    def test_human_approval_granted_to_recovery_initiated(
        self, sm: StateMachineService
    ) -> None:
        result = sm.transition(
            RecoveryCaseStatus.HUMAN_REVIEW,
            RecoveryEvent.HUMAN_APPROVAL_GRANTED,
            TransitionContext(
                has_valid_human_approval=True,
                has_valid_financial_assessment=True,
            ),
        )
        assert result.state_after == RecoveryCaseStatus.RECOVERY_INITIATED

    def test_review_back_to_resolution(self, sm: StateMachineService) -> None:
        result = sm.transition(
            RecoveryCaseStatus.HUMAN_REVIEW, RecoveryEvent.REVIEW_BACK_TO_RESOLUTION
        )
        assert result.state_after == RecoveryCaseStatus.RESOLUTION_READY

    def test_review_back_to_policy(self, sm: StateMachineService) -> None:
        result = sm.transition(
            RecoveryCaseStatus.HUMAN_REVIEW, RecoveryEvent.REVIEW_BACK_TO_POLICY
        )
        assert result.state_after == RecoveryCaseStatus.POLICY_REVIEW

    def test_review_closed(self, sm: StateMachineService) -> None:
        result = sm.transition(
            RecoveryCaseStatus.HUMAN_REVIEW, RecoveryEvent.REVIEW_CLOSED
        )
        assert result.state_after == RecoveryCaseStatus.CLOSED


# =========================================================================
# 13. validate_transition (non-raising)
# =========================================================================

class TestValidateTransition:
    """Non-raising validation method."""

    def test_valid_returns_allowed_true(self, sm: StateMachineService) -> None:
        result = sm.validate_transition(
            RecoveryCaseStatus.OVERDUE, RecoveryEvent.START_TRIAGE
        )
        assert result.allowed is True
        assert result.state_after == RecoveryCaseStatus.TRIAGING

    def test_invalid_returns_allowed_false(self, sm: StateMachineService) -> None:
        result = sm.validate_transition(
            RecoveryCaseStatus.OVERDUE, RecoveryEvent.PAYMENT_CONFIRMED
        )
        assert result.allowed is False
        assert result.state_after == RecoveryCaseStatus.OVERDUE  # unchanged

    def test_guard_failure_returns_allowed_false(self, sm: StateMachineService) -> None:
        result = sm.validate_transition(
            RecoveryCaseStatus.POLICY_REVIEW,
            RecoveryEvent.POLICY_APPROVED,
            TransitionContext(has_valid_proposal=False),
        )
        assert result.allowed is False


# =========================================================================
# 14. TransitionResult structure
# =========================================================================

class TestTransitionResult:
    """Verify TransitionResult contains required fields."""

    def test_result_contains_required_fields(self, sm: StateMachineService) -> None:
        result = sm.transition(
            RecoveryCaseStatus.OVERDUE,
            RecoveryEvent.START_TRIAGE,
            TransitionContext(event_id="EVT-001", metadata={"source": "test"}),
        )
        assert isinstance(result, TransitionResult)
        assert result.allowed is True
        assert result.state_before == RecoveryCaseStatus.OVERDUE
        assert result.state_after == RecoveryCaseStatus.TRIAGING
        assert result.event == RecoveryEvent.START_TRIAGE
        assert isinstance(result.reason, str)
        assert result.event_id == "EVT-001"
        assert result.metadata == {"source": "test"}

    def test_rejection_result_structure(self, sm: StateMachineService) -> None:
        result = sm.validate_transition(
            RecoveryCaseStatus.CLOSED, RecoveryEvent.START_TRIAGE
        )
        assert result.allowed is False
        assert result.state_before == RecoveryCaseStatus.CLOSED
        assert result.state_after == RecoveryCaseStatus.CLOSED
        assert result.event == RecoveryEvent.START_TRIAGE
        assert "terminal" in result.reason.lower()


# =========================================================================
# 15. get_allowed_events
# =========================================================================

class TestGetAllowedEvents:
    """Verify get_allowed_events returns structurally valid events."""

    def test_overdue_allowed_events(self, sm: StateMachineService) -> None:
        events = sm.get_allowed_events(RecoveryCaseStatus.OVERDUE)
        assert RecoveryEvent.START_TRIAGE in events
        assert RecoveryEvent.LEGAL_RISK_DETECTED in events
        assert RecoveryEvent.MANUAL_LOCK in events

    def test_closed_has_no_events(self, sm: StateMachineService) -> None:
        events = sm.get_allowed_events(RecoveryCaseStatus.CLOSED)
        assert events == []


# =========================================================================
# 16. No AI/Razorpay dependencies
# =========================================================================

class TestNoDependencies:
    """Verify the state machine has no AI, Razorpay, or external dependencies."""

    def test_no_ai_imports(self) -> None:
        """The state machine module must not import AI/LLM modules."""
        import inspect

        import app.services.state_machine as sm_module

        source = inspect.getsource(sm_module)
        # Extract only import lines to avoid false positives from docstrings
        import_lines = [
            line.strip()
            for line in source.splitlines()
            if line.strip().startswith(("import ", "from "))
        ]
        import_text = "\n".join(import_lines).lower()
        ai_modules = [
            "openai", "anthropic", "langchain", "google.generativeai",
            "litellm", "transformers",
        ]
        for mod in ai_modules:
            assert mod not in import_text, (
                f"State machine imports AI module: {mod}"
            )

    def test_no_razorpay_imports(self) -> None:
        """The state machine module must not import Razorpay modules."""
        import inspect

        import app.services.state_machine as sm_module

        source = inspect.getsource(sm_module)
        import_lines = [
            line.strip()
            for line in source.splitlines()
            if line.strip().startswith(("import ", "from "))
        ]
        import_text = "\n".join(import_lines).lower()
        razorpay_modules = ["razorpay", "webhook"]
        for mod in razorpay_modules:
            assert mod not in import_text, (
                f"State machine imports Razorpay-related module: {mod}"
            )

    def test_no_database_imports(self) -> None:
        """The state machine module must not import database/session modules."""
        import inspect

        import app.services.state_machine as sm_module

        source = inspect.getsource(sm_module)
        import_lines = [
            line.strip()
            for line in source.splitlines()
            if line.strip().startswith(("import ", "from "))
        ]
        import_text = "\n".join(import_lines).lower()
        db_modules = ["sqlalchemy", "asyncpg", "alembic"]
        for mod in db_modules:
            assert mod not in import_text, (
                f"State machine imports DB module: {mod}"
            )


# =========================================================================
# 17. No duplicated financial arithmetic
# =========================================================================

class TestNoFinancialArithmetic:
    """The state machine must NOT independently calculate financial amounts."""

    def test_no_financial_calculation_in_source(self) -> None:
        """The state machine must not contain financial calculation logic."""
        import inspect

        import app.services.state_machine as sm_module

        source = inspect.getsource(sm_module)
        # It should not calculate collectible, disputed, recovered amounts
        financial_calc_patterns = [
            "invoice_amount -",
            "invoice_amount -",
            "collectible_amount =",
            "disputed_amount =",
            "remaining_amount =",
        ]
        for pattern in financial_calc_patterns:
            assert pattern not in source, (
                f"State machine source contains financial calculation: {pattern}"
            )


# =========================================================================
# 18. Safety interrupt priority
# =========================================================================

class TestSafetyInterruptPriority:
    """Safety interrupts take priority over normal transitions."""

    def test_legal_risk_interrupts_payment_pending(
        self, sm: StateMachineService
    ) -> None:
        result = sm.transition(
            RecoveryCaseStatus.PAYMENT_PENDING, RecoveryEvent.LEGAL_RISK_DETECTED
        )
        assert result.state_after == RecoveryCaseStatus.AUTOMATION_LOCKED

    def test_manual_lock_interrupts_evidence_analysis(
        self, sm: StateMachineService
    ) -> None:
        result = sm.transition(
            RecoveryCaseStatus.EVIDENCE_ANALYSIS, RecoveryEvent.MANUAL_LOCK
        )
        assert result.state_after == RecoveryCaseStatus.AUTOMATION_LOCKED

    def test_legal_risk_from_partially_recovered(
        self, sm: StateMachineService
    ) -> None:
        result = sm.transition(
            RecoveryCaseStatus.PARTIALLY_RECOVERED, RecoveryEvent.LEGAL_RISK_DETECTED
        )
        assert result.state_after == RecoveryCaseStatus.AUTOMATION_LOCKED


# =========================================================================
# 19. State and event enum integrity
# =========================================================================

class TestEnumIntegrity:
    """Verify enum completeness and integrity."""

    def test_all_15_states_exist(self) -> None:
        expected = {
            "OVERDUE", "TRIAGING", "ISSUE_IDENTIFIED", "EVIDENCE_ANALYSIS",
            "RESOLUTION_READY", "POLICY_REVIEW", "RECOVERY_INITIATED",
            "PAYMENT_PENDING", "PARTIALLY_RECOVERED", "FULLY_RECOVERED",
            "HUMAN_REVIEW", "LEGAL_ESCALATION", "AUTOMATION_LOCKED",
            "EXECUTION_FAILED", "CLOSED",
        }
        actual = {s.value for s in RecoveryCaseStatus}
        assert actual == expected

    def test_payment_confirmed_is_not_a_state(self) -> None:
        state_values = {s.value for s in RecoveryCaseStatus}
        assert "PAYMENT_CONFIRMED" not in state_values

    def test_payment_confirmed_is_an_event(self) -> None:
        event_values = {e.value for e in RecoveryEvent}
        assert "PAYMENT_CONFIRMED" in event_values

    def test_terminal_states_set(self) -> None:
        assert RecoveryCaseStatus.CLOSED in TERMINAL_STATES

    def test_financial_execution_states(self) -> None:
        assert RecoveryCaseStatus.RECOVERY_INITIATED in FINANCIAL_EXECUTION_STATES
        assert RecoveryCaseStatus.PAYMENT_PENDING in FINANCIAL_EXECUTION_STATES


# =========================================================================
# 20. Edge cases
# =========================================================================

class TestEdgeCases:
    """Edge cases and boundary conditions."""

    def test_transition_with_none_context_uses_defaults(
        self, sm: StateMachineService
    ) -> None:
        """Passing None context should use default TransitionContext."""
        result = sm.transition(
            RecoveryCaseStatus.OVERDUE, RecoveryEvent.START_TRIAGE, None
        )
        assert result.allowed is True

    def test_safety_interrupt_idempotent_on_locked_state(
        self, sm: StateMachineService
    ) -> None:
        """Applying LEGAL_RISK_DETECTED to AUTOMATION_LOCKED is idempotent."""
        result = sm.transition(
            RecoveryCaseStatus.AUTOMATION_LOCKED, RecoveryEvent.LEGAL_RISK_DETECTED
        )
        assert result.allowed is True
        assert result.state_after == RecoveryCaseStatus.AUTOMATION_LOCKED

    def test_legal_lock_blocks_human_approval_granted(
        self, sm: StateMachineService
    ) -> None:
        with pytest.raises(TransitionGuardError, match="legal_lock"):
            sm.transition(
                RecoveryCaseStatus.HUMAN_REVIEW,
                RecoveryEvent.HUMAN_APPROVAL_GRANTED,
                TransitionContext(
                    has_valid_human_approval=True,
                    has_valid_financial_assessment=True,
                    is_legal_locked=True,
                ),
            )

    def test_canonical_partial_recovery_path(self, sm: StateMachineService) -> None:
        """Canonical: ₹10L invoice, ₹1L dispute, ₹9L collectible.
        Policy: HUMAN_APPROVAL_REQUIRED → HUMAN_REVIEW → approved → recover ₹9L.
        Post-recovery: PARTIALLY_RECOVERED (₹1L dispute remains)."""

        # POLICY_REVIEW → HUMAN_REVIEW (policy says human approval needed)
        r1 = sm.transition(
            RecoveryCaseStatus.POLICY_REVIEW,
            RecoveryEvent.HUMAN_APPROVAL_REQUIRED,
        )
        assert r1.state_after == RecoveryCaseStatus.HUMAN_REVIEW

        # HUMAN_REVIEW → RECOVERY_INITIATED (human approves)
        r2 = sm.transition(
            RecoveryCaseStatus.HUMAN_REVIEW,
            RecoveryEvent.HUMAN_APPROVAL_GRANTED,
            TransitionContext(
                has_valid_human_approval=True,
                has_valid_financial_assessment=True,
            ),
        )
        assert r2.state_after == RecoveryCaseStatus.RECOVERY_INITIATED

        # RECOVERY_INITIATED → PAYMENT_PENDING
        r3 = sm.transition(
            RecoveryCaseStatus.RECOVERY_INITIATED,
            RecoveryEvent.PAYMENT_REQUEST_CREATED,
        )
        assert r3.state_after == RecoveryCaseStatus.PAYMENT_PENDING

        # PAYMENT_PENDING → PARTIALLY_RECOVERED
        # ₹9L recovered out of ₹10L invoice total (₹1L disputed)
        r4 = sm.transition(
            RecoveryCaseStatus.PAYMENT_PENDING,
            RecoveryEvent.PAYMENT_CONFIRMED,
            TransitionContext(
                payment_verified=True,
                verified_recovered_amount=900_000_00,       # ₹9,00,000
                applicable_recoverable_balance=1_000_000_00,  # ₹10,00,000 total
            ),
        )
        assert r4.state_after == RecoveryCaseStatus.PARTIALLY_RECOVERED
