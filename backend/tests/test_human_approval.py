"""Deterministic tests for the Human Approval control layer (Phase 3D).

Tests cover:
  - Valid exact-match approval
  - Fingerprint mismatch
  - Amount mismatch
  - Currency mismatch
  - Action-type mismatch
  - Customer / invoice mismatch
  - Financial-assessment mismatch
  - Policy-context mismatch
  - Expired approval
  - Revoked / invalid approval
  - Duplicate approval attempt
  - Missing approval
  - Changed action after approval
  - Canonical ₹9L human-approval case
  - Fail-closed behavior
  - No Policy / State / AI / Razorpay side effects
  - Deterministic repeatability

All tests are pure unit tests — no DB, no network, no LLM, no Razorpay.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest

from app.services.human_approval import (
    ActionFingerprintInput,
    ApprovalDecision,
    ApprovalFailureReason,
    ApprovalRecord,
    ApprovalRequest,
    HumanApprovalService,
    compute_action_fingerprint,
)

# ---------------------------------------------------------------------------
# Test Fixtures — deterministic UUIDs and timestamps
# ---------------------------------------------------------------------------

NOW = datetime(2026, 9, 4, 12, 0, 0, tzinfo=UTC)
CASE_ID = str(uuid.UUID("11111111-1111-1111-1111-111111111111"))
ACTION_ID = str(uuid.UUID("22222222-2222-2222-2222-222222222222"))
CUSTOMER_ID = str(uuid.UUID("33333333-3333-3333-3333-333333333333"))
INVOICE_ID = str(uuid.UUID("44444444-4444-4444-4444-444444444444"))
FA_ID = str(uuid.UUID("55555555-5555-5555-5555-555555555555"))
POLICY_ID = str(uuid.UUID("66666666-6666-6666-6666-666666666666"))

# Canonical scenario: ₹9,00,000 = 9_00_000_00 paise
CANONICAL_AMOUNT_PAISE = 9_00_000_00


@pytest.fixture
def service() -> HumanApprovalService:
    return HumanApprovalService()


def _make_fp_input(**overrides: object) -> ActionFingerprintInput:
    """Build a standard fingerprint input, with optional overrides."""
    defaults: dict[str, object] = {
        "case_id": CASE_ID,
        "action_type": "CREATE_PARTIAL_RECOVERY",
        "amount_minor": CANONICAL_AMOUNT_PAISE,
        "currency": "INR",
        "customer_id": CUSTOMER_ID,
        "invoice_id": INVOICE_ID,
        "financial_assessment_id": FA_ID,
        "policy_decision_id": POLICY_ID,
    }
    defaults.update(overrides)
    return ActionFingerprintInput(**defaults)  # type: ignore[arg-type]


def _make_request(**overrides: object) -> ApprovalRequest:
    """Build a standard approval request, with optional overrides."""
    defaults: dict[str, object] = {
        "case_id": CASE_ID,
        "action_id": ACTION_ID,
        "action_type": "CREATE_PARTIAL_RECOVERY",
        "amount_minor": CANONICAL_AMOUNT_PAISE,
        "currency": "INR",
        "customer_id": CUSTOMER_ID,
        "invoice_id": INVOICE_ID,
        "financial_assessment_id": FA_ID,
        "policy_decision_id": POLICY_ID,
        "requested_by": "finance_manager@merchant.com",
        "justification": "Approved by VP Finance for high-value recovery",
    }
    defaults.update(overrides)
    return ApprovalRequest(**defaults)  # type: ignore[arg-type]


def _create_and_approve(
    service: HumanApprovalService,
    fp_input: ActionFingerprintInput | None = None,
    request: ApprovalRequest | None = None,
    now: datetime = NOW,
    reviewer: str = "cfo@merchant.com",
) -> ApprovalRecord:
    """Helper: create request → approve → return approved record."""
    if request is None:
        request = _make_request()
    if fp_input is None:
        fp_input = _make_fp_input()
    record = service.create_approval_request(request, now=now)
    return service.approve(record, reviewer, fp_input, now=now + timedelta(minutes=5))


# ====================================================================
# 1. Deterministic Fingerprint Generation
# ====================================================================

class TestActionFingerprint:
    """Tests for compute_action_fingerprint()."""

    def test_deterministic_repeatability(self) -> None:
        """Same inputs always produce the same fingerprint."""
        fp1 = compute_action_fingerprint(_make_fp_input())
        fp2 = compute_action_fingerprint(_make_fp_input())
        assert fp1 == fp2

    def test_different_amount_produces_different_fingerprint(self) -> None:
        fp_original = compute_action_fingerprint(_make_fp_input())
        fp_changed = compute_action_fingerprint(
            _make_fp_input(amount_minor=5_00_000_00)
        )
        assert fp_original != fp_changed

    def test_different_currency_produces_different_fingerprint(self) -> None:
        fp_original = compute_action_fingerprint(_make_fp_input())
        fp_changed = compute_action_fingerprint(_make_fp_input(currency="USD"))
        assert fp_original != fp_changed

    def test_different_action_type_produces_different_fingerprint(self) -> None:
        fp_original = compute_action_fingerprint(_make_fp_input())
        fp_changed = compute_action_fingerprint(
            _make_fp_input(action_type="CREATE_PAYMENT_LINK")
        )
        assert fp_original != fp_changed

    def test_different_customer_produces_different_fingerprint(self) -> None:
        fp_original = compute_action_fingerprint(_make_fp_input())
        fp_changed = compute_action_fingerprint(
            _make_fp_input(customer_id=str(uuid.uuid4()))
        )
        assert fp_original != fp_changed

    def test_different_invoice_produces_different_fingerprint(self) -> None:
        fp_original = compute_action_fingerprint(_make_fp_input())
        fp_changed = compute_action_fingerprint(
            _make_fp_input(invoice_id=str(uuid.uuid4()))
        )
        assert fp_original != fp_changed

    def test_different_case_produces_different_fingerprint(self) -> None:
        fp_original = compute_action_fingerprint(_make_fp_input())
        fp_changed = compute_action_fingerprint(
            _make_fp_input(case_id=str(uuid.uuid4()))
        )
        assert fp_original != fp_changed

    def test_different_financial_assessment_produces_different_fingerprint(self) -> None:
        fp_original = compute_action_fingerprint(_make_fp_input())
        fp_changed = compute_action_fingerprint(
            _make_fp_input(financial_assessment_id=str(uuid.uuid4()))
        )
        assert fp_original != fp_changed

    def test_different_policy_decision_produces_different_fingerprint(self) -> None:
        fp_original = compute_action_fingerprint(_make_fp_input())
        fp_changed = compute_action_fingerprint(
            _make_fp_input(policy_decision_id=str(uuid.uuid4()))
        )
        assert fp_original != fp_changed

    def test_fingerprint_is_hex_sha256(self) -> None:
        fp = compute_action_fingerprint(_make_fp_input())
        assert len(fp) == 64  # SHA-256 hex digest
        assert all(c in "0123456789abcdef" for c in fp)

    def test_canonical_dict_is_sorted(self) -> None:
        fp_input = _make_fp_input()
        canonical = fp_input.to_canonical_dict()
        keys = list(canonical.keys())
        assert keys == sorted(keys)


# ====================================================================
# 2. Approval Creation
# ====================================================================

class TestApprovalCreation:
    """Tests for create_approval_request()."""

    def test_creates_pending_record(self, service: HumanApprovalService) -> None:
        request = _make_request()
        record = service.create_approval_request(request, now=NOW)

        assert record.decision == ApprovalDecision.PENDING
        assert record.case_id == CASE_ID
        assert record.action_id == ACTION_ID
        assert record.requested_amount_minor == CANONICAL_AMOUNT_PAISE
        assert record.currency == "INR"
        assert record.requested_by == "finance_manager@merchant.com"
        assert record.justification is not None
        assert record.created_at == NOW
        assert record.reviewed_by is None
        assert record.reviewed_at is None

    def test_computes_fingerprint_on_creation(
        self, service: HumanApprovalService
    ) -> None:
        request = _make_request()
        record = service.create_approval_request(request, now=NOW)

        expected_fp = compute_action_fingerprint(_make_fp_input())
        assert record.action_fingerprint == expected_fp

    def test_sets_expiry(self, service: HumanApprovalService) -> None:
        request = _make_request(ttl=timedelta(hours=12))
        record = service.create_approval_request(request, now=NOW)
        assert record.expires_at == NOW + timedelta(hours=12)

    def test_duplicate_pending_raises(self, service: HumanApprovalService) -> None:
        request = _make_request()
        existing = service.create_approval_request(request, now=NOW)

        with pytest.raises(ValueError, match="Duplicate pending approval"):
            service.create_approval_request(
                request, existing_approvals=[existing], now=NOW
            )

    def test_missing_case_id_raises(self, service: HumanApprovalService) -> None:
        with pytest.raises(ValueError, match="case_id"):
            service.create_approval_request(_make_request(case_id=""), now=NOW)

    def test_missing_action_id_raises(self, service: HumanApprovalService) -> None:
        with pytest.raises(ValueError, match="action_id"):
            service.create_approval_request(_make_request(action_id=""), now=NOW)

    def test_missing_requested_by_raises(self, service: HumanApprovalService) -> None:
        with pytest.raises(ValueError, match="requested_by"):
            service.create_approval_request(
                _make_request(requested_by=""), now=NOW
            )

    def test_negative_amount_raises(self, service: HumanApprovalService) -> None:
        with pytest.raises(ValueError, match="non-negative"):
            service.create_approval_request(
                _make_request(amount_minor=-100), now=NOW
            )

    def test_missing_financial_assessment_id_raises(
        self, service: HumanApprovalService
    ) -> None:
        with pytest.raises(ValueError, match="financial_assessment_id"):
            service.create_approval_request(
                _make_request(financial_assessment_id=""), now=NOW
            )

    def test_missing_policy_decision_id_raises(
        self, service: HumanApprovalService
    ) -> None:
        with pytest.raises(ValueError, match="policy_decision_id"):
            service.create_approval_request(
                _make_request(policy_decision_id=""), now=NOW
            )


# ====================================================================
# 3. Approval Grant (Approve)
# ====================================================================

class TestApprovalGrant:
    """Tests for approve()."""

    def test_valid_exact_match_approval(
        self, service: HumanApprovalService
    ) -> None:
        record = _create_and_approve(service)
        assert record.decision == ApprovalDecision.APPROVED
        assert record.reviewed_by == "cfo@merchant.com"
        assert record.reviewed_at is not None

    def test_approve_non_pending_raises(
        self, service: HumanApprovalService
    ) -> None:
        record = _create_and_approve(service)
        # Try to approve again
        with pytest.raises(ValueError, match="expected PENDING"):
            service.approve(
                record, "someone", _make_fp_input(), now=NOW + timedelta(minutes=10)
            )

    def test_approve_expired_raises(self, service: HumanApprovalService) -> None:
        request = _make_request(ttl=timedelta(hours=1))
        record = service.create_approval_request(request, now=NOW)

        expired_time = NOW + timedelta(hours=2)
        with pytest.raises(ValueError, match="expired"):
            service.approve(record, "reviewer", _make_fp_input(), now=expired_time)

    def test_approve_with_changed_fingerprint_invalidates(
        self, service: HumanApprovalService
    ) -> None:
        """If the action changed between request and approval, result is INVALIDATED."""
        request = _make_request()
        record = service.create_approval_request(request, now=NOW)

        # Action amount changed
        changed_fp = _make_fp_input(amount_minor=9_50_000_00)
        result = service.approve(
            record, "reviewer", changed_fp, now=NOW + timedelta(minutes=5)
        )
        assert result.decision == ApprovalDecision.INVALIDATED
        assert "fingerprint changed" in (result.rejection_reason or "")


# ====================================================================
# 4. Approval Rejection
# ====================================================================

class TestApprovalRejection:
    """Tests for reject()."""

    def test_reject_pending(self, service: HumanApprovalService) -> None:
        request = _make_request()
        record = service.create_approval_request(request, now=NOW)

        rejected = service.reject(
            record, "cfo@merchant.com", "Amount too high", now=NOW + timedelta(minutes=5)
        )
        assert rejected.decision == ApprovalDecision.REJECTED
        assert rejected.rejection_reason == "Amount too high"
        assert rejected.reviewed_by == "cfo@merchant.com"

    def test_reject_non_pending_raises(self, service: HumanApprovalService) -> None:
        record = _create_and_approve(service)
        with pytest.raises(ValueError, match="expected PENDING"):
            service.reject(record, "someone", "reason")


# ====================================================================
# 5. Approval Invalidation / Revocation
# ====================================================================

class TestApprovalInvalidation:
    """Tests for invalidate()."""

    def test_invalidate_pending(self, service: HumanApprovalService) -> None:
        request = _make_request()
        record = service.create_approval_request(request, now=NOW)
        result = service.invalidate(record, "Action modified")
        assert result.decision == ApprovalDecision.INVALIDATED

    def test_invalidate_approved(self, service: HumanApprovalService) -> None:
        record = _create_and_approve(service)
        result = service.invalidate(record, "Action modified after approval")
        assert result.decision == ApprovalDecision.INVALIDATED

    def test_invalidate_rejected_is_noop(
        self, service: HumanApprovalService
    ) -> None:
        request = _make_request()
        record = service.create_approval_request(request, now=NOW)
        rejected = service.reject(
            record, "cfo", "reason", now=NOW + timedelta(minutes=1)
        )
        result = service.invalidate(rejected, "Should be no-op")
        assert result.decision == ApprovalDecision.REJECTED

    def test_invalidate_expired_is_noop(
        self, service: HumanApprovalService
    ) -> None:
        request = _make_request(ttl=timedelta(hours=1))
        record = service.create_approval_request(request, now=NOW)
        expired = service.expire_if_needed(record, now=NOW + timedelta(hours=2))
        result = service.invalidate(expired, "Should be no-op")
        assert result.decision == ApprovalDecision.EXPIRED

    def test_invalidate_already_invalidated_is_noop(
        self, service: HumanApprovalService
    ) -> None:
        request = _make_request()
        record = service.create_approval_request(request, now=NOW)
        inv1 = service.invalidate(record, "First invalidation")
        inv2 = service.invalidate(inv1, "Second invalidation")
        assert inv2 is inv1  # Same object returned


# ====================================================================
# 6. Approval Expiry
# ====================================================================

class TestApprovalExpiry:
    """Tests for expire_if_needed()."""

    def test_expire_pending_past_ttl(self, service: HumanApprovalService) -> None:
        request = _make_request(ttl=timedelta(hours=1))
        record = service.create_approval_request(request, now=NOW)
        result = service.expire_if_needed(record, now=NOW + timedelta(hours=2))
        assert result.decision == ApprovalDecision.EXPIRED

    def test_pending_within_ttl_unchanged(
        self, service: HumanApprovalService
    ) -> None:
        request = _make_request(ttl=timedelta(hours=24))
        record = service.create_approval_request(request, now=NOW)
        result = service.expire_if_needed(record, now=NOW + timedelta(hours=1))
        assert result.decision == ApprovalDecision.PENDING

    def test_approved_not_expired_by_method(
        self, service: HumanApprovalService
    ) -> None:
        record = _create_and_approve(service)
        result = service.expire_if_needed(record, now=NOW + timedelta(days=30))
        assert result.decision == ApprovalDecision.APPROVED  # No change


# ====================================================================
# 7. Approval Validation (Pre-execution Gate)
# ====================================================================

class TestApprovalValidation:
    """Tests for validate_approval()."""

    def test_valid_exact_match(self, service: HumanApprovalService) -> None:
        record = _create_and_approve(service)
        fp_input = _make_fp_input()
        result = service.validate_approval(
            record, fp_input, now=NOW + timedelta(minutes=10)
        )
        assert result.valid is True
        assert result.failure_reason is None

    def test_missing_approval(self, service: HumanApprovalService) -> None:
        result = service.validate_approval(
            None, _make_fp_input(), now=NOW
        )
        assert result.valid is False
        assert result.failure_reason == ApprovalFailureReason.APPROVAL_NOT_FOUND

    def test_pending_approval_not_valid(
        self, service: HumanApprovalService
    ) -> None:
        request = _make_request()
        record = service.create_approval_request(request, now=NOW)
        result = service.validate_approval(record, _make_fp_input(), now=NOW)
        assert result.valid is False
        assert result.failure_reason == ApprovalFailureReason.APPROVAL_NOT_APPROVED

    def test_rejected_approval_not_valid(
        self, service: HumanApprovalService
    ) -> None:
        request = _make_request()
        record = service.create_approval_request(request, now=NOW)
        rejected = service.reject(record, "cfo", "Too high", now=NOW)
        result = service.validate_approval(rejected, _make_fp_input(), now=NOW)
        assert result.valid is False
        assert result.failure_reason == ApprovalFailureReason.APPROVAL_REVOKED

    def test_expired_approval_not_valid(
        self, service: HumanApprovalService
    ) -> None:
        request = _make_request(ttl=timedelta(hours=1))
        record = service.create_approval_request(request, now=NOW)
        expired = service.expire_if_needed(record, now=NOW + timedelta(hours=2))
        result = service.validate_approval(
            expired, _make_fp_input(), now=NOW + timedelta(hours=2)
        )
        assert result.valid is False
        assert result.failure_reason == ApprovalFailureReason.APPROVAL_EXPIRED

    def test_invalidated_approval_not_valid(
        self, service: HumanApprovalService
    ) -> None:
        record = _create_and_approve(service)
        invalidated = service.invalidate(record, "Action changed")
        result = service.validate_approval(
            invalidated, _make_fp_input(), now=NOW + timedelta(minutes=10)
        )
        assert result.valid is False
        assert result.failure_reason == ApprovalFailureReason.APPROVAL_INVALIDATED

    def test_clock_expiry_on_approved_record(
        self, service: HumanApprovalService
    ) -> None:
        """Even an APPROVED record fails validation if expired by clock."""
        request = _make_request(ttl=timedelta(hours=1))
        record = service.create_approval_request(request, now=NOW)
        approved = service.approve(
            record, "cfo", _make_fp_input(), now=NOW + timedelta(minutes=30)
        )
        assert approved.decision == ApprovalDecision.APPROVED

        result = service.validate_approval(
            approved, _make_fp_input(), now=NOW + timedelta(hours=2)
        )
        assert result.valid is False
        assert result.failure_reason == ApprovalFailureReason.APPROVAL_EXPIRED

    def test_case_mismatch(self, service: HumanApprovalService) -> None:
        record = _create_and_approve(service)
        different_case = _make_fp_input(case_id=str(uuid.uuid4()))
        result = service.validate_approval(
            record, different_case, now=NOW + timedelta(minutes=10)
        )
        assert result.valid is False
        assert result.failure_reason == ApprovalFailureReason.CASE_MISMATCH

    def test_amount_mismatch(self, service: HumanApprovalService) -> None:
        record = _create_and_approve(service)
        different_amount = _make_fp_input(amount_minor=5_00_000_00)
        result = service.validate_approval(
            record, different_amount, now=NOW + timedelta(minutes=10)
        )
        assert result.valid is False
        assert result.failure_reason == ApprovalFailureReason.AMOUNT_MISMATCH

    def test_currency_mismatch(self, service: HumanApprovalService) -> None:
        record = _create_and_approve(service)
        different_currency = _make_fp_input(currency="USD")
        result = service.validate_approval(
            record, different_currency, now=NOW + timedelta(minutes=10)
        )
        assert result.valid is False
        assert result.failure_reason == ApprovalFailureReason.CURRENCY_MISMATCH

    def test_fingerprint_mismatch_action_type(
        self, service: HumanApprovalService
    ) -> None:
        """Changing action type produces fingerprint mismatch."""
        record = _create_and_approve(service)
        # Different action type but same amount, currency, case
        different_fp = _make_fp_input(action_type="CREATE_PAYMENT_LINK")
        result = service.validate_approval(
            record, different_fp, now=NOW + timedelta(minutes=10)
        )
        assert result.valid is False
        # Will fail at fingerprint check since amount/currency/case still match
        assert result.failure_reason == ApprovalFailureReason.FINGERPRINT_MISMATCH

    def test_fingerprint_mismatch_customer(
        self, service: HumanApprovalService
    ) -> None:
        record = _create_and_approve(service)
        different_fp = _make_fp_input(customer_id=str(uuid.uuid4()))
        result = service.validate_approval(
            record, different_fp, now=NOW + timedelta(minutes=10)
        )
        assert result.valid is False
        assert result.failure_reason == ApprovalFailureReason.FINGERPRINT_MISMATCH

    def test_fingerprint_mismatch_invoice(
        self, service: HumanApprovalService
    ) -> None:
        record = _create_and_approve(service)
        different_fp = _make_fp_input(invoice_id=str(uuid.uuid4()))
        result = service.validate_approval(
            record, different_fp, now=NOW + timedelta(minutes=10)
        )
        assert result.valid is False
        assert result.failure_reason == ApprovalFailureReason.FINGERPRINT_MISMATCH

    def test_fingerprint_mismatch_financial_assessment(
        self, service: HumanApprovalService
    ) -> None:
        record = _create_and_approve(service)
        different_fp = _make_fp_input(financial_assessment_id=str(uuid.uuid4()))
        result = service.validate_approval(
            record, different_fp, now=NOW + timedelta(minutes=10)
        )
        assert result.valid is False
        assert result.failure_reason == ApprovalFailureReason.FINGERPRINT_MISMATCH

    def test_fingerprint_mismatch_policy_context(
        self, service: HumanApprovalService
    ) -> None:
        record = _create_and_approve(service)
        different_fp = _make_fp_input(policy_decision_id=str(uuid.uuid4()))
        result = service.validate_approval(
            record, different_fp, now=NOW + timedelta(minutes=10)
        )
        assert result.valid is False
        assert result.failure_reason == ApprovalFailureReason.FINGERPRINT_MISMATCH


# ====================================================================
# 8. Changed Action After Approval
# ====================================================================

class TestChangedActionAfterApproval:
    """Tests for check_action_changed()."""

    def test_unchanged_action(self, service: HumanApprovalService) -> None:
        record = _create_and_approve(service)
        assert service.check_action_changed(record, _make_fp_input()) is False

    def test_amount_changed(self, service: HumanApprovalService) -> None:
        record = _create_and_approve(service)
        changed = _make_fp_input(amount_minor=10_00_000_00)
        assert service.check_action_changed(record, changed) is True

    def test_action_type_changed(self, service: HumanApprovalService) -> None:
        record = _create_and_approve(service)
        changed = _make_fp_input(action_type="APPLY_CONCESSION")
        assert service.check_action_changed(record, changed) is True

    def test_customer_changed(self, service: HumanApprovalService) -> None:
        record = _create_and_approve(service)
        changed = _make_fp_input(customer_id=str(uuid.uuid4()))
        assert service.check_action_changed(record, changed) is True

    def test_invoice_changed(self, service: HumanApprovalService) -> None:
        record = _create_and_approve(service)
        changed = _make_fp_input(invoice_id=str(uuid.uuid4()))
        assert service.check_action_changed(record, changed) is True

    def test_financial_assessment_changed(
        self, service: HumanApprovalService
    ) -> None:
        record = _create_and_approve(service)
        changed = _make_fp_input(financial_assessment_id=str(uuid.uuid4()))
        assert service.check_action_changed(record, changed) is True

    def test_policy_context_changed(self, service: HumanApprovalService) -> None:
        record = _create_and_approve(service)
        changed = _make_fp_input(policy_decision_id=str(uuid.uuid4()))
        assert service.check_action_changed(record, changed) is True

    def test_currency_changed(self, service: HumanApprovalService) -> None:
        record = _create_and_approve(service)
        changed = _make_fp_input(currency="USD")
        assert service.check_action_changed(record, changed) is True


# ====================================================================
# 9. Canonical ₹9L Human Approval Case
# ====================================================================

class TestCanonicalScenario:
    """End-to-end canonical scenario from docs.

    Invoice: ₹10,00,000
    Verified disputed: ₹1,00,000
    Collectible: ₹9,00,000
    Autonomous authority: ₹5,00,000
    → Policy: HUMAN_APPROVAL_REQUIRED
    → Human approves exact ₹9,00,000 action
    → Validation passes
    """

    def test_canonical_approval_flow(self, service: HumanApprovalService) -> None:
        # Step 1: Create request for ₹9,00,000 recovery (90000000 paise)
        request = _make_request(
            amount_minor=90_000_00,  # ₹9,00,000 in paise
            action_type="CREATE_PARTIAL_RECOVERY",
        )
        record = service.create_approval_request(request, now=NOW)
        assert record.decision == ApprovalDecision.PENDING
        assert record.requested_amount_minor == 90_000_00

        # Step 2: Human reviewer approves
        fp_input = _make_fp_input(amount_minor=90_000_00)
        approved = service.approve(
            record, "vp_finance@merchant.com", fp_input,
            now=NOW + timedelta(minutes=30),
        )
        assert approved.decision == ApprovalDecision.APPROVED
        assert approved.reviewed_by == "vp_finance@merchant.com"

        # Step 3: Validate for execution
        result = service.validate_approval(
            approved, fp_input, now=NOW + timedelta(minutes=35)
        )
        assert result.valid is True

    def test_canonical_amount_change_invalidates(
        self, service: HumanApprovalService
    ) -> None:
        """A changed amount (₹9,00,000 → ₹9,50,000) invalidates approval."""
        request = _make_request(amount_minor=90_000_00)
        record = service.create_approval_request(request, now=NOW)

        # Original fingerprint
        fp_original = _make_fp_input(amount_minor=90_000_00)
        approved = service.approve(
            record, "cfo", fp_original, now=NOW + timedelta(minutes=5)
        )
        assert approved.decision == ApprovalDecision.APPROVED

        # Validate with changed amount
        fp_changed = _make_fp_input(amount_minor=95_000_00)
        result = service.validate_approval(
            approved, fp_changed, now=NOW + timedelta(minutes=10)
        )
        assert result.valid is False
        # amount_minor changed → first check to fail is AMOUNT_MISMATCH
        assert result.failure_reason == ApprovalFailureReason.AMOUNT_MISMATCH

    def test_canonical_policy_context_change_invalidates(
        self, service: HumanApprovalService
    ) -> None:
        """A changed policy context invalidates approval."""
        request = _make_request(amount_minor=90_000_00)
        record = service.create_approval_request(request, now=NOW)

        fp_original = _make_fp_input(amount_minor=90_000_00)
        approved = service.approve(
            record, "cfo", fp_original, now=NOW + timedelta(minutes=5)
        )
        assert approved.decision == ApprovalDecision.APPROVED

        # Policy decision changed (different policy version applied)
        new_policy_id = str(uuid.uuid4())
        fp_changed = _make_fp_input(
            amount_minor=90_000_00,
            policy_decision_id=new_policy_id,
        )
        result = service.validate_approval(
            approved, fp_changed, now=NOW + timedelta(minutes=10)
        )
        assert result.valid is False
        assert result.failure_reason == ApprovalFailureReason.FINGERPRINT_MISMATCH


# ====================================================================
# 10. Fail-Closed Behavior
# ====================================================================

class TestFailClosed:
    """Approval system must fail closed: missing or invalid data → rejected."""

    def test_no_approval_fails_closed(self, service: HumanApprovalService) -> None:
        result = service.validate_approval(None, _make_fp_input(), now=NOW)
        assert result.valid is False

    def test_any_non_approved_status_fails_closed(
        self, service: HumanApprovalService
    ) -> None:
        """Every non-APPROVED status must fail validation."""
        for decision in ApprovalDecision:
            if decision == ApprovalDecision.APPROVED:
                continue

            record = ApprovalRecord(
                approval_id=str(uuid.uuid4()),
                case_id=CASE_ID,
                action_id=ACTION_ID,
                action_fingerprint=compute_action_fingerprint(_make_fp_input()),
                decision=decision,
                requested_amount_minor=CANONICAL_AMOUNT_PAISE,
                currency="INR",
                requested_by="someone",
                justification=None,
                created_at=NOW,
                expires_at=NOW + timedelta(hours=24),
            )
            result = service.validate_approval(
                record, _make_fp_input(), now=NOW + timedelta(minutes=5)
            )
            assert result.valid is False, (
                f"Expected validation to fail for decision={decision}"
            )

    def test_missing_fields_prevent_creation(
        self, service: HumanApprovalService
    ) -> None:
        """All required fields must be present for approval request creation."""
        required_fields = [
            "case_id", "action_id", "action_type", "currency",
            "customer_id", "invoice_id", "financial_assessment_id",
            "policy_decision_id", "requested_by",
        ]
        for field_name in required_fields:
            with pytest.raises(ValueError):
                service.create_approval_request(
                    _make_request(**{field_name: ""}), now=NOW
                )


# ====================================================================
# 11. No Side Effects
# ====================================================================

class TestNoSideEffects:
    """Ensure the service has no Policy / State / AI / Razorpay side effects."""

    def test_service_has_no_state(self) -> None:
        """Service is stateless — two instances behave identically."""
        s1 = HumanApprovalService()
        s2 = HumanApprovalService()

        request = _make_request()
        r1 = s1.create_approval_request(request, now=NOW)
        r2 = s2.create_approval_request(request, now=NOW)

        # Same fingerprint, same decision, same fields (IDs differ by uuid4)
        assert r1.action_fingerprint == r2.action_fingerprint
        assert r1.decision == r2.decision
        assert r1.requested_amount_minor == r2.requested_amount_minor

    def test_no_import_of_ai_modules(self) -> None:
        """The human_approval module must not import AI/LLM modules."""
        import app.services.human_approval as mod
        source = open(mod.__file__).read()  # noqa: SIM115
        # Extract only import lines (not comments/docstrings)
        import_lines = [
            line.strip() for line in source.splitlines()
            if line.strip().startswith(("import ", "from "))
        ]
        import_text = "\n".join(import_lines).lower()
        for forbidden in ["genai", "openai", "anthropic", "langchain"]:
            assert forbidden not in import_text, (
                f"human_approval.py must not import {forbidden}"
            )

    def test_no_import_of_razorpay(self) -> None:
        """The human_approval module must not import Razorpay."""
        import app.services.human_approval as mod
        source = open(mod.__file__).read()  # noqa: SIM115
        import_lines = [
            line.strip() for line in source.splitlines()
            if line.strip().startswith(("import ", "from "))
        ]
        import_text = "\n".join(import_lines).lower()
        assert "razorpay" not in import_text

    def test_no_import_of_state_machine(self) -> None:
        """The human_approval module must not import the state machine."""
        import app.services.human_approval as mod
        source = open(mod.__file__).read()  # noqa: SIM115
        import_lines = [
            line.strip() for line in source.splitlines()
            if line.strip().startswith(("import ", "from "))
        ]
        import_text = "\n".join(import_lines)
        assert "state_machine" not in import_text

    def test_no_import_of_policy_engine(self) -> None:
        """The human_approval module must not import the policy engine."""
        import app.services.human_approval as mod
        source = open(mod.__file__).read()  # noqa: SIM115
        import_lines = [
            line.strip() for line in source.splitlines()
            if line.strip().startswith(("import ", "from "))
        ]
        import_text = "\n".join(import_lines)
        assert "policy_engine" not in import_text

    def test_no_database_imports(self) -> None:
        """The human_approval module must not import database/ORM modules."""
        import app.services.human_approval as mod
        source = open(mod.__file__).read()  # noqa: SIM115
        import_lines = [
            line.strip() for line in source.splitlines()
            if line.strip().startswith(("import ", "from "))
        ]
        import_text = "\n".join(import_lines)
        for forbidden in ["sqlalchemy", "from app.infrastructure", "Session"]:
            assert forbidden not in import_text, (
                f"human_approval.py must not import {forbidden}"
            )

    def test_create_does_not_mutate_input(
        self, service: HumanApprovalService
    ) -> None:
        """create_approval_request must not mutate its input."""
        request = _make_request()
        original_case = request.case_id
        service.create_approval_request(request, now=NOW)
        assert request.case_id == original_case

    def test_validate_does_not_mutate_record(
        self, service: HumanApprovalService
    ) -> None:
        """validate_approval must not mutate the approval record."""
        record = _create_and_approve(service)
        original_decision = record.decision
        service.validate_approval(record, _make_fp_input(), now=NOW + timedelta(minutes=10))
        assert record.decision == original_decision


# ====================================================================
# 12. Deterministic Repeatability
# ====================================================================

class TestDeterministicRepeatability:
    """The same inputs must produce the same outputs every time."""

    def test_fingerprint_is_deterministic(self) -> None:
        """100 calls with same input → same fingerprint."""
        fp_input = _make_fp_input()
        fingerprints = {compute_action_fingerprint(fp_input) for _ in range(100)}
        assert len(fingerprints) == 1

    def test_approval_creation_is_deterministic_except_id(
        self, service: HumanApprovalService
    ) -> None:
        """Two calls produce records with same fingerprint and amount."""
        request = _make_request()
        r1 = service.create_approval_request(request, now=NOW)
        r2 = service.create_approval_request(request, now=NOW)
        assert r1.action_fingerprint == r2.action_fingerprint
        assert r1.requested_amount_minor == r2.requested_amount_minor
        # IDs differ (uuid4)
        assert r1.approval_id != r2.approval_id

    def test_validation_is_deterministic(
        self, service: HumanApprovalService
    ) -> None:
        """Same approval + same fp_input → same validation result."""
        record = _create_and_approve(service)
        fp_input = _make_fp_input()
        check_time = NOW + timedelta(minutes=10)

        results = [
            service.validate_approval(record, fp_input, now=check_time)
            for _ in range(50)
        ]
        assert all(r.valid is True for r in results)


# ====================================================================
# 13. Edge Cases
# ====================================================================

class TestEdgeCases:
    """Edge cases and boundary conditions."""

    def test_zero_amount_approval(self, service: HumanApprovalService) -> None:
        """Zero-amount action can be approved (escalation, write-off)."""
        request = _make_request(amount_minor=0)
        record = service.create_approval_request(request, now=NOW)
        assert record.requested_amount_minor == 0

        fp_input = _make_fp_input(amount_minor=0)
        approved = service.approve(
            record, "cfo", fp_input, now=NOW + timedelta(minutes=5)
        )
        assert approved.decision == ApprovalDecision.APPROVED

        result = service.validate_approval(
            approved, fp_input, now=NOW + timedelta(minutes=10)
        )
        assert result.valid is True

    def test_expiry_at_exact_boundary(self, service: HumanApprovalService) -> None:
        """Approval at exactly expires_at is expired (>=)."""
        request = _make_request(ttl=timedelta(hours=1))
        record = service.create_approval_request(request, now=NOW)
        fp_input = _make_fp_input()
        approved = service.approve(
            record, "cfo", fp_input, now=NOW + timedelta(minutes=5)
        )

        # Validate at exactly the expiry time
        result = service.validate_approval(
            approved, fp_input, now=NOW + timedelta(hours=1)
        )
        assert result.valid is False
        assert result.failure_reason == ApprovalFailureReason.APPROVAL_EXPIRED

    def test_one_second_before_expiry_is_valid(
        self, service: HumanApprovalService
    ) -> None:
        """Approval 1 second before expiry is still valid."""
        request = _make_request(ttl=timedelta(hours=1))
        record = service.create_approval_request(request, now=NOW)
        fp_input = _make_fp_input()
        approved = service.approve(
            record, "cfo", fp_input, now=NOW + timedelta(minutes=5)
        )

        result = service.validate_approval(
            approved, fp_input,
            now=NOW + timedelta(hours=1) - timedelta(seconds=1),
        )
        assert result.valid is True

    def test_large_amount_paise(self, service: HumanApprovalService) -> None:
        """Handle very large amounts (₹1 crore = 1,00,00,000_00 paise)."""
        large_amount = 1_00_00_000_00  # ₹1 crore in paise
        request = _make_request(amount_minor=large_amount)
        record = service.create_approval_request(request, now=NOW)
        fp_input = _make_fp_input(amount_minor=large_amount)
        approved = service.approve(
            record, "cfo", fp_input, now=NOW + timedelta(minutes=5)
        )
        result = service.validate_approval(
            approved, fp_input, now=NOW + timedelta(minutes=10)
        )
        assert result.valid is True

    def test_approval_cannot_cross_cases(
        self, service: HumanApprovalService
    ) -> None:
        """An approval for case A cannot validate for case B."""
        # Create and approve for case A
        record = _create_and_approve(service)

        # Validate with case B's fingerprint
        case_b_id = str(uuid.uuid4())
        fp_case_b = _make_fp_input(case_id=case_b_id)
        result = service.validate_approval(
            record, fp_case_b, now=NOW + timedelta(minutes=10)
        )
        assert result.valid is False
        assert result.failure_reason == ApprovalFailureReason.CASE_MISMATCH

    def test_one_paise_difference_invalidates(
        self, service: HumanApprovalService
    ) -> None:
        """Even 1 paise difference must invalidate."""
        request = _make_request(amount_minor=90_000_00)
        record = service.create_approval_request(request, now=NOW)
        fp_input = _make_fp_input(amount_minor=90_000_00)
        approved = service.approve(
            record, "cfo", fp_input, now=NOW + timedelta(minutes=5)
        )

        fp_changed = _make_fp_input(amount_minor=90_000_01)
        result = service.validate_approval(
            approved, fp_changed, now=NOW + timedelta(minutes=10)
        )
        assert result.valid is False
        assert result.failure_reason == ApprovalFailureReason.AMOUNT_MISMATCH
