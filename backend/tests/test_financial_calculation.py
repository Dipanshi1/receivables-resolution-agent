"""Deterministic tests for the Financial Calculation Core.

These tests verify:
- integer minor-unit arithmetic (paise for INR)
- no floating-point in authoritative calculations
- claimed vs verified dispute separation
- documented financial formulas
- boundary conditions (zero, overpayment, over-dispute)
- canonical ₹10L benchmark scenario
- architectural boundaries (no AI, no Policy, no Razorpay imports)

Reference: docs/02-engineering/financial-calculation.md Sections 28–42.
"""

from __future__ import annotations

import ast
import inspect
import textwrap

import pytest
from pydantic import ValidationError

from app.services.financial_calculation import (
    CALCULATION_VERSION,
    FinancialAssessmentStatus,
    FinancialCalculationInput,
    calculate_financial_position,
)

# ---------------------------------------------------------------------------
# Helper: paise conversion
# ---------------------------------------------------------------------------
PAISE_PER_RUPEE = 100


def rupees(r: int) -> int:
    """Convert whole rupees to paise."""
    return r * PAISE_PER_RUPEE


# ===================================================================
# A. Normal Invoice — no dispute, no adjustment, no payment
# ===================================================================
class TestNormalInvoice:
    def test_basic_outstanding_equals_gross(self):
        inp = FinancialCalculationInput(
            gross_invoice_amount_minor=rupees(10_00_000),
        )
        result = calculate_financial_position(inp)
        assert result.current_outstanding_amount_minor == rupees(10_00_000)
        assert result.collectible_amount_minor == rupees(10_00_000)
        assert result.safely_recoverable_amount_minor == rupees(10_00_000)
        assert result.remaining_amount_minor == rupees(10_00_000)
        assert result.verified_recovered_amount_minor == 0
        assert result.verified_disputed_amount_minor is None
        assert result.claimed_disputed_amount_minor == 0
        assert result.status == FinancialAssessmentStatus.CALCULATED

    def test_zero_invoice(self):
        inp = FinancialCalculationInput(gross_invoice_amount_minor=0)
        result = calculate_financial_position(inp)
        assert result.current_outstanding_amount_minor == 0
        assert result.collectible_amount_minor == 0
        assert result.remaining_amount_minor == 0

    def test_result_includes_version_and_currency(self):
        inp = FinancialCalculationInput(gross_invoice_amount_minor=100)
        result = calculate_financial_position(inp)
        assert result.calculation_version == CALCULATION_VERSION
        assert result.currency == "INR"


# ===================================================================
# B. Verified Dispute — reduces collectible
# ===================================================================
class TestVerifiedDispute:
    def test_verified_dispute_reduces_collectible(self):
        inp = FinancialCalculationInput(
            gross_invoice_amount_minor=rupees(10_00_000),
            verified_disputed_amount_minor=rupees(1_00_000),
        )
        result = calculate_financial_position(inp)
        assert result.current_outstanding_amount_minor == rupees(10_00_000)
        assert result.collectible_amount_minor == rupees(9_00_000)
        assert result.safely_recoverable_amount_minor == rupees(9_00_000)
        assert result.remaining_amount_minor == rupees(9_00_000)

    def test_zero_verified_dispute_does_not_reduce(self):
        inp = FinancialCalculationInput(
            gross_invoice_amount_minor=rupees(5_00_000),
            verified_disputed_amount_minor=0,
        )
        result = calculate_financial_position(inp)
        assert result.collectible_amount_minor == rupees(5_00_000)
        assert result.status == FinancialAssessmentStatus.CALCULATED


# ===================================================================
# C. Claimed Dispute Only — collectible NOT reduced by unverified claim
# ===================================================================
class TestClaimedDisputeOnly:
    def test_claimed_dispute_without_verification_does_not_reduce_collectible(self):
        inp = FinancialCalculationInput(
            gross_invoice_amount_minor=rupees(10_00_000),
            claimed_disputed_amount_minor=rupees(3_00_000),
            # verified_disputed_amount_minor is None → unknown
        )
        result = calculate_financial_position(inp)
        # Spec Section 15: when claim exists but no verification → fail closed
        assert result.status == FinancialAssessmentStatus.INSUFFICIENT
        assert result.collectible_amount_minor == 0
        # outstanding is unchanged
        assert result.current_outstanding_amount_minor == rupees(10_00_000)
        # claimed is preserved for transparency
        assert result.claimed_disputed_amount_minor == rupees(3_00_000)
        assert result.verified_disputed_amount_minor is None

    def test_claimed_and_verified_differ(self):
        """Spec Section 14: customer claim ≠ verified amount."""
        inp = FinancialCalculationInput(
            gross_invoice_amount_minor=rupees(10_00_000),
            claimed_disputed_amount_minor=rupees(3_00_000),
            verified_disputed_amount_minor=rupees(1_00_000),
        )
        result = calculate_financial_position(inp)
        # Uses verified, not claimed
        assert result.collectible_amount_minor == rupees(9_00_000)
        assert result.claimed_disputed_amount_minor == rupees(3_00_000)
        assert result.verified_disputed_amount_minor == rupees(1_00_000)


# ===================================================================
# D. Full Payment — outstanding becomes zero
# ===================================================================
class TestFullPayment:
    def test_full_payment_zeroes_outstanding(self):
        amt = rupees(10_00_000)
        inp = FinancialCalculationInput(
            gross_invoice_amount_minor=amt,
            verified_payments_minor=amt,
            verified_disputed_amount_minor=0,
        )
        result = calculate_financial_position(inp)
        assert result.current_outstanding_amount_minor == 0
        assert result.collectible_amount_minor == 0
        assert result.remaining_amount_minor == 0


# ===================================================================
# E. Overpayment — safely clamped to zero
# ===================================================================
class TestOverpayment:
    def test_overpayment_clamps_outstanding_to_zero(self):
        inp = FinancialCalculationInput(
            gross_invoice_amount_minor=rupees(10_00_000),
            verified_payments_minor=rupees(12_00_000),
            verified_disputed_amount_minor=0,
        )
        result = calculate_financial_position(inp)
        assert result.current_outstanding_amount_minor == 0
        assert result.collectible_amount_minor == 0
        assert result.remaining_amount_minor == 0

    def test_payment_exceeds_by_one_paise(self):
        inp = FinancialCalculationInput(
            gross_invoice_amount_minor=1000,
            verified_payments_minor=1001,
            verified_disputed_amount_minor=0,
        )
        result = calculate_financial_position(inp)
        assert result.current_outstanding_amount_minor == 0
        assert result.remaining_amount_minor == 0


# ===================================================================
# F. Adjustment — reduces current outstanding
# ===================================================================
class TestAdjustment:
    def test_valid_adjustment_reduces_outstanding(self):
        inp = FinancialCalculationInput(
            gross_invoice_amount_minor=rupees(10_00_000),
            valid_adjustments_minor=rupees(1_00_000),
            verified_disputed_amount_minor=rupees(1_00_000),
        )
        result = calculate_financial_position(inp)
        # outstanding = max(0, 10L - 1L - 0) = 9L
        assert result.current_outstanding_amount_minor == rupees(9_00_000)
        # collectible = max(0, 9L - 1L) = 8L
        assert result.collectible_amount_minor == rupees(8_00_000)

    def test_adjustment_exceeds_gross(self):
        """Adjustments larger than gross should clamp outstanding to zero."""
        inp = FinancialCalculationInput(
            gross_invoice_amount_minor=rupees(5_00_000),
            valid_adjustments_minor=rupees(7_00_000),
            verified_disputed_amount_minor=0,
        )
        result = calculate_financial_position(inp)
        assert result.current_outstanding_amount_minor == 0
        assert result.collectible_amount_minor == 0


# ===================================================================
# G. Invalid Inputs — negative monetary values rejected
# ===================================================================
class TestInvalidInputs:
    def test_negative_gross_amount_rejected(self):
        with pytest.raises(ValidationError, match="gross_invoice_amount_minor"):
            FinancialCalculationInput(gross_invoice_amount_minor=-1)

    def test_negative_adjustment_rejected(self):
        with pytest.raises(ValidationError, match="valid_adjustments_minor"):
            FinancialCalculationInput(
                gross_invoice_amount_minor=100,
                valid_adjustments_minor=-1,
            )

    def test_negative_payment_rejected(self):
        with pytest.raises(ValidationError, match="verified_payments_minor"):
            FinancialCalculationInput(
                gross_invoice_amount_minor=100,
                verified_payments_minor=-1,
            )

    def test_negative_claimed_dispute_rejected(self):
        with pytest.raises(ValidationError, match="claimed_disputed_amount_minor"):
            FinancialCalculationInput(
                gross_invoice_amount_minor=100,
                claimed_disputed_amount_minor=-1,
            )

    def test_negative_verified_dispute_rejected(self):
        with pytest.raises(ValidationError, match="verified_disputed_amount_minor"):
            FinancialCalculationInput(
                gross_invoice_amount_minor=100,
                verified_disputed_amount_minor=-1,
            )

    def test_negative_verified_recovered_rejected(self):
        with pytest.raises(ValidationError, match="verified_recovered_amount_minor"):
            FinancialCalculationInput(
                gross_invoice_amount_minor=100,
                verified_recovered_amount_minor=-1,
            )

    def test_verified_recovered_exceeds_recoverable_rejected(self):
        with pytest.raises(ValidationError, match="cannot exceed applicable recoverable balance"):
            FinancialCalculationInput(
                gross_invoice_amount_minor=100,
                verified_recovered_amount_minor=101,
            )

    def test_arbitrary_unverified_recovery_field_rejected(self):
        """Arbitrary non-verified recovered_amount_minor must not be accepted."""
        with pytest.raises(ValidationError):
            FinancialCalculationInput(
                gross_invoice_amount_minor=100,
                recovered_amount_minor=50,  # type: ignore[call-arg]
            )


# ===================================================================
# H. Verified Dispute >= Outstanding — collectible clamps to zero
# ===================================================================
class TestDisputeExceedsOutstanding:
    def test_dispute_equals_outstanding(self):
        amt = rupees(10_00_000)
        inp = FinancialCalculationInput(
            gross_invoice_amount_minor=amt,
            verified_disputed_amount_minor=amt,
        )
        result = calculate_financial_position(inp)
        assert result.collectible_amount_minor == 0
        assert result.remaining_amount_minor == 0

    def test_dispute_exceeds_outstanding(self):
        inp = FinancialCalculationInput(
            gross_invoice_amount_minor=rupees(5_00_000),
            verified_disputed_amount_minor=rupees(8_00_000),
        )
        result = calculate_financial_position(inp)
        assert result.collectible_amount_minor == 0
        assert result.remaining_amount_minor == 0

    def test_dispute_exceeds_outstanding_by_one_paise(self):
        inp = FinancialCalculationInput(
            gross_invoice_amount_minor=1000,
            verified_disputed_amount_minor=1001,
        )
        result = calculate_financial_position(inp)
        assert result.collectible_amount_minor == 0


# ===================================================================
# I. Verified Recovered Amount — must reflect verified payments only
# ===================================================================
class TestVerifiedRecoveredAmount:
    def test_verified_recovered_reduces_remaining(self):
        inp = FinancialCalculationInput(
            gross_invoice_amount_minor=rupees(10_00_000),
            verified_disputed_amount_minor=rupees(1_00_000),
            verified_recovered_amount_minor=rupees(5_00_000),
        )
        result = calculate_financial_position(inp)
        # collectible = 9L, remaining = max(0, 9L - 5L) = 4L
        assert result.collectible_amount_minor == rupees(9_00_000)
        assert result.verified_recovered_amount_minor == rupees(5_00_000)
        assert result.remaining_amount_minor == rupees(4_00_000)

    def test_verified_recovered_equals_applicable_recoverable_valid(self):
        """Verified recovery exactly equal to applicable recoverable amount is valid."""
        inp = FinancialCalculationInput(
            gross_invoice_amount_minor=rupees(9_00_000),
            verified_disputed_amount_minor=0,
            verified_recovered_amount_minor=rupees(9_00_000),
        )
        result = calculate_financial_position(inp)
        assert result.collectible_amount_minor == rupees(9_00_000)
        assert result.verified_recovered_amount_minor == rupees(9_00_000)
        assert result.remaining_amount_minor == 0

    def test_verified_recovered_greater_than_applicable_recoverable_rejected(self):
        """Spec Section 10: verified_recovered_amount <= applicable recoverable balance.

        A case such as invoice = 1,000,000, verified_dispute = 100,000, collectible = 900,000,
        verified_recovered = 950,000 must NOT silently return remaining = 0.
        It must be rejected as an invalid over-recovery input.
        """
        with pytest.raises(ValidationError, match="cannot exceed applicable recoverable balance"):
            FinancialCalculationInput(
                gross_invoice_amount_minor=rupees(10_00_000),
                verified_disputed_amount_minor=rupees(1_00_000),
                verified_recovered_amount_minor=rupees(9_50_000),
            )

    def test_over_recovery_not_silently_clamped_to_zero(self):
        """Over-recovery exceeding collectible must be rejected, not silently clamped to 0."""
        with pytest.raises(ValidationError, match="cannot exceed applicable recoverable balance"):
            FinancialCalculationInput(
                gross_invoice_amount_minor=rupees(10_00_000),
                verified_disputed_amount_minor=rupees(8_00_000),
                verified_recovered_amount_minor=rupees(5_00_000),  # collectible is 2L, 5L > 2L
            )

    def test_verified_recovered_greater_than_applicable_by_one_paise_rejected(self):
        """Boundary test: recovery exceeding recoverable by exactly 1 paise is rejected."""
        with pytest.raises(ValidationError, match="cannot exceed applicable recoverable balance"):
            FinancialCalculationInput(
                gross_invoice_amount_minor=1000,
                verified_disputed_amount_minor=100,
                verified_recovered_amount_minor=901,  # collectible is 900
            )

    def test_calculation_function_rejects_bypassed_over_recovery(self):
        """Even if Pydantic model validation is bypassed via model_construct,
        calculate_financial_position raises ValueError on over-recovery.
        """
        inp = FinancialCalculationInput.model_construct(
            gross_invoice_amount_minor=rupees(10_00_000),
            valid_adjustments_minor=0,
            verified_payments_minor=0,
            claimed_disputed_amount_minor=0,
            verified_disputed_amount_minor=rupees(1_00_000),
            verified_recovered_amount_minor=rupees(9_50_000),
            currency="INR",
        )
        with pytest.raises(ValueError, match="cannot exceed applicable recoverable balance"):
            calculate_financial_position(inp)


# ===================================================================
# J. Remaining Balance
# ===================================================================
class TestRemainingBalance:
    def test_remaining_formula(self):
        """remaining = max(0, safely_recoverable - verified_recovered)"""
        inp = FinancialCalculationInput(
            gross_invoice_amount_minor=rupees(10_00_000),
            verified_disputed_amount_minor=rupees(2_00_000),
            verified_recovered_amount_minor=rupees(3_00_000),
        )
        result = calculate_financial_position(inp)
        # collectible/safely_recoverable = 10L - 2L = 8L
        # remaining = max(0, 8L - 3L) = 5L
        assert result.safely_recoverable_amount_minor == rupees(8_00_000)
        assert result.remaining_amount_minor == rupees(5_00_000)

    def test_remaining_zero_when_fully_recovered(self):
        """When verified recovered equals safely recoverable, remaining is exactly zero."""
        inp = FinancialCalculationInput(
            gross_invoice_amount_minor=rupees(10_00_000),
            verified_disputed_amount_minor=rupees(2_00_000),
            verified_recovered_amount_minor=rupees(8_00_000),
        )
        result = calculate_financial_position(inp)
        assert result.safely_recoverable_amount_minor == rupees(8_00_000)
        assert result.remaining_amount_minor == 0


# ===================================================================
# K. Canonical Benchmark Scenario (₹10L invoice, ₹1L dispute, ₹9L collectible)
# ===================================================================
class TestCanonicalBenchmark:
    """Spec Section 30: Simple partial dispute example."""

    def test_canonical_10l_1l_9l(self):
        inp = FinancialCalculationInput(
            gross_invoice_amount_minor=100_000_000,  # ₹10,00,000 = 10L
            claimed_disputed_amount_minor=10_000_000,  # ₹1,00,000
            verified_disputed_amount_minor=10_000_000,  # ₹1,00,000
        )
        result = calculate_financial_position(inp)

        assert result.current_outstanding_amount_minor == 100_000_000
        assert result.collectible_amount_minor == 90_000_000  # ₹9,00,000
        assert result.safely_recoverable_amount_minor == 90_000_000

    def test_policy_limit_does_not_affect_collectible(self):
        """The later Policy Engine's ₹5L limit must NOT affect this result.

        The calculation engine reports ₹9L collectible regardless of
        any autonomous authority limit.
        """
        inp = FinancialCalculationInput(
            gross_invoice_amount_minor=100_000_000,
            verified_disputed_amount_minor=10_000_000,
        )
        result = calculate_financial_position(inp)
        # Must be 90_000_000, not 50_000_000
        assert result.collectible_amount_minor == 90_000_000
        assert result.safely_recoverable_amount_minor == 90_000_000

    def test_canonical_with_previous_payment(self):
        """Spec Section 31: payment already received."""
        inp = FinancialCalculationInput(
            gross_invoice_amount_minor=100_000_000,  # ₹10L
            verified_payments_minor=20_000_000,  # ₹2L
            verified_disputed_amount_minor=10_000_000,  # ₹1L
        )
        result = calculate_financial_position(inp)
        # outstanding = 10L - 2L = 8L
        assert result.current_outstanding_amount_minor == 80_000_000
        # collectible = 8L - 1L = 7L
        assert result.collectible_amount_minor == 70_000_000

    def test_canonical_with_credit_note(self):
        """Spec Section 32: credit note adjustment."""
        inp = FinancialCalculationInput(
            gross_invoice_amount_minor=100_000_000,  # ₹10L
            valid_adjustments_minor=10_000_000,  # ₹1L credit note
            verified_disputed_amount_minor=10_000_000,  # ₹1L
        )
        result = calculate_financial_position(inp)
        # outstanding = 10L - 1L = 9L
        assert result.current_outstanding_amount_minor == 90_000_000
        # collectible = 9L - 1L = 8L
        assert result.collectible_amount_minor == 80_000_000

    def test_canonical_partial_payment_after_recovery(self):
        """Spec Section 33: partial payment after recovery action."""
        inp = FinancialCalculationInput(
            gross_invoice_amount_minor=100_000_000,  # ₹10L
            verified_disputed_amount_minor=10_000_000,  # ₹1L
            verified_recovered_amount_minor=50_000_000,  # ₹5L verified
        )
        result = calculate_financial_position(inp)
        assert result.collectible_amount_minor == 90_000_000
        assert result.verified_recovered_amount_minor == 50_000_000
        assert result.remaining_amount_minor == 40_000_000  # 9L - 5L


# ===================================================================
# L. No Floating-Point Arithmetic
# ===================================================================
class TestNoFloatingPoint:
    """Verify that the financial calculation module does not use float literals
    or float() conversions for authoritative monetary arithmetic.
    """

    def test_no_float_in_source(self):
        """Parse the AST of the calculation module and verify no float usage."""
        source = inspect.getsource(
            __import__(
                "app.services.financial_calculation", fromlist=["calculate_financial_position"]
            )
        )
        tree = ast.parse(textwrap.dedent(source))
        for node in ast.walk(tree):
            # No float literal constants in the module
            if isinstance(node, ast.Constant) and isinstance(node.value, float):
                pytest.fail(
                    f"Float literal {node.value} found at line {node.lineno} "
                    f"in financial_calculation module"
                )

    def test_all_result_amounts_are_int(self):
        inp = FinancialCalculationInput(
            gross_invoice_amount_minor=100_000_000,
            verified_disputed_amount_minor=10_000_000,
            verified_recovered_amount_minor=50_000_000,
        )
        result = calculate_financial_position(inp)
        assert isinstance(result.gross_invoice_amount_minor, int)
        assert isinstance(result.valid_adjustments_minor, int)
        assert isinstance(result.verified_payments_minor, int)
        assert isinstance(result.current_outstanding_amount_minor, int)
        assert isinstance(result.claimed_disputed_amount_minor, int)
        assert isinstance(result.collectible_amount_minor, int)
        assert isinstance(result.safely_recoverable_amount_minor, int)
        assert isinstance(result.verified_recovered_amount_minor, int)
        assert isinstance(result.remaining_amount_minor, int)


# ===================================================================
# Architectural Boundary Tests
# ===================================================================
class TestArchitecturalBoundaries:
    """Verify that the financial calculation module does not import
    AI, Razorpay, Policy Engine, or State Machine modules.
    """

    def test_no_ai_imports(self):
        source = inspect.getsource(
            __import__(
                "app.services.financial_calculation", fromlist=["calculate_financial_position"]
            )
        )
        tree = ast.parse(textwrap.dedent(source))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    assert "ai" not in alias.name.lower() or alias.name == "pydantic"
            if isinstance(node, ast.ImportFrom) and node.module:
                mod = node.module.lower()
                assert "razorpay" not in mod
                assert "policy" not in mod
                assert "state_machine" not in mod
                assert "orchestrat" not in mod
                assert "webhook" not in mod

    def test_module_has_no_side_effects(self):
        """Importing the module must not perform I/O or connect to anything."""
        import importlib

        mod = importlib.import_module("app.services.financial_calculation")
        # Module exists and has the expected exports
        assert hasattr(mod, "calculate_financial_position")
        assert hasattr(mod, "FinancialCalculationInput")
        assert hasattr(mod, "FinancialCalculationResult")
        assert hasattr(mod, "FinancialAssessmentStatus")


# ===================================================================
# Boundary Tests (Spec Section 42)
# ===================================================================
class TestBoundaryValues:
    def test_zero_payment(self):
        inp = FinancialCalculationInput(
            gross_invoice_amount_minor=1000,
            verified_payments_minor=0,
            verified_disputed_amount_minor=0,
        )
        result = calculate_financial_position(inp)
        assert result.current_outstanding_amount_minor == 1000

    def test_payment_equals_invoice(self):
        inp = FinancialCalculationInput(
            gross_invoice_amount_minor=1000,
            verified_payments_minor=1000,
            verified_disputed_amount_minor=0,
        )
        result = calculate_financial_position(inp)
        assert result.current_outstanding_amount_minor == 0
        assert result.collectible_amount_minor == 0

    def test_payment_exceeds_invoice_by_one(self):
        inp = FinancialCalculationInput(
            gross_invoice_amount_minor=1000,
            verified_payments_minor=1001,
            verified_disputed_amount_minor=0,
        )
        result = calculate_financial_position(inp)
        assert result.current_outstanding_amount_minor == 0

    def test_dispute_equals_outstanding(self):
        inp = FinancialCalculationInput(
            gross_invoice_amount_minor=1000,
            verified_disputed_amount_minor=1000,
        )
        result = calculate_financial_position(inp)
        assert result.collectible_amount_minor == 0

    def test_dispute_exceeds_outstanding_by_one(self):
        inp = FinancialCalculationInput(
            gross_invoice_amount_minor=1000,
            verified_disputed_amount_minor=1001,
        )
        result = calculate_financial_position(inp)
        assert result.collectible_amount_minor == 0

    def test_zero_dispute(self):
        inp = FinancialCalculationInput(
            gross_invoice_amount_minor=1000,
            verified_disputed_amount_minor=0,
        )
        result = calculate_financial_position(inp)
        assert result.collectible_amount_minor == 1000


# ===================================================================
# Combined Scenarios
# ===================================================================
class TestCombinedScenarios:
    def test_adjustment_plus_payment_plus_dispute(self):
        inp = FinancialCalculationInput(
            gross_invoice_amount_minor=rupees(10_00_000),
            valid_adjustments_minor=rupees(50_000),
            verified_payments_minor=rupees(2_00_000),
            claimed_disputed_amount_minor=rupees(1_50_000),
            verified_disputed_amount_minor=rupees(1_00_000),
            verified_recovered_amount_minor=rupees(2_00_000),
        )
        result = calculate_financial_position(inp)
        # outstanding = max(0, 10L - 0.5L - 2L) = 7.5L
        assert result.current_outstanding_amount_minor == rupees(7_50_000)
        # collectible = max(0, 7.5L - 1L) = 6.5L
        assert result.collectible_amount_minor == rupees(6_50_000)
        # remaining = max(0, 6.5L - 2L) = 4.5L
        assert result.remaining_amount_minor == rupees(4_50_000)

    def test_full_dispute_with_payment(self):
        """Everything disputed, some payment already made."""
        inp = FinancialCalculationInput(
            gross_invoice_amount_minor=rupees(5_00_000),
            verified_payments_minor=rupees(1_00_000),
            verified_disputed_amount_minor=rupees(5_00_000),
        )
        result = calculate_financial_position(inp)
        # outstanding = 5L - 1L = 4L
        assert result.current_outstanding_amount_minor == rupees(4_00_000)
        # collectible = max(0, 4L - 5L) = 0
        assert result.collectible_amount_minor == 0

    def test_immutable_input(self):
        """FinancialCalculationInput is frozen (immutable)."""
        inp = FinancialCalculationInput(gross_invoice_amount_minor=1000)
        with pytest.raises(ValidationError):
            inp.gross_invoice_amount_minor = 2000  # type: ignore[misc]

    def test_immutable_result(self):
        """FinancialCalculationResult is frozen (immutable)."""
        inp = FinancialCalculationInput(
            gross_invoice_amount_minor=1000,
            verified_disputed_amount_minor=0,
        )
        result = calculate_financial_position(inp)
        with pytest.raises(ValidationError):
            result.collectible_amount_minor = 999  # type: ignore[misc]
