"""Deterministic Policy Engine.

Implements the authoritative policy evaluation service as specified in
docs/02-engineering/policy-engine.md.

The Policy Engine sits between AI-generated recommendations and financial
execution. It evaluates whether a proposed recovery action is permitted
given current financial assessment, merchant policy, legal/safety signals,
evidence status, and outreach history.

Rules:
  - Pure deterministic logic only — no LLM/AI.
  - No Razorpay/external I/O.
  - No database mutation.
  - No RecoveryCase state mutation (the State Machine handles transitions).
  - No independent financial calculation (consumes Financial Calculation Service output).
  - Fail-closed on missing/invalid data.
  - AI output/confidence cannot override hard constraints.

Reference: docs/02-engineering/policy-engine.md
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import time
from enum import StrEnum
from typing import Any

from app.domain.enums import PolicyDecisionResult, RecoveryActionType, RecoveryCaseStatus

# ---------------------------------------------------------------------------
# Policy Reason Codes
# ---------------------------------------------------------------------------

class PolicyReasonCode(StrEnum):
    """Reason codes for policy decisions, used for audit and traceability."""

    # APPROVED reasons
    WITHIN_AUTOMATED_AUTHORITY = "WITHIN_AUTOMATED_AUTHORITY"

    # HUMAN_APPROVAL_REQUIRED reasons
    AUTO_RECOVERY_LIMIT_EXCEEDED = "AUTO_RECOVERY_LIMIT_EXCEEDED"
    CONCESSION_EXCEEDS_AUTO_CAP = "CONCESSION_EXCEEDS_AUTO_CAP"
    HIGH_VALUE_ACTION = "HIGH_VALUE_ACTION"

    # DEFERRED reasons
    QUIET_HOURS = "QUIET_HOURS"

    # BLOCKED reasons
    AMOUNT_EXCEEDS_COLLECTIBLE = "AMOUNT_EXCEEDS_COLLECTIBLE"
    AMOUNT_EXCEEDS_SAFELY_RECOVERABLE = "AMOUNT_EXCEEDS_SAFELY_RECOVERABLE"
    MISSING_COLLECTIBLE_AMOUNT = "MISSING_COLLECTIBLE_AMOUNT"
    EVIDENCE_CONFLICT = "EVIDENCE_CONFLICT"
    EVIDENCE_INSUFFICIENT = "EVIDENCE_INSUFFICIENT"
    INVALID_CASE_STATE = "INVALID_CASE_STATE"
    FULLY_RECOVERED_NO_ACTION = "FULLY_RECOVERED_NO_ACTION"
    STALE_FINANCIAL_ASSESSMENT = "STALE_FINANCIAL_ASSESSMENT"
    INVALID_FINANCIAL_ASSESSMENT = "INVALID_FINANCIAL_ASSESSMENT"
    INVALID_PROPOSAL_AMOUNT = "INVALID_PROPOSAL_AMOUNT"
    TOUCHPOINT_LIMIT_EXCEEDED = "TOUCHPOINT_LIMIT_EXCEEDED"
    MISSING_POLICY = "MISSING_POLICY"
    MISSING_FINANCIAL_ASSESSMENT = "MISSING_FINANCIAL_ASSESSMENT"

    # STOPPED reasons
    LEGAL_RISK = "LEGAL_RISK"
    SAFETY_VIOLATION = "SAFETY_VIOLATION"
    SYSTEM_INTEGRITY_FAILURE = "SYSTEM_INTEGRITY_FAILURE"


# ---------------------------------------------------------------------------
# States from which policy-approved recovery execution is valid
# ---------------------------------------------------------------------------

_VALID_EXECUTION_STATES: frozenset[RecoveryCaseStatus] = frozenset({
    RecoveryCaseStatus.POLICY_REVIEW,
    RecoveryCaseStatus.RESOLUTION_READY,
})

# States that are blocked from any autonomous action
_BLOCKED_STATES: frozenset[RecoveryCaseStatus] = frozenset({
    RecoveryCaseStatus.LEGAL_ESCALATION,
    RecoveryCaseStatus.AUTOMATION_LOCKED,
    RecoveryCaseStatus.CLOSED,
    RecoveryCaseStatus.FULLY_RECOVERED,
})

# Action types that involve customer-facing outreach
_OUTREACH_ACTIONS: frozenset[RecoveryActionType] = frozenset({
    RecoveryActionType.SEND_REMINDER,
})

# Action types that involve financial concessions
_CONCESSION_ACTIONS: frozenset[RecoveryActionType] = frozenset({
    RecoveryActionType.APPLY_CONCESSION,
})


# ---------------------------------------------------------------------------
# Policy Input Types
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class MerchantPolicySnapshot:
    """Snapshot of merchant policy configuration for policy evaluation.

    All monetary values are integer minor units (paise).
    The Policy Engine consumes this — it does not look up the DB.
    """

    version: str
    max_auto_recovery_amount: int          # paise
    max_concession_percent: int            # integer basis points: 500 = 5.00%
    max_concession_amount: int             # paise
    max_touchpoints: int
    touchpoint_window_days: int
    quiet_hours_start: time | None = None
    quiet_hours_end: time | None = None
    high_value_threshold: int = 0          # paise
    max_execution_retries: int = 2


@dataclass(frozen=True)
class FinancialAssessmentSnapshot:
    """Snapshot of financial assessment results consumed from Financial Calculation Service.

    The Policy Engine does NOT calculate these values.
    """

    status: str                             # FinancialAssessmentStatus value
    gross_invoice_amount_minor: int         # paise
    collectible_amount_minor: int           # paise
    safely_recoverable_amount_minor: int    # paise
    verified_recovered_amount_minor: int    # paise
    remaining_amount_minor: int             # paise
    currency: str = "INR"
    calculation_version: str = "v1.0"


@dataclass(frozen=True)
class PolicyEvaluationInput:
    """Complete input for a policy evaluation.

    Contains all data the Policy Engine needs. The caller is responsible for
    assembling this from the current case state, proposal, financial assessment,
    merchant policy, outreach history, and legal/safety signals.
    """

    # Current case context
    case_id: str
    current_state: RecoveryCaseStatus

    # Proposed action
    action_type: RecoveryActionType
    proposed_amount: int                    # paise — the recovery/concession amount
    proposal_id: str | None = None

    # Financial assessment (consumed, not calculated)
    financial_assessment: FinancialAssessmentSnapshot | None = None

    # Merchant policy
    merchant_policy: MerchantPolicySnapshot | None = None

    # Evidence status
    evidence_sufficient: bool = False
    evidence_conflict: bool = False

    # Legal/safety flags
    is_legal_locked: bool = False
    is_automation_locked: bool = False
    is_safety_violation: bool = False

    # Outreach history
    touchpoints_in_window: int = 0

    # Current time for quiet-hours evaluation
    current_time: time | None = None

    # Financial assessment staleness
    is_financial_assessment_stale: bool = False

    # Concession amount (for concession actions, in paise)
    concession_amount: int = 0

    # Invoice amount for concession-percent calculation (paise)
    invoice_amount: int = 0

    # Arbitrary metadata
    metadata: dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Policy Decision Result
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class PolicyDecision:
    """Result of a deterministic policy evaluation.

    Contains the decision, reason code, check results, and policy version
    for audit purposes.
    """

    decision: PolicyDecisionResult
    reason_code: PolicyReasonCode
    checks: dict[str, bool]
    policy_version: str
    blocking_reason: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Policy Engine Service
# ---------------------------------------------------------------------------

class PolicyEngineService:
    """Deterministic Policy Engine.

    Pure function-oriented service. Does not mutate database state.
    Does not call any AI/LLM. Does not call Razorpay or any external service.
    Does not calculate financial amounts. Does not change RecoveryCase state.

    Usage:
        engine = PolicyEngineService()
        decision = engine.evaluate(policy_input)
    """

    def evaluate(self, inputs: PolicyEvaluationInput) -> PolicyDecision:
        """Evaluate a proposed recovery action against all policy rules.

        Rules are evaluated in documented precedence order (Section 5 / 28):
          1. Legal / safety stop
          2. System integrity failure
          3. Invalid financial state
          4. Evidence sufficiency / conflict
          5. Valid state check
          6. Validate proposed action / amount
          7. Collectible / safely-recoverable amount checks
          8. Fully-recovered check
          9. Autonomous financial authority
          10. Concession limits
          11. Outreach restrictions
          12. Quiet hours
          13. Return APPROVED

        Returns:
            PolicyDecision with the deterministic result.
        """
        checks: dict[str, bool] = {}

        # --- Rule P-006: Legal / High-Risk Stop (highest priority) ---
        checks["legal_lock"] = inputs.is_legal_locked
        if inputs.is_legal_locked:
            checks["automated_recovery_allowed"] = False
            checks["automated_outreach_allowed"] = False
            return self._stopped(
                PolicyReasonCode.LEGAL_RISK,
                checks,
                inputs,
                "Case has legal lock; all automation is forbidden",
            )

        # --- Safety violation ---
        if inputs.is_safety_violation:
            checks["safety_violation"] = True
            checks["automated_recovery_allowed"] = False
            return self._stopped(
                PolicyReasonCode.SAFETY_VIOLATION,
                checks,
                inputs,
                "Safety violation detected; automation stopped",
            )

        # --- Automation lock ---
        if inputs.is_automation_locked:
            checks["automation_locked"] = True
            checks["automated_recovery_allowed"] = False
            return self._stopped(
                PolicyReasonCode.SYSTEM_INTEGRITY_FAILURE,
                checks,
                inputs,
                "Case is automation locked; execution forbidden",
            )

        # --- Rule P-015: Missing policy fails closed ---
        if inputs.merchant_policy is None:
            checks["policy_available"] = False
            return self._blocked(
                PolicyReasonCode.MISSING_POLICY,
                checks,
                inputs,
                "Merchant policy is unavailable; fail closed",
            )

        policy = inputs.merchant_policy

        # --- Rule P-002 / P-015: Missing financial assessment fails closed ---
        if inputs.financial_assessment is None:
            checks["financial_assessment_available"] = False
            return self._blocked(
                PolicyReasonCode.MISSING_FINANCIAL_ASSESSMENT,
                checks,
                inputs,
                "Financial assessment is unavailable; fail closed",
            )

        assessment = inputs.financial_assessment

        # --- Rule P-020: Stale financial assessment ---
        checks["financial_assessment_current"] = not inputs.is_financial_assessment_stale
        if inputs.is_financial_assessment_stale:
            return self._blocked(
                PolicyReasonCode.STALE_FINANCIAL_ASSESSMENT,
                checks,
                inputs,
                "Financial assessment is stale; revalidation required",
            )

        # --- Check financial assessment status ---
        checks["financial_assessment_verified"] = (
            assessment.status in ("CALCULATED", "VERIFIED")
        )
        if assessment.status == "CONFLICTING":
            checks["evidence_conflict"] = True
            return self._blocked(
                PolicyReasonCode.EVIDENCE_CONFLICT,
                checks,
                inputs,
                "Financial assessment has conflicting evidence; "
                "cannot determine safe recovery amount",
            )
        if assessment.status in ("INSUFFICIENT", "INVALID", "PENDING"):
            checks["financial_assessment_verified"] = False
            return self._blocked(
                PolicyReasonCode.INVALID_FINANCIAL_ASSESSMENT,
                checks,
                inputs,
                f"Financial assessment status is {assessment.status}; "
                "cannot proceed with autonomous recovery",
            )

        # --- Rule P-003: Evidence conflict ---
        checks["evidence_conflict"] = inputs.evidence_conflict
        if inputs.evidence_conflict:
            return self._blocked(
                PolicyReasonCode.EVIDENCE_CONFLICT,
                checks,
                inputs,
                "Material evidence conflict; autonomous recovery forbidden",
            )

        # --- Rule P-002: Evidence sufficiency ---
        checks["evidence_sufficient"] = inputs.evidence_sufficient
        if not inputs.evidence_sufficient:
            return self._blocked(
                PolicyReasonCode.EVIDENCE_INSUFFICIENT,
                checks,
                inputs,
                "Evidence is insufficient for autonomous recovery",
            )

        # --- Rule P-011: Valid state for execution ---
        checks["state_valid"] = inputs.current_state not in _BLOCKED_STATES
        if inputs.current_state in _BLOCKED_STATES:
            return self._blocked(
                PolicyReasonCode.INVALID_CASE_STATE,
                checks,
                inputs,
                f"Case state {inputs.current_state} does not permit recovery execution",
            )

        # --- Validate proposed amount ---
        checks["amount_valid"] = inputs.proposed_amount > 0
        if inputs.proposed_amount <= 0:
            return self._blocked(
                PolicyReasonCode.INVALID_PROPOSAL_AMOUNT,
                checks,
                inputs,
                "Proposed recovery amount must be positive",
            )

        # --- Rule P-002: Collectible amount required ---
        checks["collectible_available"] = assessment.collectible_amount_minor > 0
        if assessment.collectible_amount_minor <= 0:
            return self._blocked(
                PolicyReasonCode.MISSING_COLLECTIBLE_AMOUNT,
                checks,
                inputs,
                "Collectible amount is zero or unavailable; "
                "autonomous recovery not allowed",
            )

        # --- Rule P-001: Recovery amount cannot exceed collectible ---
        checks["amount_supported"] = (
            inputs.proposed_amount <= assessment.collectible_amount_minor
        )
        if inputs.proposed_amount > assessment.collectible_amount_minor:
            return self._blocked(
                PolicyReasonCode.AMOUNT_EXCEEDS_COLLECTIBLE,
                checks,
                inputs,
                f"Proposed amount ({inputs.proposed_amount}) exceeds "
                f"verified collectible ({assessment.collectible_amount_minor})",
            )

        # --- Amount cannot exceed safely recoverable ---
        checks["amount_within_safely_recoverable"] = (
            inputs.proposed_amount <= assessment.safely_recoverable_amount_minor
        )
        if inputs.proposed_amount > assessment.safely_recoverable_amount_minor:
            return self._blocked(
                PolicyReasonCode.AMOUNT_EXCEEDS_SAFELY_RECOVERABLE,
                checks,
                inputs,
                f"Proposed amount ({inputs.proposed_amount}) exceeds "
                f"safely recoverable ({assessment.safely_recoverable_amount_minor})",
            )

        # --- Rule P-019: No recovery after full recovery ---
        checks["not_fully_recovered"] = assessment.remaining_amount_minor > 0
        if assessment.remaining_amount_minor <= 0:
            return self._blocked(
                PolicyReasonCode.FULLY_RECOVERED_NO_ACTION,
                checks,
                inputs,
                "Case is fully recovered; no further recovery actions permitted",
            )

        # --- Rule P-005: Concession limit ---
        if inputs.action_type in _CONCESSION_ACTIONS and inputs.concession_amount > 0:
            max_by_percent = (
                inputs.invoice_amount * policy.max_concession_percent
            ) // 10000  # percent in basis points (500 = 5.00%), so /10000
            max_concession = min(max_by_percent, policy.max_concession_amount)
            checks["concession_limit_ok"] = inputs.concession_amount <= max_concession
            if inputs.concession_amount > max_concession:
                return self._human_approval_required(
                    PolicyReasonCode.CONCESSION_EXCEEDS_AUTO_CAP,
                    checks,
                    inputs,
                    f"Concession ({inputs.concession_amount}) exceeds "
                    f"automatic cap ({max_concession})",
                )
        else:
            checks["concession_limit_ok"] = True

        # --- Rule P-004 / P-009: Autonomous financial authority ---
        checks["auto_limit_ok"] = (
            inputs.proposed_amount <= policy.max_auto_recovery_amount
        )
        if inputs.proposed_amount > policy.max_auto_recovery_amount:
            return self._human_approval_required(
                PolicyReasonCode.AUTO_RECOVERY_LIMIT_EXCEEDED,
                checks,
                inputs,
                f"Proposed amount ({inputs.proposed_amount}) exceeds "
                f"autonomous authority ({policy.max_auto_recovery_amount})",
            )

        # --- Rule P-007: Outreach touchpoint limit ---
        if inputs.action_type in _OUTREACH_ACTIONS:
            checks["touchpoint_limit_ok"] = (
                inputs.touchpoints_in_window < policy.max_touchpoints
            )
            if inputs.touchpoints_in_window >= policy.max_touchpoints:
                return self._blocked(
                    PolicyReasonCode.TOUCHPOINT_LIMIT_EXCEEDED,
                    checks,
                    inputs,
                    f"Touchpoints in window ({inputs.touchpoints_in_window}) "
                    f"reached limit ({policy.max_touchpoints})",
                )
        else:
            checks["touchpoint_limit_ok"] = True

        # --- Rule P-008: Quiet hours ---
        if inputs.action_type in _OUTREACH_ACTIONS and inputs.current_time is not None:
            quiet_ok = self._check_quiet_hours(
                inputs.current_time, policy.quiet_hours_start, policy.quiet_hours_end
            )
            checks["quiet_hours_ok"] = quiet_ok
            if not quiet_ok:
                return self._deferred(
                    PolicyReasonCode.QUIET_HOURS,
                    checks,
                    inputs,
                    "Action deferred due to quiet hours",
                )
        else:
            checks["quiet_hours_ok"] = True

        # --- All checks passed → APPROVED ---
        return PolicyDecision(
            decision=PolicyDecisionResult.APPROVED,
            reason_code=PolicyReasonCode.WITHIN_AUTOMATED_AUTHORITY,
            checks=checks,
            policy_version=policy.version,
            metadata=inputs.metadata,
        )

    # -------------------------------------------------------------------
    # Decision builders
    # -------------------------------------------------------------------

    @staticmethod
    def _stopped(
        reason: PolicyReasonCode,
        checks: dict[str, bool],
        inputs: PolicyEvaluationInput,
        blocking_reason: str,
    ) -> PolicyDecision:
        return PolicyDecision(
            decision=PolicyDecisionResult.STOPPED,
            reason_code=reason,
            checks=checks,
            policy_version=(
                inputs.merchant_policy.version
                if inputs.merchant_policy
                else "UNAVAILABLE"
            ),
            blocking_reason=blocking_reason,
            metadata=inputs.metadata,
        )

    @staticmethod
    def _blocked(
        reason: PolicyReasonCode,
        checks: dict[str, bool],
        inputs: PolicyEvaluationInput,
        blocking_reason: str,
    ) -> PolicyDecision:
        return PolicyDecision(
            decision=PolicyDecisionResult.BLOCKED,
            reason_code=reason,
            checks=checks,
            policy_version=(
                inputs.merchant_policy.version
                if inputs.merchant_policy
                else "UNAVAILABLE"
            ),
            blocking_reason=blocking_reason,
            metadata=inputs.metadata,
        )

    @staticmethod
    def _human_approval_required(
        reason: PolicyReasonCode,
        checks: dict[str, bool],
        inputs: PolicyEvaluationInput,
        blocking_reason: str,
    ) -> PolicyDecision:
        return PolicyDecision(
            decision=PolicyDecisionResult.HUMAN_APPROVAL_REQUIRED,
            reason_code=reason,
            checks=checks,
            policy_version=(
                inputs.merchant_policy.version
                if inputs.merchant_policy
                else "UNAVAILABLE"
            ),
            blocking_reason=blocking_reason,
            metadata=inputs.metadata,
        )

    @staticmethod
    def _deferred(
        reason: PolicyReasonCode,
        checks: dict[str, bool],
        inputs: PolicyEvaluationInput,
        blocking_reason: str,
    ) -> PolicyDecision:
        return PolicyDecision(
            decision=PolicyDecisionResult.DEFERRED,
            reason_code=reason,
            checks=checks,
            policy_version=(
                inputs.merchant_policy.version
                if inputs.merchant_policy
                else "UNAVAILABLE"
            ),
            blocking_reason=blocking_reason,
            metadata=inputs.metadata,
        )

    # -------------------------------------------------------------------
    # Quiet hours evaluation
    # -------------------------------------------------------------------

    @staticmethod
    def _check_quiet_hours(
        current: time,
        start: time | None,
        end: time | None,
    ) -> bool:
        """Return True if current time is OUTSIDE quiet hours (action allowed).

        Handles overnight quiet periods (e.g., 20:00 → 08:00).
        Returns True (ok) if start or end is None (no quiet hours configured).
        """
        if start is None or end is None:
            return True

        if start <= end:
            # Same-day window: e.g., 14:00-18:00
            return not (start <= current < end)
        else:
            # Overnight window: e.g., 20:00-08:00
            return not (current >= start or current < end)
