"""Deterministic Financial Calculation Core.

This module implements the authoritative financial calculation logic for the
Receivables Resolution Agent. All monetary values are represented as integer
minor currency units (paise for INR: ₹1 = 100 paise). No floating-point
arithmetic is used for authoritative financial amounts.

The Financial Calculation Core:
- IS deterministic and independently testable
- DOES NOT use LLM / AI providers
- DOES NOT make policy decisions or determine autonomous authority
- DOES NOT transition RecoveryCase state
- DOES NOT execute payments or call Razorpay
- DOES NOT send outreach or perform human approval
- DOES NOT mutate authoritative financial state as a side effect

Reference: docs/02-engineering/financial-calculation.md
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field, model_validator


# ---------------------------------------------------------------------------
# Financial Assessment Status (Section 23 of spec)
# ---------------------------------------------------------------------------
class FinancialAssessmentStatus(StrEnum):
    """Status of a financial assessment calculation."""

    PENDING = "PENDING"
    CALCULATED = "CALCULATED"
    VERIFIED = "VERIFIED"
    INSUFFICIENT = "INSUFFICIENT"
    CONFLICTING = "CONFLICTING"
    STALE = "STALE"
    INVALID = "INVALID"


# ---------------------------------------------------------------------------
# Calculation Version
# ---------------------------------------------------------------------------
CALCULATION_VERSION = "v1.0"


# ---------------------------------------------------------------------------
# Typed Calculation Input  (Sections 4, 8 of spec)
# ---------------------------------------------------------------------------
class FinancialCalculationInput(BaseModel):
    """Typed, validated input for the Financial Calculation Service.

    All monetary fields are non-negative integers in minor currency units
    (paise). Negative authoritative monetary inputs are rejected.
    """

    gross_invoice_amount_minor: int = Field(
        ...,
        ge=0,
        description="Gross invoice amount in minor units (paise). Must be >= 0.",
    )
    valid_adjustments_minor: int = Field(
        default=0,
        ge=0,
        description="Sum of valid credit notes / adjustments in minor units. Must be >= 0.",
    )
    verified_payments_minor: int = Field(
        default=0,
        ge=0,
        description="Sum of verified (not merely attempted) payments in minor units. Must be >= 0.",
    )
    claimed_disputed_amount_minor: int = Field(
        default=0,
        ge=0,
        description=(
            "Amount the customer claims is disputed (untrusted). Must be >= 0. "
            "This is NOT automatically used as a verified financial amount."
        ),
    )
    verified_disputed_amount_minor: int | None = Field(
        default=None,
        ge=0,
        description=(
            "Evidence-supported disputed amount in minor units. None means unknown / "
            "not yet assessed. When present, must be >= 0."
        ),
    )
    verified_recovered_amount_minor: int = Field(
        default=0,
        ge=0,
        description=(
            "Sum of verified recovered payments attributable to the recovery action "
            "in minor units (paise). Must be >= 0."
        ),
    )
    currency: str = Field(
        default="INR",
        min_length=3,
        max_length=3,
        description="ISO 4217 currency code. MVP: INR.",
    )

    model_config = {"frozen": True, "extra": "forbid"}

    @model_validator(mode="after")
    def _validate_financial_consistency(self) -> FinancialCalculationInput:
        """Catch logically impossible input combinations early and enforce invariants."""
        # Calculate current outstanding
        current_outstanding: int = max(
            0,
            self.gross_invoice_amount_minor
            - self.valid_adjustments_minor
            - self.verified_payments_minor,
        )

        # Calculate applicable recoverable balance (safely recoverable amount)
        if self.verified_disputed_amount_minor is None:
            if self.claimed_disputed_amount_minor > 0:
                applicable_recoverable: int = 0
            else:
                applicable_recoverable = current_outstanding
        else:
            applicable_recoverable = max(
                0, current_outstanding - self.verified_disputed_amount_minor
            )

        # Enforce over-recovery invariant (Section 10 of spec):
        # verified_recovered_amount <= applicable_recoverable_balance
        if self.verified_recovered_amount_minor > applicable_recoverable:
            raise ValueError(
                f"verified_recovered_amount_minor ({self.verified_recovered_amount_minor}) "
                f"cannot exceed applicable recoverable balance ({applicable_recoverable})"
            )
        return self


# ---------------------------------------------------------------------------
# Typed Calculation Result (Section 35 of spec)
# ---------------------------------------------------------------------------
class FinancialCalculationResult(BaseModel):
    """Structured result of a deterministic financial assessment.

    All monetary fields are non-negative integers in minor currency units.
    """

    status: FinancialAssessmentStatus
    currency: str
    calculation_version: str = CALCULATION_VERSION

    # Core financial decomposition
    gross_invoice_amount_minor: int = Field(ge=0)
    valid_adjustments_minor: int = Field(ge=0)
    verified_payments_minor: int = Field(ge=0)
    current_outstanding_amount_minor: int = Field(ge=0)

    # Dispute decomposition — claimed vs verified remain distinct
    claimed_disputed_amount_minor: int = Field(ge=0)
    verified_disputed_amount_minor: int | None = Field(default=None, ge=0)

    # Recovery decomposition
    collectible_amount_minor: int = Field(ge=0)
    safely_recoverable_amount_minor: int = Field(ge=0)
    verified_recovered_amount_minor: int = Field(ge=0)
    remaining_amount_minor: int = Field(ge=0)

    model_config = {"frozen": True}

    @property
    def recovered_amount_minor(self) -> int:
        """Compatibility property forwarding to verified_recovered_amount_minor."""
        return self.verified_recovered_amount_minor


# ---------------------------------------------------------------------------
# Pure Deterministic Calculation  (Sections 5–22, 28–30 of spec)
# ---------------------------------------------------------------------------
def calculate_financial_position(
    inputs: FinancialCalculationInput,
) -> FinancialCalculationResult:
    """Compute the authoritative financial position for a receivable.

    This is a pure function: no side effects, no I/O, no LLM, no policy.

    Formulas (from docs/02-engineering/financial-calculation.md):

        current_outstanding = max(0,
            gross_invoice_amount
            - valid_adjustments
            - verified_payments
        )

        collectible_amount = max(0,
            current_outstanding
            - verified_disputed_amount      # only when known
        )

        safely_recoverable_amount = collectible_amount
            (Financial perspective only; Policy authority is separate.)

        remaining_amount = max(0,
            safely_recoverable_amount
            - verified_recovered_amount
        )

    Over-recovery invariant (Section 10 of spec):
        verified_recovered_amount <= applicable_recoverable_balance
        (where applicable_recoverable_balance is safely_recoverable_amount)

    Args:
        inputs: Validated financial inputs.

    Returns:
        FinancialCalculationResult with all decomposed amounts.

    Raises:
        ValueError: If verified_recovered_amount exceeds applicable recoverable balance.
    """
    # --- Step 1: Current Outstanding (Section 5.4) ---
    # "current_outstanding = max(0, gross - adjustments - payments)"
    current_outstanding: int = max(
        0,
        inputs.gross_invoice_amount_minor
        - inputs.valid_adjustments_minor
        - inputs.verified_payments_minor,
    )

    # --- Step 2: Determine assessment status based on dispute knowledge ---
    verified_disputed: int | None = inputs.verified_disputed_amount_minor

    if verified_disputed is None:
        # Dispute not yet assessed — Section 15: "verified_disputed_amount = UNKNOWN"
        # Cannot reliably determine collectible; report INSUFFICIENT
        status = FinancialAssessmentStatus.INSUFFICIENT
        # Conservative: collectible is the full outstanding since we cannot
        # subtract an unknown disputed value. However per Section 15 the system
        # must not create an unsupported collectible calculation.
        # We report the outstanding as collectible=0 to be safe, but the spec
        # Section 40 says "fail closed" — so we set INSUFFICIENT and let the
        # caller (orchestrator) decide how to handle it.
        #
        # DESIGN DECISION: When verified dispute is unknown AND a claimed
        # dispute exists, we cannot determine collectible. When there is no
        # claimed dispute either, the full outstanding is collectible because
        # there is nothing disputed.
        if inputs.claimed_disputed_amount_minor > 0:
            # Customer claims exist but no verification — fail closed
            collectible: int = 0
        else:
            # No dispute claim at all — full outstanding is collectible
            collectible = current_outstanding
            status = FinancialAssessmentStatus.CALCULATED
    else:
        # Verified disputed amount is known
        status = FinancialAssessmentStatus.CALCULATED

        # --- Step 3: Collectible Amount (Section 5.7) ---
        # "collectible = max(0, current_outstanding - verified_disputed_amount)"
        collectible = max(0, current_outstanding - verified_disputed)

    # --- Step 4: Safely Recoverable Amount (Section 5.8) ---
    # "The Financial Calculation Service establishes the financially supported amount."
    # safely_recoverable_amount equals collectible from the financial perspective.
    # Policy authority is separate and NOT applied here.
    safely_recoverable: int = collectible

    # --- Step 5: Over-Recovery Invariant Enforcement (Section 10) ---
    # "verified_recovered_amount <= applicable_recoverable_balance"
    # For Phase 3A core, applicable recoverable balance is safely_recoverable.
    if inputs.verified_recovered_amount_minor > safely_recoverable:
        raise ValueError(
            f"verified_recovered_amount_minor ({inputs.verified_recovered_amount_minor}) "
            f"cannot exceed applicable recoverable balance ({safely_recoverable})"
        )

    # --- Step 6: Remaining Amount (Section 22) ---
    # "remaining = max(0, applicable_recoverable - verified_recovered)"
    remaining: int = max(0, safely_recoverable - inputs.verified_recovered_amount_minor)

    return FinancialCalculationResult(
        status=status,
        currency=inputs.currency,
        calculation_version=CALCULATION_VERSION,
        gross_invoice_amount_minor=inputs.gross_invoice_amount_minor,
        valid_adjustments_minor=inputs.valid_adjustments_minor,
        verified_payments_minor=inputs.verified_payments_minor,
        current_outstanding_amount_minor=current_outstanding,
        claimed_disputed_amount_minor=inputs.claimed_disputed_amount_minor,
        verified_disputed_amount_minor=verified_disputed,
        collectible_amount_minor=collectible,
        safely_recoverable_amount_minor=safely_recoverable,
        verified_recovered_amount_minor=inputs.verified_recovered_amount_minor,
        remaining_amount_minor=remaining,
    )
