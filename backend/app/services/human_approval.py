"""Deterministic Human Approval Control Layer.

Implements the approval-control mechanism required when the Policy Engine returns
HUMAN_APPROVAL_REQUIRED (docs/02-engineering/policy-engine.md §15, §30).

A human approval authorizes ONE exact RecoveryAction.  Approval is
cryptographically bound to the action's material parameters via a SHA-256
fingerprint.  Any material change to the action invalidates prior approvals.

Rules:
  - Pure deterministic logic only — no LLM/AI.
  - No Razorpay/external I/O.
  - No database mutation (caller manages persistence).
  - No RecoveryCase state mutation (State Machine handles transitions).
  - No financial calculation (consumes Financial Calculation Service output).
  - No payment execution.
  - Fail-closed on missing/invalid data.

Reference: docs/02-engineering/policy-engine.md §10 (P-010), §14 (P-009)
           docs/02-engineering/state-machine.md §14, §24
           docs/02-engineering/database-schema.md §21
"""

from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import Any

# ---------------------------------------------------------------------------
# Approval Decision (mirrors domain enum, kept local for pure-service use)
# ---------------------------------------------------------------------------

class ApprovalDecision(StrEnum):
    """Decision on a human approval request."""

    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"
    INVALIDATED = "INVALIDATED"


# ---------------------------------------------------------------------------
# Rejection / Failure Reason Codes
# ---------------------------------------------------------------------------

class ApprovalFailureReason(StrEnum):
    """Explicit reasons why an approval validation failed."""

    # Fingerprint binding failures
    FINGERPRINT_MISMATCH = "FINGERPRINT_MISMATCH"
    AMOUNT_MISMATCH = "AMOUNT_MISMATCH"
    CURRENCY_MISMATCH = "CURRENCY_MISMATCH"
    ACTION_TYPE_MISMATCH = "ACTION_TYPE_MISMATCH"
    CASE_MISMATCH = "CASE_MISMATCH"
    ACTION_MISMATCH = "ACTION_MISMATCH"
    CUSTOMER_MISMATCH = "CUSTOMER_MISMATCH"
    INVOICE_MISMATCH = "INVOICE_MISMATCH"
    FINANCIAL_ASSESSMENT_MISMATCH = "FINANCIAL_ASSESSMENT_MISMATCH"
    POLICY_CONTEXT_MISMATCH = "POLICY_CONTEXT_MISMATCH"

    # Status failures
    APPROVAL_NOT_FOUND = "APPROVAL_NOT_FOUND"
    APPROVAL_EXPIRED = "APPROVAL_EXPIRED"
    APPROVAL_REVOKED = "APPROVAL_REVOKED"
    APPROVAL_ALREADY_USED = "APPROVAL_ALREADY_USED"
    APPROVAL_NOT_APPROVED = "APPROVAL_NOT_APPROVED"
    APPROVAL_INVALIDATED = "APPROVAL_INVALIDATED"

    # Structural failures
    DUPLICATE_PENDING_APPROVAL = "DUPLICATE_PENDING_APPROVAL"
    MISSING_REQUIRED_FIELD = "MISSING_REQUIRED_FIELD"
    ACTION_CHANGED_AFTER_APPROVAL = "ACTION_CHANGED_AFTER_APPROVAL"


# ---------------------------------------------------------------------------
# Default approval TTL
# ---------------------------------------------------------------------------

DEFAULT_APPROVAL_TTL = timedelta(hours=24)


# ---------------------------------------------------------------------------
# Action Fingerprint Input
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ActionFingerprintInput:
    """Material fields that constitute the action fingerprint.

    Changing ANY of these fields produces a different fingerprint, which
    invalidates any prior approval bound to the previous fingerprint.

    All monetary amounts are integer minor units (paise).
    """

    case_id: str
    action_type: str
    amount_minor: int
    currency: str
    customer_id: str
    invoice_id: str
    financial_assessment_id: str
    policy_decision_id: str

    def to_canonical_dict(self) -> dict[str, str | int]:
        """Return a canonically ordered dict for deterministic hashing."""
        return {
            "action_type": self.action_type,
            "amount_minor": self.amount_minor,
            "case_id": self.case_id,
            "currency": self.currency,
            "customer_id": self.customer_id,
            "financial_assessment_id": self.financial_assessment_id,
            "invoice_id": self.invoice_id,
            "policy_decision_id": self.policy_decision_id,
        }


# ---------------------------------------------------------------------------
# Approval Request
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ApprovalRequest:
    """Typed input for requesting human approval on a recovery action.

    The caller must provide all material fields so the system can compute
    the action fingerprint and bind the approval to it.
    """

    case_id: str
    action_id: str
    action_type: str
    amount_minor: int
    currency: str
    customer_id: str
    invoice_id: str
    financial_assessment_id: str
    policy_decision_id: str
    requested_by: str
    justification: str | None = None
    ttl: timedelta = DEFAULT_APPROVAL_TTL
    metadata: dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Approval Record (pure domain value object — NOT an ORM model)
# ---------------------------------------------------------------------------

@dataclass
class ApprovalRecord:
    """In-memory representation of a human approval.

    This is a domain value object produced by the service.
    The caller is responsible for persisting it to the ``human_approvals`` table.
    """

    approval_id: str
    case_id: str
    action_id: str
    action_fingerprint: str
    decision: ApprovalDecision
    requested_amount_minor: int
    currency: str
    requested_by: str
    justification: str | None
    created_at: datetime
    expires_at: datetime
    reviewed_by: str | None = None
    reviewed_at: datetime | None = None
    rejection_reason: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Approval Validation Result
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ApprovalValidationResult:
    """Result of validating an approval against a current action state."""

    valid: bool
    approval_id: str | None = None
    failure_reason: ApprovalFailureReason | None = None
    failure_detail: str | None = None


# ---------------------------------------------------------------------------
# Deterministic Fingerprint Generation
# ---------------------------------------------------------------------------

def compute_action_fingerprint(fp_input: ActionFingerprintInput) -> str:
    """Compute a deterministic SHA-256 fingerprint from material action fields.

    The fingerprint is a hex-encoded SHA-256 hash of the JSON-serialised
    canonical dictionary.  Because the dictionary keys are sorted
    alphabetically and the serialisation uses ``sort_keys=True`` with no
    whitespace, identical inputs always produce the same hash.

    This function is pure and stateless.
    """
    canonical = fp_input.to_canonical_dict()
    payload = json.dumps(canonical, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# Human Approval Service
# ---------------------------------------------------------------------------

class HumanApprovalService:
    """Deterministic Human Approval control layer.

    Pure function-oriented service.  Does not mutate database state.
    Does not call any AI/LLM.  Does not call Razorpay or any external service.
    Does not calculate financial amounts.  Does not change RecoveryCase state.
    Does not execute payment.

    Usage::

        service = HumanApprovalService()

        # 1. Create an approval request
        record = service.create_approval_request(request, existing_approvals=[])

        # 2. Approve
        record = service.approve(record, reviewer, fingerprint_input, now)

        # 3. Validate before execution
        result = service.validate_approval(record, fingerprint_input, now)
    """

    # ---------------------------------------------------------------
    # Create approval request
    # ---------------------------------------------------------------

    def create_approval_request(
        self,
        request: ApprovalRequest,
        existing_approvals: list[ApprovalRecord] | None = None,
        now: datetime | None = None,
    ) -> ApprovalRecord:
        """Create a new PENDING approval record bound to an action fingerprint.

        Args:
            request: Typed approval request with all material fields.
            existing_approvals: Existing approval records for the same action.
                If a PENDING approval already exists, raises ``ValueError``.
            now: Current UTC time.  Defaults to ``datetime.now(timezone.utc)``.

        Returns:
            A new ``ApprovalRecord`` with status ``PENDING``.

        Raises:
            ValueError: If a PENDING approval already exists for the action,
                or if required fields are missing.
        """
        if now is None:
            now = datetime.now(UTC)

        # Validate required fields
        self._validate_request_fields(request)

        # Check for duplicate pending approval
        if existing_approvals:
            for existing in existing_approvals:
                if (
                    existing.action_id == request.action_id
                    and existing.decision == ApprovalDecision.PENDING
                ):
                    raise ValueError(
                        f"Duplicate pending approval: approval {existing.approval_id} "
                        f"already exists for action {request.action_id}"
                    )

        # Compute fingerprint
        fp_input = ActionFingerprintInput(
            case_id=request.case_id,
            action_type=request.action_type,
            amount_minor=request.amount_minor,
            currency=request.currency,
            customer_id=request.customer_id,
            invoice_id=request.invoice_id,
            financial_assessment_id=request.financial_assessment_id,
            policy_decision_id=request.policy_decision_id,
        )
        fingerprint = compute_action_fingerprint(fp_input)

        return ApprovalRecord(
            approval_id=str(uuid.uuid4()),
            case_id=request.case_id,
            action_id=request.action_id,
            action_fingerprint=fingerprint,
            decision=ApprovalDecision.PENDING,
            requested_amount_minor=request.amount_minor,
            currency=request.currency,
            requested_by=request.requested_by,
            justification=request.justification,
            created_at=now,
            expires_at=now + request.ttl,
            metadata=dict(request.metadata),
        )

    # ---------------------------------------------------------------
    # Approve
    # ---------------------------------------------------------------

    def approve(
        self,
        record: ApprovalRecord,
        reviewer: str,
        current_fp_input: ActionFingerprintInput,
        now: datetime | None = None,
    ) -> ApprovalRecord:
        """Grant approval on a PENDING record after re-verifying the fingerprint.

        The method re-computes the action fingerprint from ``current_fp_input``
        and ensures it matches the fingerprint stored when the approval was
        requested.  If the action has changed, the approval is INVALIDATED
        instead of APPROVED.

        Args:
            record: The existing PENDING approval record.
            reviewer: Identity of the human reviewer.
            current_fp_input: Current material fields of the action.
            now: Current UTC time.

        Returns:
            Updated ``ApprovalRecord`` (new object — the original is not mutated).

        Raises:
            ValueError: If the record is not in PENDING status or is expired.
        """
        if now is None:
            now = datetime.now(UTC)

        # Must be PENDING
        if record.decision != ApprovalDecision.PENDING:
            raise ValueError(
                f"Cannot approve: approval {record.approval_id} "
                f"is in status {record.decision}, expected PENDING"
            )

        # Must not be expired
        if now >= record.expires_at:
            raise ValueError(
                f"Cannot approve: approval {record.approval_id} has expired "
                f"(expired at {record.expires_at.isoformat()})"
            )

        # Re-verify fingerprint
        current_fingerprint = compute_action_fingerprint(current_fp_input)
        if current_fingerprint != record.action_fingerprint:
            # Action changed — invalidate instead of approving
            return ApprovalRecord(
                approval_id=record.approval_id,
                case_id=record.case_id,
                action_id=record.action_id,
                action_fingerprint=record.action_fingerprint,
                decision=ApprovalDecision.INVALIDATED,
                requested_amount_minor=record.requested_amount_minor,
                currency=record.currency,
                requested_by=record.requested_by,
                justification=record.justification,
                created_at=record.created_at,
                expires_at=record.expires_at,
                reviewed_by=reviewer,
                reviewed_at=now,
                rejection_reason=(
                    "Action fingerprint changed between request and approval; "
                    "prior approval is invalid"
                ),
                metadata=record.metadata,
            )

        return ApprovalRecord(
            approval_id=record.approval_id,
            case_id=record.case_id,
            action_id=record.action_id,
            action_fingerprint=record.action_fingerprint,
            decision=ApprovalDecision.APPROVED,
            requested_amount_minor=record.requested_amount_minor,
            currency=record.currency,
            requested_by=record.requested_by,
            justification=record.justification,
            created_at=record.created_at,
            expires_at=record.expires_at,
            reviewed_by=reviewer,
            reviewed_at=now,
            metadata=record.metadata,
        )

    # ---------------------------------------------------------------
    # Reject
    # ---------------------------------------------------------------

    def reject(
        self,
        record: ApprovalRecord,
        reviewer: str,
        reason: str,
        now: datetime | None = None,
    ) -> ApprovalRecord:
        """Reject a PENDING approval request.

        Args:
            record: The existing PENDING approval record.
            reviewer: Identity of the human reviewer.
            reason: Explicit rejection reason.
            now: Current UTC time.

        Returns:
            Updated ``ApprovalRecord`` with status ``REJECTED``.

        Raises:
            ValueError: If the record is not in PENDING status.
        """
        if now is None:
            now = datetime.now(UTC)

        if record.decision != ApprovalDecision.PENDING:
            raise ValueError(
                f"Cannot reject: approval {record.approval_id} "
                f"is in status {record.decision}, expected PENDING"
            )

        return ApprovalRecord(
            approval_id=record.approval_id,
            case_id=record.case_id,
            action_id=record.action_id,
            action_fingerprint=record.action_fingerprint,
            decision=ApprovalDecision.REJECTED,
            requested_amount_minor=record.requested_amount_minor,
            currency=record.currency,
            requested_by=record.requested_by,
            justification=record.justification,
            created_at=record.created_at,
            expires_at=record.expires_at,
            reviewed_by=reviewer,
            reviewed_at=now,
            rejection_reason=reason,
            metadata=record.metadata,
        )

    # ---------------------------------------------------------------
    # Invalidate / Revoke
    # ---------------------------------------------------------------

    def invalidate(
        self,
        record: ApprovalRecord,
        reason: str,
        now: datetime | None = None,
    ) -> ApprovalRecord:
        """Invalidate an approval (e.g., because the action changed).

        Can invalidate PENDING or APPROVED approvals.
        REJECTED, EXPIRED, and already-INVALIDATED approvals are no-ops
        (returns the record as-is).

        Args:
            record: The approval record to invalidate.
            reason: Explicit invalidation reason.
            now: Current UTC time.

        Returns:
            Updated ``ApprovalRecord`` with status ``INVALIDATED``.
        """
        if now is None:
            now = datetime.now(UTC)

        if record.decision in (
            ApprovalDecision.REJECTED,
            ApprovalDecision.EXPIRED,
            ApprovalDecision.INVALIDATED,
        ):
            return record

        return ApprovalRecord(
            approval_id=record.approval_id,
            case_id=record.case_id,
            action_id=record.action_id,
            action_fingerprint=record.action_fingerprint,
            decision=ApprovalDecision.INVALIDATED,
            requested_amount_minor=record.requested_amount_minor,
            currency=record.currency,
            requested_by=record.requested_by,
            justification=record.justification,
            created_at=record.created_at,
            expires_at=record.expires_at,
            reviewed_by=record.reviewed_by,
            reviewed_at=now,
            rejection_reason=reason,
            metadata=record.metadata,
        )

    # ---------------------------------------------------------------
    # Expire
    # ---------------------------------------------------------------

    def expire_if_needed(
        self,
        record: ApprovalRecord,
        now: datetime | None = None,
    ) -> ApprovalRecord:
        """Transition a PENDING approval to EXPIRED if past its TTL.

        Only affects PENDING approvals.  All other statuses are returned as-is.

        Args:
            record: The approval record.
            now: Current UTC time.

        Returns:
            The (possibly updated) approval record.
        """
        if now is None:
            now = datetime.now(UTC)

        if record.decision != ApprovalDecision.PENDING:
            return record

        if now >= record.expires_at:
            return ApprovalRecord(
                approval_id=record.approval_id,
                case_id=record.case_id,
                action_id=record.action_id,
                action_fingerprint=record.action_fingerprint,
                decision=ApprovalDecision.EXPIRED,
                requested_amount_minor=record.requested_amount_minor,
                currency=record.currency,
                requested_by=record.requested_by,
                justification=record.justification,
                created_at=record.created_at,
                expires_at=record.expires_at,
                reviewed_at=now,
                rejection_reason="Approval expired",
                metadata=record.metadata,
            )

        return record

    # ---------------------------------------------------------------
    # Validate approval for execution
    # ---------------------------------------------------------------

    def validate_approval(
        self,
        approval: ApprovalRecord | None,
        current_fp_input: ActionFingerprintInput,
        now: datetime | None = None,
    ) -> ApprovalValidationResult:
        """Validate that an approval authorizes execution of the exact current action.

        This is the final gate before execution.  It checks:
          1. Approval exists
          2. Approval is in APPROVED status
          3. Approval is not expired
          4. Approval fingerprint matches the current action fingerprint
          5. Case / action IDs match
          6. Amount and currency match

        Args:
            approval: The approval record, or None.
            current_fp_input: Current material fields of the action.
            now: Current UTC time.

        Returns:
            ``ApprovalValidationResult`` with ``valid=True`` or explicit failure.
        """
        if now is None:
            now = datetime.now(UTC)

        # 1. Must exist
        if approval is None:
            return ApprovalValidationResult(
                valid=False,
                failure_reason=ApprovalFailureReason.APPROVAL_NOT_FOUND,
                failure_detail="No approval record found for this action",
            )

        # 2. Must be APPROVED
        if approval.decision == ApprovalDecision.PENDING:
            return ApprovalValidationResult(
                valid=False,
                approval_id=approval.approval_id,
                failure_reason=ApprovalFailureReason.APPROVAL_NOT_APPROVED,
                failure_detail="Approval is still PENDING; not yet reviewed",
            )
        if approval.decision == ApprovalDecision.REJECTED:
            return ApprovalValidationResult(
                valid=False,
                approval_id=approval.approval_id,
                failure_reason=ApprovalFailureReason.APPROVAL_REVOKED,
                failure_detail="Approval was REJECTED",
            )
        if approval.decision == ApprovalDecision.EXPIRED:
            return ApprovalValidationResult(
                valid=False,
                approval_id=approval.approval_id,
                failure_reason=ApprovalFailureReason.APPROVAL_EXPIRED,
                failure_detail="Approval has EXPIRED",
            )
        if approval.decision == ApprovalDecision.INVALIDATED:
            return ApprovalValidationResult(
                valid=False,
                approval_id=approval.approval_id,
                failure_reason=ApprovalFailureReason.APPROVAL_INVALIDATED,
                failure_detail="Approval was INVALIDATED due to action change",
            )
        if approval.decision != ApprovalDecision.APPROVED:
            return ApprovalValidationResult(
                valid=False,
                approval_id=approval.approval_id,
                failure_reason=ApprovalFailureReason.APPROVAL_NOT_APPROVED,
                failure_detail=f"Approval status is {approval.decision}",
            )

        # 3. Must not be expired by clock
        if now >= approval.expires_at:
            return ApprovalValidationResult(
                valid=False,
                approval_id=approval.approval_id,
                failure_reason=ApprovalFailureReason.APPROVAL_EXPIRED,
                failure_detail=(
                    f"Approval expired at {approval.expires_at.isoformat()}"
                ),
            )

        # 4. Case ID must match
        if approval.case_id != current_fp_input.case_id:
            return ApprovalValidationResult(
                valid=False,
                approval_id=approval.approval_id,
                failure_reason=ApprovalFailureReason.CASE_MISMATCH,
                failure_detail=(
                    f"Approval case_id ({approval.case_id}) does not match "
                    f"action case_id ({current_fp_input.case_id})"
                ),
            )

        # 5. Amount must match
        if approval.requested_amount_minor != current_fp_input.amount_minor:
            return ApprovalValidationResult(
                valid=False,
                approval_id=approval.approval_id,
                failure_reason=ApprovalFailureReason.AMOUNT_MISMATCH,
                failure_detail=(
                    f"Approval amount ({approval.requested_amount_minor}) does not match "
                    f"action amount ({current_fp_input.amount_minor})"
                ),
            )

        # 6. Currency must match
        if approval.currency != current_fp_input.currency:
            return ApprovalValidationResult(
                valid=False,
                approval_id=approval.approval_id,
                failure_reason=ApprovalFailureReason.CURRENCY_MISMATCH,
                failure_detail=(
                    f"Approval currency ({approval.currency}) does not match "
                    f"action currency ({current_fp_input.currency})"
                ),
            )

        # 7. Fingerprint must match
        current_fingerprint = compute_action_fingerprint(current_fp_input)
        if approval.action_fingerprint != current_fingerprint:
            return ApprovalValidationResult(
                valid=False,
                approval_id=approval.approval_id,
                failure_reason=ApprovalFailureReason.FINGERPRINT_MISMATCH,
                failure_detail=(
                    "Action fingerprint has changed since approval was granted; "
                    "material action parameters have been modified"
                ),
            )

        # All checks passed
        return ApprovalValidationResult(
            valid=True,
            approval_id=approval.approval_id,
        )

    # ---------------------------------------------------------------
    # Check if action change invalidates approval
    # ---------------------------------------------------------------

    def check_action_changed(
        self,
        approval: ApprovalRecord,
        current_fp_input: ActionFingerprintInput,
    ) -> bool:
        """Return True if the action has materially changed since approval.

        Compares the current fingerprint with the stored approval fingerprint.
        """
        current_fingerprint = compute_action_fingerprint(current_fp_input)
        return approval.action_fingerprint != current_fingerprint

    # ---------------------------------------------------------------
    # Private helpers
    # ---------------------------------------------------------------

    @staticmethod
    def _validate_request_fields(request: ApprovalRequest) -> None:
        """Validate that all required fields are present and valid.

        Raises ValueError with explicit detail on any missing field.
        """
        if not request.case_id:
            raise ValueError("case_id is required for approval request")
        if not request.action_id:
            raise ValueError("action_id is required for approval request")
        if not request.action_type:
            raise ValueError("action_type is required for approval request")
        if request.amount_minor < 0:
            raise ValueError(
                f"amount_minor must be non-negative, got {request.amount_minor}"
            )
        if not request.currency:
            raise ValueError("currency is required for approval request")
        if not request.customer_id:
            raise ValueError("customer_id is required for approval request")
        if not request.invoice_id:
            raise ValueError("invoice_id is required for approval request")
        if not request.financial_assessment_id:
            raise ValueError(
                "financial_assessment_id is required for approval request"
            )
        if not request.policy_decision_id:
            raise ValueError(
                "policy_decision_id is required for approval request"
            )
        if not request.requested_by:
            raise ValueError("requested_by is required for approval request")
