"""Comprehensive tests for the deterministic Policy Engine.

Covers:
  - Canonical ₹9L collectible / ₹5L authority case
  - Within-authority approval
  - Over-authority human approval
  - Blocked cases (amount exceeds collectible, evidence, state, etc.)
  - Stopped cases (legal risk, safety, automation lock)
  - Deferred cases (quiet hours)
  - Legal/safety restrictions
  - Stale/insufficient/conflicting financial inputs
  - Concession limits
  - Missing/invalid policy data
  - Deterministic repeatability
  - No financial arithmetic duplication
  - No AI/Razorpay/DB side effects
  - Touchpoint limits
  - Fully recovered blocking
"""

from datetime import time

import pytest

from app.domain.enums import PolicyDecisionResult, RecoveryActionType, RecoveryCaseStatus
from app.services.policy_engine import (
    FinancialAssessmentSnapshot,
    MerchantPolicySnapshot,
    PolicyDecision,
    PolicyEngineService,
    PolicyEvaluationInput,
    PolicyReasonCode,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def engine() -> PolicyEngineService:
    """Provide a fresh PolicyEngineService instance."""
    return PolicyEngineService()


@pytest.fixture
def default_policy() -> MerchantPolicySnapshot:
    """Default merchant policy: ₹5,00,000 auto authority, 5% / ₹25,000 concession."""
    return MerchantPolicySnapshot(
        version="v1.0",
        max_auto_recovery_amount=500_000_00,     # ₹5,00,000 in paise
        max_concession_percent=500,               # 5.00% in basis points
        max_concession_amount=25_000_00,          # ₹25,000 in paise
        max_touchpoints=3,
        touchpoint_window_days=14,
        quiet_hours_start=time(20, 0),
        quiet_hours_end=time(8, 0),
        high_value_threshold=500_000_00,
        max_execution_retries=2,
    )


@pytest.fixture
def canonical_assessment() -> FinancialAssessmentSnapshot:
    """Canonical case: ₹10L invoice, ₹1L dispute, ₹9L collectible."""
    return FinancialAssessmentSnapshot(
        status="CALCULATED",
        gross_invoice_amount_minor=1_000_000_00,  # ₹10,00,000
        collectible_amount_minor=900_000_00,       # ₹9,00,000
        safely_recoverable_amount_minor=900_000_00,
        verified_recovered_amount_minor=0,
        remaining_amount_minor=900_000_00,
    )


@pytest.fixture
def small_assessment() -> FinancialAssessmentSnapshot:
    """Small case within auto-authority: ₹3L collectible."""
    return FinancialAssessmentSnapshot(
        status="CALCULATED",
        gross_invoice_amount_minor=300_000_00,
        collectible_amount_minor=300_000_00,
        safely_recoverable_amount_minor=300_000_00,
        verified_recovered_amount_minor=0,
        remaining_amount_minor=300_000_00,
    )


def _make_input(
    *,
    policy: MerchantPolicySnapshot | None = None,
    assessment: FinancialAssessmentSnapshot | None = None,
    proposed_amount: int = 900_000_00,
    action_type: RecoveryActionType = RecoveryActionType.CREATE_PAYMENT_LINK,
    current_state: RecoveryCaseStatus = RecoveryCaseStatus.POLICY_REVIEW,
    evidence_sufficient: bool = True,
    evidence_conflict: bool = False,
    is_legal_locked: bool = False,
    is_automation_locked: bool = False,
    is_safety_violation: bool = False,
    touchpoints_in_window: int = 1,
    current_time: time | None = None,
    is_financial_assessment_stale: bool = False,
    concession_amount: int = 0,
    invoice_amount: int = 0,
) -> PolicyEvaluationInput:
    return PolicyEvaluationInput(
        case_id="case-001",
        current_state=current_state,
        action_type=action_type,
        proposed_amount=proposed_amount,
        proposal_id="prop-001",
        financial_assessment=assessment,
        merchant_policy=policy,
        evidence_sufficient=evidence_sufficient,
        evidence_conflict=evidence_conflict,
        is_legal_locked=is_legal_locked,
        is_automation_locked=is_automation_locked,
        is_safety_violation=is_safety_violation,
        touchpoints_in_window=touchpoints_in_window,
        current_time=current_time,
        is_financial_assessment_stale=is_financial_assessment_stale,
        concession_amount=concession_amount,
        invoice_amount=invoice_amount,
    )


# =========================================================================
# 1. Canonical case — ₹9L collectible / ₹5L authority
# =========================================================================

class TestCanonicalCase:
    """Canonical case from the spec: ₹10L invoice, ₹1L dispute, ₹9L collectible."""

    def test_canonical_human_approval_required(
        self,
        engine: PolicyEngineService,
        default_policy: MerchantPolicySnapshot,
        canonical_assessment: FinancialAssessmentSnapshot,
    ) -> None:
        """₹9,00,000 > ₹5,00,000 autonomous authority → HUMAN_APPROVAL_REQUIRED."""
        inp = _make_input(
            policy=default_policy,
            assessment=canonical_assessment,
            proposed_amount=900_000_00,
        )
        result = engine.evaluate(inp)
        assert result.decision == PolicyDecisionResult.HUMAN_APPROVAL_REQUIRED
        assert result.reason_code == PolicyReasonCode.AUTO_RECOVERY_LIMIT_EXCEEDED
        assert result.checks["auto_limit_ok"] is False
        assert result.policy_version == "v1.0"

    def test_canonical_does_not_reduce_collectible(
        self,
        engine: PolicyEngineService,
        default_policy: MerchantPolicySnapshot,
        canonical_assessment: FinancialAssessmentSnapshot,
    ) -> None:
        """Policy Engine must NOT reduce financial assessment to ₹5L authority."""
        inp = _make_input(
            policy=default_policy,
            assessment=canonical_assessment,
            proposed_amount=900_000_00,
        )
        result = engine.evaluate(inp)
        # The decision is HUMAN_APPROVAL_REQUIRED, not BLOCKED
        assert result.decision == PolicyDecisionResult.HUMAN_APPROVAL_REQUIRED
        # Amount is supported (under collectible), just over auto authority
        assert result.checks["amount_supported"] is True


# =========================================================================
# 2. Within-authority approval
# =========================================================================

class TestWithinAuthorityApproval:
    """Cases where proposed amount is within autonomous authority."""

    def test_approved_within_authority(
        self,
        engine: PolicyEngineService,
        default_policy: MerchantPolicySnapshot,
        small_assessment: FinancialAssessmentSnapshot,
    ) -> None:
        """₹3L proposed, ₹5L authority → APPROVED."""
        inp = _make_input(
            policy=default_policy,
            assessment=small_assessment,
            proposed_amount=300_000_00,
        )
        result = engine.evaluate(inp)
        assert result.decision == PolicyDecisionResult.APPROVED
        assert result.reason_code == PolicyReasonCode.WITHIN_AUTOMATED_AUTHORITY
        assert result.checks["auto_limit_ok"] is True
        assert result.checks["amount_supported"] is True

    def test_approved_exactly_at_authority_limit(
        self,
        engine: PolicyEngineService,
        default_policy: MerchantPolicySnapshot,
    ) -> None:
        """₹5L proposed = ₹5L authority → APPROVED (boundary)."""
        assessment = FinancialAssessmentSnapshot(
            status="CALCULATED",
            gross_invoice_amount_minor=500_000_00,
            collectible_amount_minor=500_000_00,
            safely_recoverable_amount_minor=500_000_00,
            verified_recovered_amount_minor=0,
            remaining_amount_minor=500_000_00,
        )
        inp = _make_input(
            policy=default_policy,
            assessment=assessment,
            proposed_amount=500_000_00,
        )
        result = engine.evaluate(inp)
        assert result.decision == PolicyDecisionResult.APPROVED

    def test_approved_with_high_authority_merchant(
        self,
        engine: PolicyEngineService,
        canonical_assessment: FinancialAssessmentSnapshot,
    ) -> None:
        """Merchant with ₹10L authority, ₹9L proposal → APPROVED."""
        high_authority_policy = MerchantPolicySnapshot(
            version="v1.0",
            max_auto_recovery_amount=1_000_000_00,
            max_concession_percent=500,
            max_concession_amount=25_000_00,
            max_touchpoints=3,
            touchpoint_window_days=14,
        )
        inp = _make_input(
            policy=high_authority_policy,
            assessment=canonical_assessment,
            proposed_amount=900_000_00,
        )
        result = engine.evaluate(inp)
        assert result.decision == PolicyDecisionResult.APPROVED

    def test_approved_checks_structure(
        self,
        engine: PolicyEngineService,
        default_policy: MerchantPolicySnapshot,
        small_assessment: FinancialAssessmentSnapshot,
    ) -> None:
        """Verify all expected checks are present in APPROVED result."""
        inp = _make_input(
            policy=default_policy,
            assessment=small_assessment,
            proposed_amount=300_000_00,
        )
        result = engine.evaluate(inp)
        assert result.decision == PolicyDecisionResult.APPROVED
        expected_checks = {
            "legal_lock", "financial_assessment_current",
            "financial_assessment_verified", "evidence_conflict",
            "evidence_sufficient", "state_valid", "amount_valid",
            "collectible_available", "amount_supported",
            "amount_within_safely_recoverable", "not_fully_recovered",
            "concession_limit_ok", "auto_limit_ok", "touchpoint_limit_ok",
            "quiet_hours_ok",
        }
        assert expected_checks.issubset(set(result.checks.keys()))


# =========================================================================
# 3. Over-authority human approval
# =========================================================================

class TestOverAuthorityHumanApproval:
    """Proposed amount exceeds autonomous authority → HUMAN_APPROVAL_REQUIRED."""

    def test_just_over_authority(
        self,
        engine: PolicyEngineService,
        default_policy: MerchantPolicySnapshot,
    ) -> None:
        """₹5,00,001 proposed vs ₹5,00,000 authority → HUMAN_APPROVAL_REQUIRED."""
        assessment = FinancialAssessmentSnapshot(
            status="CALCULATED",
            gross_invoice_amount_minor=600_000_00,
            collectible_amount_minor=600_000_00,
            safely_recoverable_amount_minor=600_000_00,
            verified_recovered_amount_minor=0,
            remaining_amount_minor=600_000_00,
        )
        inp = _make_input(
            policy=default_policy,
            assessment=assessment,
            proposed_amount=500_001_00,  # ₹5,00,001
        )
        result = engine.evaluate(inp)
        assert result.decision == PolicyDecisionResult.HUMAN_APPROVAL_REQUIRED
        assert result.reason_code == PolicyReasonCode.AUTO_RECOVERY_LIMIT_EXCEEDED


# =========================================================================
# 4. Blocked cases
# =========================================================================

class TestBlockedCases:
    """Cases that are BLOCKED by hard policy constraints."""

    def test_amount_exceeds_collectible(
        self,
        engine: PolicyEngineService,
        default_policy: MerchantPolicySnapshot,
    ) -> None:
        """Proposed ₹9L but collectible is only ₹7L → BLOCKED."""
        assessment = FinancialAssessmentSnapshot(
            status="CALCULATED",
            gross_invoice_amount_minor=1_000_000_00,
            collectible_amount_minor=700_000_00,
            safely_recoverable_amount_minor=700_000_00,
            verified_recovered_amount_minor=0,
            remaining_amount_minor=700_000_00,
        )
        inp = _make_input(
            policy=default_policy,
            assessment=assessment,
            proposed_amount=900_000_00,
        )
        result = engine.evaluate(inp)
        assert result.decision == PolicyDecisionResult.BLOCKED
        assert result.reason_code == PolicyReasonCode.AMOUNT_EXCEEDS_COLLECTIBLE

    def test_amount_exceeds_safely_recoverable(
        self,
        engine: PolicyEngineService,
        default_policy: MerchantPolicySnapshot,
    ) -> None:
        """Proposed amount exceeds safely recoverable → BLOCKED."""
        assessment = FinancialAssessmentSnapshot(
            status="CALCULATED",
            gross_invoice_amount_minor=500_000_00,
            collectible_amount_minor=500_000_00,
            safely_recoverable_amount_minor=300_000_00,  # lower than collectible
            verified_recovered_amount_minor=0,
            remaining_amount_minor=300_000_00,
        )
        inp = _make_input(
            policy=default_policy,
            assessment=assessment,
            proposed_amount=400_000_00,
        )
        result = engine.evaluate(inp)
        assert result.decision == PolicyDecisionResult.BLOCKED
        assert result.reason_code == PolicyReasonCode.AMOUNT_EXCEEDS_SAFELY_RECOVERABLE

    def test_zero_proposed_amount_blocked(
        self,
        engine: PolicyEngineService,
        default_policy: MerchantPolicySnapshot,
        small_assessment: FinancialAssessmentSnapshot,
    ) -> None:
        """Zero proposed amount → BLOCKED."""
        inp = _make_input(
            policy=default_policy,
            assessment=small_assessment,
            proposed_amount=0,
        )
        result = engine.evaluate(inp)
        assert result.decision == PolicyDecisionResult.BLOCKED
        assert result.reason_code == PolicyReasonCode.INVALID_PROPOSAL_AMOUNT

    def test_negative_proposed_amount_blocked(
        self,
        engine: PolicyEngineService,
        default_policy: MerchantPolicySnapshot,
        small_assessment: FinancialAssessmentSnapshot,
    ) -> None:
        """Negative proposed amount → BLOCKED."""
        inp = _make_input(
            policy=default_policy,
            assessment=small_assessment,
            proposed_amount=-100,
        )
        result = engine.evaluate(inp)
        assert result.decision == PolicyDecisionResult.BLOCKED
        assert result.reason_code == PolicyReasonCode.INVALID_PROPOSAL_AMOUNT

    def test_invalid_case_state_legal_escalation(
        self,
        engine: PolicyEngineService,
        default_policy: MerchantPolicySnapshot,
        small_assessment: FinancialAssessmentSnapshot,
    ) -> None:
        """LEGAL_ESCALATION state → BLOCKED."""
        inp = _make_input(
            policy=default_policy,
            assessment=small_assessment,
            proposed_amount=100_000_00,
            current_state=RecoveryCaseStatus.LEGAL_ESCALATION,
        )
        result = engine.evaluate(inp)
        assert result.decision == PolicyDecisionResult.BLOCKED
        assert result.reason_code == PolicyReasonCode.INVALID_CASE_STATE

    def test_invalid_case_state_automation_locked(
        self,
        engine: PolicyEngineService,
        default_policy: MerchantPolicySnapshot,
        small_assessment: FinancialAssessmentSnapshot,
    ) -> None:
        """AUTOMATION_LOCKED state → BLOCKED."""
        inp = _make_input(
            policy=default_policy,
            assessment=small_assessment,
            proposed_amount=100_000_00,
            current_state=RecoveryCaseStatus.AUTOMATION_LOCKED,
        )
        result = engine.evaluate(inp)
        assert result.decision == PolicyDecisionResult.BLOCKED
        assert result.reason_code == PolicyReasonCode.INVALID_CASE_STATE

    def test_invalid_case_state_closed(
        self,
        engine: PolicyEngineService,
        default_policy: MerchantPolicySnapshot,
        small_assessment: FinancialAssessmentSnapshot,
    ) -> None:
        """CLOSED state → BLOCKED."""
        inp = _make_input(
            policy=default_policy,
            assessment=small_assessment,
            proposed_amount=100_000_00,
            current_state=RecoveryCaseStatus.CLOSED,
        )
        result = engine.evaluate(inp)
        assert result.decision == PolicyDecisionResult.BLOCKED
        assert result.reason_code == PolicyReasonCode.INVALID_CASE_STATE

    def test_fully_recovered_no_further_action(
        self,
        engine: PolicyEngineService,
        default_policy: MerchantPolicySnapshot,
    ) -> None:
        """Fully recovered (remaining=0) → BLOCKED."""
        assessment = FinancialAssessmentSnapshot(
            status="CALCULATED",
            gross_invoice_amount_minor=500_000_00,
            collectible_amount_minor=500_000_00,
            safely_recoverable_amount_minor=500_000_00,
            verified_recovered_amount_minor=500_000_00,
            remaining_amount_minor=0,
        )
        inp = _make_input(
            policy=default_policy,
            assessment=assessment,
            proposed_amount=100_000_00,
            current_state=RecoveryCaseStatus.POLICY_REVIEW,
        )
        result = engine.evaluate(inp)
        assert result.decision == PolicyDecisionResult.BLOCKED
        assert result.reason_code == PolicyReasonCode.FULLY_RECOVERED_NO_ACTION

    def test_touchpoint_limit_exceeded(
        self,
        engine: PolicyEngineService,
        default_policy: MerchantPolicySnapshot,
        small_assessment: FinancialAssessmentSnapshot,
    ) -> None:
        """Outreach with touchpoints at limit → BLOCKED."""
        inp = _make_input(
            policy=default_policy,
            assessment=small_assessment,
            proposed_amount=100_000_00,
            action_type=RecoveryActionType.SEND_REMINDER,
            touchpoints_in_window=3,  # equals max_touchpoints=3
        )
        result = engine.evaluate(inp)
        assert result.decision == PolicyDecisionResult.BLOCKED
        assert result.reason_code == PolicyReasonCode.TOUCHPOINT_LIMIT_EXCEEDED


# =========================================================================
# 5. Stopped cases
# =========================================================================

class TestStoppedCases:
    """Cases that are STOPPED by legal/safety constraints."""

    def test_legal_lock_stops_automation(
        self,
        engine: PolicyEngineService,
        default_policy: MerchantPolicySnapshot,
        canonical_assessment: FinancialAssessmentSnapshot,
    ) -> None:
        """Legal lock → STOPPED."""
        inp = _make_input(
            policy=default_policy,
            assessment=canonical_assessment,
            proposed_amount=100_000_00,
            is_legal_locked=True,
        )
        result = engine.evaluate(inp)
        assert result.decision == PolicyDecisionResult.STOPPED
        assert result.reason_code == PolicyReasonCode.LEGAL_RISK
        assert result.checks["legal_lock"] is True
        assert result.checks["automated_recovery_allowed"] is False
        assert result.checks["automated_outreach_allowed"] is False

    def test_safety_violation_stops_automation(
        self,
        engine: PolicyEngineService,
        default_policy: MerchantPolicySnapshot,
        canonical_assessment: FinancialAssessmentSnapshot,
    ) -> None:
        """Safety violation → STOPPED."""
        inp = _make_input(
            policy=default_policy,
            assessment=canonical_assessment,
            proposed_amount=100_000_00,
            is_safety_violation=True,
        )
        result = engine.evaluate(inp)
        assert result.decision == PolicyDecisionResult.STOPPED
        assert result.reason_code == PolicyReasonCode.SAFETY_VIOLATION

    def test_automation_locked_stops(
        self,
        engine: PolicyEngineService,
        default_policy: MerchantPolicySnapshot,
        canonical_assessment: FinancialAssessmentSnapshot,
    ) -> None:
        """Automation locked → STOPPED."""
        inp = _make_input(
            policy=default_policy,
            assessment=canonical_assessment,
            proposed_amount=100_000_00,
            is_automation_locked=True,
        )
        result = engine.evaluate(inp)
        assert result.decision == PolicyDecisionResult.STOPPED

    def test_legal_lock_has_highest_priority(
        self,
        engine: PolicyEngineService,
        default_policy: MerchantPolicySnapshot,
        canonical_assessment: FinancialAssessmentSnapshot,
    ) -> None:
        """Legal lock takes precedence over everything else."""
        inp = _make_input(
            policy=default_policy,
            assessment=canonical_assessment,
            proposed_amount=900_000_00,
            is_legal_locked=True,
            evidence_sufficient=False,  # would be BLOCKED otherwise
        )
        result = engine.evaluate(inp)
        # Legal stop must come first
        assert result.decision == PolicyDecisionResult.STOPPED
        assert result.reason_code == PolicyReasonCode.LEGAL_RISK


# =========================================================================
# 6. Deferred cases
# =========================================================================

class TestDeferredCases:
    """Cases deferred due to quiet hours."""

    def test_quiet_hours_defer_outreach(
        self,
        engine: PolicyEngineService,
        default_policy: MerchantPolicySnapshot,
        small_assessment: FinancialAssessmentSnapshot,
    ) -> None:
        """Outreach during quiet hours (21:00, window 20:00-08:00) → DEFERRED."""
        inp = _make_input(
            policy=default_policy,
            assessment=small_assessment,
            proposed_amount=100_000_00,
            action_type=RecoveryActionType.SEND_REMINDER,
            current_time=time(21, 0),
            touchpoints_in_window=0,
        )
        result = engine.evaluate(inp)
        assert result.decision == PolicyDecisionResult.DEFERRED
        assert result.reason_code == PolicyReasonCode.QUIET_HOURS

    def test_outside_quiet_hours_not_deferred(
        self,
        engine: PolicyEngineService,
        default_policy: MerchantPolicySnapshot,
        small_assessment: FinancialAssessmentSnapshot,
    ) -> None:
        """Outreach during business hours (10:00) → not deferred."""
        inp = _make_input(
            policy=default_policy,
            assessment=small_assessment,
            proposed_amount=100_000_00,
            action_type=RecoveryActionType.SEND_REMINDER,
            current_time=time(10, 0),
            touchpoints_in_window=0,
        )
        result = engine.evaluate(inp)
        assert result.decision == PolicyDecisionResult.APPROVED

    def test_quiet_hours_at_boundary_start(
        self,
        engine: PolicyEngineService,
        default_policy: MerchantPolicySnapshot,
        small_assessment: FinancialAssessmentSnapshot,
    ) -> None:
        """Exactly at quiet hours start (20:00) → DEFERRED."""
        inp = _make_input(
            policy=default_policy,
            assessment=small_assessment,
            proposed_amount=100_000_00,
            action_type=RecoveryActionType.SEND_REMINDER,
            current_time=time(20, 0),
            touchpoints_in_window=0,
        )
        result = engine.evaluate(inp)
        assert result.decision == PolicyDecisionResult.DEFERRED

    def test_quiet_hours_at_boundary_end(
        self,
        engine: PolicyEngineService,
        default_policy: MerchantPolicySnapshot,
        small_assessment: FinancialAssessmentSnapshot,
    ) -> None:
        """Exactly at quiet hours end (08:00) → allowed (end is exclusive)."""
        inp = _make_input(
            policy=default_policy,
            assessment=small_assessment,
            proposed_amount=100_000_00,
            action_type=RecoveryActionType.SEND_REMINDER,
            current_time=time(8, 0),
            touchpoints_in_window=0,
        )
        result = engine.evaluate(inp)
        assert result.decision == PolicyDecisionResult.APPROVED

    def test_quiet_hours_only_affect_outreach(
        self,
        engine: PolicyEngineService,
        default_policy: MerchantPolicySnapshot,
        small_assessment: FinancialAssessmentSnapshot,
    ) -> None:
        """Non-outreach action during quiet hours → not deferred."""
        inp = _make_input(
            policy=default_policy,
            assessment=small_assessment,
            proposed_amount=100_000_00,
            action_type=RecoveryActionType.CREATE_PAYMENT_LINK,
            current_time=time(22, 0),
        )
        result = engine.evaluate(inp)
        assert result.decision == PolicyDecisionResult.APPROVED


# =========================================================================
# 7. Financial assessment issues
# =========================================================================

class TestFinancialAssessmentIssues:
    """Stale, insufficient, conflicting financial assessments."""

    def test_stale_financial_assessment_blocked(
        self,
        engine: PolicyEngineService,
        default_policy: MerchantPolicySnapshot,
        canonical_assessment: FinancialAssessmentSnapshot,
    ) -> None:
        """Stale assessment → BLOCKED."""
        inp = _make_input(
            policy=default_policy,
            assessment=canonical_assessment,
            proposed_amount=100_000_00,
            is_financial_assessment_stale=True,
        )
        result = engine.evaluate(inp)
        assert result.decision == PolicyDecisionResult.BLOCKED
        assert result.reason_code == PolicyReasonCode.STALE_FINANCIAL_ASSESSMENT

    def test_missing_financial_assessment_blocked(
        self,
        engine: PolicyEngineService,
        default_policy: MerchantPolicySnapshot,
    ) -> None:
        """Missing assessment → BLOCKED."""
        inp = _make_input(
            policy=default_policy,
            assessment=None,
            proposed_amount=100_000_00,
        )
        result = engine.evaluate(inp)
        assert result.decision == PolicyDecisionResult.BLOCKED
        assert result.reason_code == PolicyReasonCode.MISSING_FINANCIAL_ASSESSMENT

    def test_conflicting_assessment_blocked(
        self,
        engine: PolicyEngineService,
        default_policy: MerchantPolicySnapshot,
    ) -> None:
        """Conflicting assessment status → BLOCKED."""
        assessment = FinancialAssessmentSnapshot(
            status="CONFLICTING",
            gross_invoice_amount_minor=1_000_000_00,
            collectible_amount_minor=0,
            safely_recoverable_amount_minor=0,
            verified_recovered_amount_minor=0,
            remaining_amount_minor=0,
        )
        inp = _make_input(
            policy=default_policy,
            assessment=assessment,
            proposed_amount=100_000_00,
        )
        result = engine.evaluate(inp)
        assert result.decision == PolicyDecisionResult.BLOCKED
        assert result.reason_code == PolicyReasonCode.EVIDENCE_CONFLICT

    def test_insufficient_assessment_blocked(
        self,
        engine: PolicyEngineService,
        default_policy: MerchantPolicySnapshot,
    ) -> None:
        """Insufficient assessment status → BLOCKED."""
        assessment = FinancialAssessmentSnapshot(
            status="INSUFFICIENT",
            gross_invoice_amount_minor=1_000_000_00,
            collectible_amount_minor=0,
            safely_recoverable_amount_minor=0,
            verified_recovered_amount_minor=0,
            remaining_amount_minor=0,
        )
        inp = _make_input(
            policy=default_policy,
            assessment=assessment,
            proposed_amount=100_000_00,
        )
        result = engine.evaluate(inp)
        assert result.decision == PolicyDecisionResult.BLOCKED
        assert result.reason_code == PolicyReasonCode.INVALID_FINANCIAL_ASSESSMENT

    def test_invalid_assessment_status_blocked(
        self,
        engine: PolicyEngineService,
        default_policy: MerchantPolicySnapshot,
    ) -> None:
        """INVALID assessment status → BLOCKED."""
        assessment = FinancialAssessmentSnapshot(
            status="INVALID",
            gross_invoice_amount_minor=1_000_000_00,
            collectible_amount_minor=0,
            safely_recoverable_amount_minor=0,
            verified_recovered_amount_minor=0,
            remaining_amount_minor=0,
        )
        inp = _make_input(
            policy=default_policy,
            assessment=assessment,
            proposed_amount=100_000_00,
        )
        result = engine.evaluate(inp)
        assert result.decision == PolicyDecisionResult.BLOCKED

    def test_pending_assessment_status_blocked(
        self,
        engine: PolicyEngineService,
        default_policy: MerchantPolicySnapshot,
    ) -> None:
        """PENDING assessment status → BLOCKED."""
        assessment = FinancialAssessmentSnapshot(
            status="PENDING",
            gross_invoice_amount_minor=1_000_000_00,
            collectible_amount_minor=0,
            safely_recoverable_amount_minor=0,
            verified_recovered_amount_minor=0,
            remaining_amount_minor=0,
        )
        inp = _make_input(
            policy=default_policy,
            assessment=assessment,
            proposed_amount=100_000_00,
        )
        result = engine.evaluate(inp)
        assert result.decision == PolicyDecisionResult.BLOCKED

    def test_zero_collectible_blocked(
        self,
        engine: PolicyEngineService,
        default_policy: MerchantPolicySnapshot,
    ) -> None:
        """Zero collectible amount → BLOCKED."""
        assessment = FinancialAssessmentSnapshot(
            status="CALCULATED",
            gross_invoice_amount_minor=1_000_000_00,
            collectible_amount_minor=0,
            safely_recoverable_amount_minor=0,
            verified_recovered_amount_minor=0,
            remaining_amount_minor=0,
        )
        inp = _make_input(
            policy=default_policy,
            assessment=assessment,
            proposed_amount=100_000_00,
        )
        result = engine.evaluate(inp)
        assert result.decision == PolicyDecisionResult.BLOCKED
        assert result.reason_code == PolicyReasonCode.MISSING_COLLECTIBLE_AMOUNT


# =========================================================================
# 8. Evidence issues
# =========================================================================

class TestEvidenceIssues:
    """Evidence conflict and insufficiency."""

    def test_evidence_conflict_blocks_recovery(
        self,
        engine: PolicyEngineService,
        default_policy: MerchantPolicySnapshot,
        canonical_assessment: FinancialAssessmentSnapshot,
    ) -> None:
        """Evidence conflict → BLOCKED."""
        inp = _make_input(
            policy=default_policy,
            assessment=canonical_assessment,
            proposed_amount=100_000_00,
            evidence_conflict=True,
        )
        result = engine.evaluate(inp)
        assert result.decision == PolicyDecisionResult.BLOCKED
        assert result.reason_code == PolicyReasonCode.EVIDENCE_CONFLICT

    def test_evidence_insufficient_blocks_recovery(
        self,
        engine: PolicyEngineService,
        default_policy: MerchantPolicySnapshot,
        canonical_assessment: FinancialAssessmentSnapshot,
    ) -> None:
        """Insufficient evidence → BLOCKED."""
        inp = _make_input(
            policy=default_policy,
            assessment=canonical_assessment,
            proposed_amount=100_000_00,
            evidence_sufficient=False,
        )
        result = engine.evaluate(inp)
        assert result.decision == PolicyDecisionResult.BLOCKED
        assert result.reason_code == PolicyReasonCode.EVIDENCE_INSUFFICIENT


# =========================================================================
# 9. Concession limits
# =========================================================================

class TestConcessionLimits:
    """Concession cap enforcement."""

    def test_concession_within_limit_approved(
        self,
        engine: PolicyEngineService,
        default_policy: MerchantPolicySnapshot,
        small_assessment: FinancialAssessmentSnapshot,
    ) -> None:
        """Concession ₹20,000 on ₹10L invoice (cap=min(5%=₹50K, ₹25K)=₹25K) → APPROVED."""
        inp = _make_input(
            policy=default_policy,
            assessment=small_assessment,
            proposed_amount=100_000_00,
            action_type=RecoveryActionType.APPLY_CONCESSION,
            concession_amount=20_000_00,    # ₹20,000
            invoice_amount=1_000_000_00,     # ₹10,00,000
        )
        result = engine.evaluate(inp)
        assert result.decision == PolicyDecisionResult.APPROVED

    def test_concession_exceeds_cap_requires_human_approval(
        self,
        engine: PolicyEngineService,
        default_policy: MerchantPolicySnapshot,
        small_assessment: FinancialAssessmentSnapshot,
    ) -> None:
        """Concession ₹30,000 on ₹10L invoice (cap=₹25K) → HUMAN_APPROVAL_REQUIRED."""
        inp = _make_input(
            policy=default_policy,
            assessment=small_assessment,
            proposed_amount=100_000_00,
            action_type=RecoveryActionType.APPLY_CONCESSION,
            concession_amount=30_000_00,    # ₹30,000
            invoice_amount=1_000_000_00,
        )
        result = engine.evaluate(inp)
        assert result.decision == PolicyDecisionResult.HUMAN_APPROVAL_REQUIRED
        assert result.reason_code == PolicyReasonCode.CONCESSION_EXCEEDS_AUTO_CAP

    def test_concession_cap_uses_min_of_percent_and_absolute(
        self,
        engine: PolicyEngineService,
    ) -> None:
        """Small invoice: 5% of ₹2L = ₹10K < ₹25K → cap is ₹10K."""
        policy = MerchantPolicySnapshot(
            version="v1.0",
            max_auto_recovery_amount=500_000_00,
            max_concession_percent=500,        # 5%
            max_concession_amount=25_000_00,    # ₹25,000
            max_touchpoints=3,
            touchpoint_window_days=14,
        )
        assessment = FinancialAssessmentSnapshot(
            status="CALCULATED",
            gross_invoice_amount_minor=200_000_00,  # ₹2L
            collectible_amount_minor=200_000_00,
            safely_recoverable_amount_minor=200_000_00,
            verified_recovered_amount_minor=0,
            remaining_amount_minor=200_000_00,
        )
        inp = _make_input(
            policy=policy,
            assessment=assessment,
            proposed_amount=100_000_00,
            action_type=RecoveryActionType.APPLY_CONCESSION,
            concession_amount=15_000_00,    # ₹15,000 > ₹10,000 (5% of ₹2L)
            invoice_amount=200_000_00,
        )
        result = engine.evaluate(inp)
        assert result.decision == PolicyDecisionResult.HUMAN_APPROVAL_REQUIRED
        assert result.reason_code == PolicyReasonCode.CONCESSION_EXCEEDS_AUTO_CAP


# =========================================================================
# 10. Missing/invalid policy data
# =========================================================================

class TestMissingPolicyData:
    """Missing or unavailable policy configuration."""

    def test_missing_policy_blocked(
        self,
        engine: PolicyEngineService,
        canonical_assessment: FinancialAssessmentSnapshot,
    ) -> None:
        """Missing merchant policy → BLOCKED (fail closed)."""
        inp = _make_input(
            policy=None,
            assessment=canonical_assessment,
            proposed_amount=100_000_00,
        )
        result = engine.evaluate(inp)
        assert result.decision == PolicyDecisionResult.BLOCKED
        assert result.reason_code == PolicyReasonCode.MISSING_POLICY
        assert result.policy_version == "UNAVAILABLE"

    def test_missing_both_policy_and_assessment(
        self,
        engine: PolicyEngineService,
    ) -> None:
        """Missing both → fail closed (legal check first, then policy, then assessment)."""
        inp = _make_input(
            policy=None,
            assessment=None,
            proposed_amount=100_000_00,
        )
        result = engine.evaluate(inp)
        assert result.decision == PolicyDecisionResult.BLOCKED
        assert result.reason_code == PolicyReasonCode.MISSING_POLICY


# =========================================================================
# 11. Deterministic repeatability
# =========================================================================

class TestDeterministicRepeatability:
    """Same inputs must produce same outputs."""

    def test_same_inputs_same_output(
        self,
        engine: PolicyEngineService,
        default_policy: MerchantPolicySnapshot,
        canonical_assessment: FinancialAssessmentSnapshot,
    ) -> None:
        """Identical evaluation calls must be deterministic."""
        inp = _make_input(
            policy=default_policy,
            assessment=canonical_assessment,
            proposed_amount=900_000_00,
        )
        r1 = engine.evaluate(inp)
        r2 = engine.evaluate(inp)
        assert r1.decision == r2.decision
        assert r1.reason_code == r2.reason_code
        assert r1.checks == r2.checks
        assert r1.policy_version == r2.policy_version

    def test_different_amounts_different_decisions(
        self,
        engine: PolicyEngineService,
        default_policy: MerchantPolicySnapshot,
    ) -> None:
        """Different amounts yield appropriate different decisions."""
        assessment = FinancialAssessmentSnapshot(
            status="CALCULATED",
            gross_invoice_amount_minor=900_000_00,
            collectible_amount_minor=900_000_00,
            safely_recoverable_amount_minor=900_000_00,
            verified_recovered_amount_minor=0,
            remaining_amount_minor=900_000_00,
        )
        # Within authority
        r_under = engine.evaluate(_make_input(
            policy=default_policy, assessment=assessment, proposed_amount=400_000_00,
        ))
        # Over authority
        r_over = engine.evaluate(_make_input(
            policy=default_policy, assessment=assessment, proposed_amount=600_000_00,
        ))
        assert r_under.decision == PolicyDecisionResult.APPROVED
        assert r_over.decision == PolicyDecisionResult.HUMAN_APPROVAL_REQUIRED


# =========================================================================
# 12. No financial arithmetic duplication
# =========================================================================

class TestNoFinancialArithmetic:
    """Policy Engine must NOT independently calculate financial amounts."""

    def test_no_financial_calculation_in_source(self) -> None:
        import inspect

        import app.services.policy_engine as pe_module

        source = inspect.getsource(pe_module)
        # Should not contain formulas that recalculate collectible/disputed/remaining
        calc_patterns = [
            "gross_invoice_amount_minor -",
            "current_outstanding =",
            "collectible =",  # assignment that calculates it
        ]
        for pattern in calc_patterns:
            assert pattern not in source, (
                f"Policy engine should not contain financial calculation: {pattern}"
            )


# =========================================================================
# 13. No AI/Razorpay/DB side effects
# =========================================================================

class TestNoDependencies:
    """Policy Engine has no AI, Razorpay, or DB dependencies."""

    def test_no_ai_imports(self) -> None:
        import inspect

        import app.services.policy_engine as pe_module

        source = inspect.getsource(pe_module)
        import_lines = [
            line.strip()
            for line in source.splitlines()
            if line.strip().startswith(("import ", "from "))
        ]
        import_text = "\n".join(import_lines).lower()
        ai_modules = ["openai", "anthropic", "langchain", "litellm", "transformers"]
        for mod in ai_modules:
            assert mod not in import_text, f"Policy engine imports AI module: {mod}"

    def test_no_razorpay_imports(self) -> None:
        import inspect

        import app.services.policy_engine as pe_module

        source = inspect.getsource(pe_module)
        import_lines = [
            line.strip()
            for line in source.splitlines()
            if line.strip().startswith(("import ", "from "))
        ]
        import_text = "\n".join(import_lines).lower()
        for mod in ["razorpay", "webhook"]:
            assert mod not in import_text, f"Policy engine imports: {mod}"

    def test_no_database_imports(self) -> None:
        import inspect

        import app.services.policy_engine as pe_module

        source = inspect.getsource(pe_module)
        import_lines = [
            line.strip()
            for line in source.splitlines()
            if line.strip().startswith(("import ", "from "))
        ]
        import_text = "\n".join(import_lines).lower()
        for mod in ["sqlalchemy", "asyncpg", "alembic"]:
            assert mod not in import_text, f"Policy engine imports DB module: {mod}"


# =========================================================================
# 14. Rule precedence
# =========================================================================

class TestRulePrecedence:
    """Safety rules must take precedence over lower-priority rules."""

    def test_legal_lock_overrides_amount_check(
        self,
        engine: PolicyEngineService,
        default_policy: MerchantPolicySnapshot,
        canonical_assessment: FinancialAssessmentSnapshot,
    ) -> None:
        """Legal lock takes priority even if amount would be approved."""
        inp = _make_input(
            policy=default_policy,
            assessment=canonical_assessment,
            proposed_amount=100_000_00,
            is_legal_locked=True,
        )
        result = engine.evaluate(inp)
        assert result.decision == PolicyDecisionResult.STOPPED

    def test_evidence_conflict_overrides_amount_check(
        self,
        engine: PolicyEngineService,
        default_policy: MerchantPolicySnapshot,
        canonical_assessment: FinancialAssessmentSnapshot,
    ) -> None:
        """Evidence conflict takes priority over amount eligibility."""
        inp = _make_input(
            policy=default_policy,
            assessment=canonical_assessment,
            proposed_amount=100_000_00,
            evidence_conflict=True,
        )
        result = engine.evaluate(inp)
        assert result.decision == PolicyDecisionResult.BLOCKED
        assert result.reason_code == PolicyReasonCode.EVIDENCE_CONFLICT

    def test_stale_assessment_overrides_amount_check(
        self,
        engine: PolicyEngineService,
        default_policy: MerchantPolicySnapshot,
        canonical_assessment: FinancialAssessmentSnapshot,
    ) -> None:
        """Stale assessment takes priority over amount eligibility."""
        inp = _make_input(
            policy=default_policy,
            assessment=canonical_assessment,
            proposed_amount=100_000_00,
            is_financial_assessment_stale=True,
        )
        result = engine.evaluate(inp)
        assert result.decision == PolicyDecisionResult.BLOCKED
        assert result.reason_code == PolicyReasonCode.STALE_FINANCIAL_ASSESSMENT


# =========================================================================
# 15. PolicyDecision structure
# =========================================================================

class TestPolicyDecisionStructure:
    """Verify PolicyDecision contains required fields for audit."""

    def test_approved_contains_all_fields(
        self,
        engine: PolicyEngineService,
        default_policy: MerchantPolicySnapshot,
        small_assessment: FinancialAssessmentSnapshot,
    ) -> None:
        inp = _make_input(
            policy=default_policy,
            assessment=small_assessment,
            proposed_amount=300_000_00,
        )
        result = engine.evaluate(inp)
        assert isinstance(result, PolicyDecision)
        assert isinstance(result.decision, PolicyDecisionResult)
        assert isinstance(result.reason_code, PolicyReasonCode)
        assert isinstance(result.checks, dict)
        assert isinstance(result.policy_version, str)
        assert result.policy_version == "v1.0"

    def test_blocked_contains_blocking_reason(
        self,
        engine: PolicyEngineService,
        default_policy: MerchantPolicySnapshot,
    ) -> None:
        assessment = FinancialAssessmentSnapshot(
            status="CALCULATED",
            gross_invoice_amount_minor=500_000_00,
            collectible_amount_minor=100_000_00,
            safely_recoverable_amount_minor=100_000_00,
            verified_recovered_amount_minor=0,
            remaining_amount_minor=100_000_00,
        )
        inp = _make_input(
            policy=default_policy,
            assessment=assessment,
            proposed_amount=200_000_00,
        )
        result = engine.evaluate(inp)
        assert result.decision == PolicyDecisionResult.BLOCKED
        assert result.blocking_reason is not None
        assert len(result.blocking_reason) > 0


# =========================================================================
# 16. Outreach touchpoint rules
# =========================================================================

class TestTouchpointRules:
    """Touchpoint limit enforcement for outreach actions."""

    def test_outreach_within_limit_approved(
        self,
        engine: PolicyEngineService,
        default_policy: MerchantPolicySnapshot,
        small_assessment: FinancialAssessmentSnapshot,
    ) -> None:
        """Outreach with 1/3 touchpoints → APPROVED."""
        inp = _make_input(
            policy=default_policy,
            assessment=small_assessment,
            proposed_amount=100_000_00,
            action_type=RecoveryActionType.SEND_REMINDER,
            touchpoints_in_window=1,
            current_time=time(10, 0),  # business hours
        )
        result = engine.evaluate(inp)
        assert result.decision == PolicyDecisionResult.APPROVED

    def test_touchpoint_limit_does_not_apply_to_payment_links(
        self,
        engine: PolicyEngineService,
        default_policy: MerchantPolicySnapshot,
        small_assessment: FinancialAssessmentSnapshot,
    ) -> None:
        """Payment link creation is not an outreach action."""
        inp = _make_input(
            policy=default_policy,
            assessment=small_assessment,
            proposed_amount=100_000_00,
            action_type=RecoveryActionType.CREATE_PAYMENT_LINK,
            touchpoints_in_window=10,  # way over limit
        )
        result = engine.evaluate(inp)
        assert result.decision == PolicyDecisionResult.APPROVED


# =========================================================================
# 17. Edge cases
# =========================================================================

class TestEdgeCases:
    """Edge cases and boundary conditions."""

    def test_verified_assessment_status_accepted(
        self,
        engine: PolicyEngineService,
        default_policy: MerchantPolicySnapshot,
    ) -> None:
        """VERIFIED status is accepted like CALCULATED."""
        assessment = FinancialAssessmentSnapshot(
            status="VERIFIED",
            gross_invoice_amount_minor=300_000_00,
            collectible_amount_minor=300_000_00,
            safely_recoverable_amount_minor=300_000_00,
            verified_recovered_amount_minor=0,
            remaining_amount_minor=300_000_00,
        )
        inp = _make_input(
            policy=default_policy,
            assessment=assessment,
            proposed_amount=300_000_00,
        )
        result = engine.evaluate(inp)
        assert result.decision == PolicyDecisionResult.APPROVED

    def test_policy_review_state_is_valid(
        self,
        engine: PolicyEngineService,
        default_policy: MerchantPolicySnapshot,
        small_assessment: FinancialAssessmentSnapshot,
    ) -> None:
        """POLICY_REVIEW is a valid state for policy evaluation."""
        inp = _make_input(
            policy=default_policy,
            assessment=small_assessment,
            proposed_amount=100_000_00,
            current_state=RecoveryCaseStatus.POLICY_REVIEW,
        )
        result = engine.evaluate(inp)
        assert result.checks["state_valid"] is True

    def test_resolution_ready_state_is_valid(
        self,
        engine: PolicyEngineService,
        default_policy: MerchantPolicySnapshot,
        small_assessment: FinancialAssessmentSnapshot,
    ) -> None:
        """RESOLUTION_READY is a valid state for policy evaluation."""
        inp = _make_input(
            policy=default_policy,
            assessment=small_assessment,
            proposed_amount=100_000_00,
            current_state=RecoveryCaseStatus.RESOLUTION_READY,
        )
        result = engine.evaluate(inp)
        assert result.decision == PolicyDecisionResult.APPROVED

    def test_no_quiet_hours_configured(
        self,
        engine: PolicyEngineService,
        small_assessment: FinancialAssessmentSnapshot,
    ) -> None:
        """No quiet hours in policy → always allowed."""
        policy = MerchantPolicySnapshot(
            version="v1.0",
            max_auto_recovery_amount=500_000_00,
            max_concession_percent=500,
            max_concession_amount=25_000_00,
            max_touchpoints=3,
            touchpoint_window_days=14,
            quiet_hours_start=None,
            quiet_hours_end=None,
        )
        inp = _make_input(
            policy=policy,
            assessment=small_assessment,
            proposed_amount=100_000_00,
            action_type=RecoveryActionType.SEND_REMINDER,
            current_time=time(23, 0),
            touchpoints_in_window=0,
        )
        result = engine.evaluate(inp)
        assert result.decision == PolicyDecisionResult.APPROVED
