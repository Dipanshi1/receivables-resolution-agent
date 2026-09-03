# Financial Calculation Specification

## 1. Purpose

This document defines the deterministic financial calculation rules used by the Receivables Resolution Agent.

It is the single source of truth for calculating:

- invoice financial position,
- valid adjustments,
- verified payments,
- disputed amounts,
- blocked amounts,
- current outstanding amount,
- collectible amount,
- safely recoverable amount,
- recovered amount, and
- remaining balance.

The Financial Calculation Service must be deterministic, reproducible, auditable, and independent of LLM reasoning.

---

# 2. Core Principle

> **AI may extract financial facts; deterministic application logic determines financial amounts.**

The LLM must never be treated as the authoritative calculator for:

- disputed amount,
- collectible amount,
- safely recoverable amount,
- recovered amount,
- outstanding amount, or
- remaining balance.

---

# 3. Monetary Representation

All authoritative monetary values are represented internally using integer minor currency units.

For INR:

```text
₹1 = 100 paise

Example:

₹9,00,000
=
90,000,000 paise

The system must not use floating-point numbers for authoritative financial calculations.

API fields should explicitly communicate this representation.

Examples:

amount_minor
total_amount_minor
paid_amount_minor
disputed_amount_minor
collectible_amount_minor
recovered_amount_minor
4. Financial Calculation Inputs

The Financial Calculation Service may use:

Invoice
Invoice Lines
Verified Payments
Valid Credit Notes
Valid Adjustments
Verified Dispute Assessments
Relevant Contract / Pricing Rules

The exact inputs depend on the scenario being evaluated.

Customer claims are not authoritative financial inputs until they have been verified through the evidence workflow.

5. Financial Concepts

The system must distinguish the following concepts.

5.1 Gross Invoice Amount

The amount originally invoiced before subsequent valid adjustments and verified payments.

gross_invoice_amount
5.2 Valid Adjustments

Adjustments that legitimately reduce the amount currently owed.

Examples may include:

Credit notes
Approved billing adjustments
Other explicitly supported financial corrections

Only valid and verified adjustments may affect the authoritative financial calculation.

5.3 Verified Payments

Payments that have been verified through the application's payment workflow.

A payment is authoritative only after the corresponding payment evidence has passed the required validation process.

An attempted payment is not equivalent to a verified payment.

5.4 Current Outstanding Amount

The amount that remains financially outstanding after valid adjustments and verified payments.

For the baseline calculation:

current_outstanding_amount
=
gross_invoice_amount
-
valid_adjustments
-
verified_payments

The result must never be negative.

Therefore:

current_outstanding_amount
=
max(
    0,
    gross_invoice_amount
    -
    valid_adjustments
    -
    verified_payments
)

Scenario-specific accounting rules may refine this calculation where required.

5.5 Customer-Claimed Disputed Amount

The amount the customer claims is disputed.

claimed_disputed_amount

This is an input to evidence analysis.

It is not automatically accepted as a verified financial amount.

5.6 Verified Disputed Amount

The portion of the receivable that is supported by the available business evidence and determined to be genuinely disputed or blocked.

verified_disputed_amount

This value may be:

known
unknown

It must not be fabricated when evidence is insufficient.

5.7 Collectible Amount

The portion of the current outstanding amount that is supported as collectible after accounting for verified blocked/disputed value.

Baseline formulation:

collectible_amount
=
max(
    0,
    current_outstanding_amount
    -
    verified_disputed_amount
)

This formula applies where the verified disputed amount represents a portion of the current outstanding balance.

The implementation must not blindly apply this formula to scenarios where the dispute has already been reflected through another financial adjustment.

5.8 Safely Recoverable Amount

The amount that can currently be pursued through the recovery workflow after financial assessment and safety constraints.

The Financial Calculation Service establishes the financially supported amount.

The Policy Engine then determines how much of that amount may be executed automatically.

Therefore:

safely_recoverable_amount

and:

autonomous_recovery_authority

are distinct concepts.

Example:

Safely recoverable:
₹9,00,000

Autonomous authority:
₹5,00,000

Result:

Safe recovery exists:
YES

Autonomous execution of ₹9,00,000:
NO

Human approval:
REQUIRED
6. Calculation Flow

The baseline financial calculation flow is:

Gross Invoice Amount
        ↓
Valid Adjustments
        ↓
Verified Payments
        ↓
Current Outstanding Amount
        ↓
Verified Disputed / Blocked Amount
        ↓
Collectible Amount
        ↓
Policy Constraints
        ↓
Safely Executable Recovery Amount

The calculation service must keep financial assessment separate from policy authorization.

7. Financial Calculation Boundary

The following responsibilities belong to the Financial Calculation Service:

Determine current outstanding
Determine verified disputed amount where applicable
Determine collectible amount
Determine remaining financial balance
Validate monetary consistency
Prevent negative financial values
Prevent over-recovery

The following responsibilities do not belong to it:

Deciding whether automation is permitted
Deciding whether human approval is required
Sending customer communications
Calling Razorpay
Changing Recovery Case state
Interpreting customer intent

Those responsibilities belong to other application components.

8. Calculation Preconditions

Before a financial assessment is marked verified:

1. Required financial inputs must be present.
2. Monetary values must be valid.
3. Payments must be verified before inclusion.
4. Adjustments must be valid before inclusion.
5. Relevant dispute evidence must be assessed.
6. Material evidence conflicts must be resolved or explicitly marked unresolved.
7. Currency must be known and consistent.

If a required input cannot be established:

financial_assessment_status = INSUFFICIENT

The system must not invent a replacement value.

9. Negative Values

Authoritative financial amounts representing balances, payments, disputes, recoveries, or collectible values must not become negative.

Examples:

invoice_amount < 0
payment_amount < 0
recovered_amount < 0
collectible_amount < 0

must be rejected.

Where a calculation would mathematically produce a negative balance because payments/adjustments exceed the outstanding amount, the outstanding balance is capped at zero.

The application should separately retain the underlying payment/adjustment records rather than encoding an artificial negative receivable.

10. Over-Recovery Prevention

The system must preserve:

recovered_amount <= applicable_recoverable_balance

and:

recovery_action_amount <= verified_collectible_amount

A proposed action that violates these constraints must not execute.

11. Payment Inclusion Rules

A payment may affect authoritative recovery calculations only when it has passed the required verification process.

Examples of non-authoritative payment states:

payment_attempted
payment_pending
payment_failed
payment_unverified

Examples of authoritative payment state:

payment_verified

The application must not add an unverified payment to recovered totals.

12. Duplicate Payment Protection

The same payment must not be counted twice.

Payment aggregation must use a stable internal/provider payment identifier.

Example:

PAY-001
₹5,00,000

received twice through duplicate webhook processing must contribute only once:

verified_payments += ₹5,00,000

not:

verified_payments += ₹10,00,000
13. Credit Note and Adjustment Rules

A credit note or adjustment may affect the current outstanding amount only when:

1. It is associated with the correct invoice/customer context.
2. It is considered valid by the application.
3. It has not already been applied.
4. It has a known amount and currency.

The same adjustment must not be applied more than once.

14. Dispute Calculation

The dispute workflow distinguishes:

Customer Claim
        ↓
Evidence
        ↓
Verified Dispute

The customer claim may be:

₹1,00,000

while the evidence may establish:

₹80,000

In that situation:

claimed_disputed_amount = ₹1,00,000
verified_disputed_amount = ₹80,000

The financial calculation uses the verified value, not the original customer assertion.

15. Insufficient Evidence

If the evidence does not support a reliable disputed amount:

verified_disputed_amount = UNKNOWN

The system must not substitute:

claimed_disputed_amount

as the verified financial amount.

Expected workflow:

Insufficient Evidence
        ↓
No unsupported collectible calculation
        ↓
Human Review / Evidence Request
16. Conflicting Evidence

If material evidence produces conflicting financial facts:

Evidence Conflict
        ↓
Verified Financial Assessment
        ↓
NOT ESTABLISHED

The system must not silently choose one conflicting value merely to continue automation.

Expected behavior is:

Human Review

or another explicitly defined safe workflow.

17. Multiple Disputed Lines

For invoices containing multiple disputed line items, each verified disputed component should be calculated separately before aggregation.

Conceptually:

Line 1
    ↓
Verified dispute = ₹20,000

Line 2
    ↓
Verified dispute = ₹30,000

Line 3
    ↓
No dispute

Then:

verified_disputed_amount
=
₹20,000
+
₹30,000
=
₹50,000

The exact line-level calculation must use the validated commercial facts for the scenario.

18. Tax and Pricing Semantics

Tax treatment must be explicit in the financial model.

The system must not assume that:

unit_price

always includes or excludes tax.

The calculation rules for a given invoice/scenario must identify whether amounts are:

tax-inclusive
tax-exclusive

where this distinction affects the result.

Ambiguous tax treatment must not be silently guessed.

19. Partial Recovery

Partial recovery occurs when:

collectible_amount > 0

but:

collectible_amount < relevant outstanding recovery balance

or the recovery action intentionally covers only part of the currently collectible value.

Example:

Current outstanding:
₹10,00,000

Verified disputed:
₹1,00,000

Collectible:
₹9,00,000

The application may create a recovery action for:

₹9,00,000

subject to policy authorization.

The remaining:

₹1,00,000

remains associated with the unresolved disputed portion.

20. Partial Payment

Partial payment is different from partial recovery.

Example:

Approved recovery:
₹9,00,000

Customer pays:
₹5,00,000

Then:

Verified recovered:
₹5,00,000

Approved recovery remaining:
₹4,00,000

The application determines the Recovery Case state after reconciliation.

A provider event indicating partial payment must not by itself determine the final business state.

21. Recovered Amount

The authoritative recovered amount is the sum of verified payments attributable to the Recovery Case / Recovery Action according to the application's payment mapping rules.

Conceptually:

recovered_amount
=
sum(verified attributable payments)

Duplicate or unverified payments must not be included.

22. Remaining Balance

The remaining financial balance must be derived deterministically from the current verified financial state.

A simplified recovery balance can be represented as:

remaining_recovery_amount
=
applicable_recoverable_amount
-
verified_recovered_amount

The result must not be negative:

remaining_recovery_amount
=
max(
    0,
    applicable_recoverable_amount
    -
    verified_recovered_amount
)

The exact applicable recoverable amount depends on the case's financial state.

23. Financial Assessment Status

Every financial assessment should have an explicit status.

Recommended values:

PENDING
CALCULATED
VERIFIED
INSUFFICIENT
CONFLICTING
STALE
INVALID

A recovery action may rely on a financial assessment only when the required assessment fields are in an appropriate verified state.

24. Financial Assessment Versioning

Financial calculations should be versioned.

Example:

calculation_version = v1.0

If calculation semantics change:

v1.0
→
v1.1

Historical financial assessments must retain the version under which they were calculated.

25. Stale Financial Assessment

A financial assessment becomes stale when material financial facts change after the assessment was calculated.

Examples:

New verified payment
New valid credit note
Approved adjustment
Material evidence correction

If a recovery proposal relies on a stale financial assessment:

Execution
    ↓
Revalidation Required

The application must not execute against stale financial state.

26. Currency Consistency

All financial values participating in one calculation must use the same currency unless an explicit conversion rule exists.

For the MVP:

Primary currency:
INR

The system must not silently convert currencies.

27. Rounding

Authoritative monetary calculations must use deterministic rounding rules.

The implementation should avoid repeated intermediate rounding where the underlying amounts are already represented exactly in minor units.

Any calculation that requires rounding must use one documented rounding rule consistently.

The rounding behavior must be covered by automated tests.

28. Calculation Invariants

The implementation must guarantee:

1. gross_invoice_amount >= 0
2. valid_adjustments >= 0
3. verified_payments >= 0
4. claimed_disputed_amount >= 0 when present
5. verified_disputed_amount >= 0 when present
6. collectible_amount >= 0
7. recovered_amount >= 0
8. remaining amounts >= 0
9. recovered_amount <= applicable balance
10. recovery_action_amount <= verified_collectible_amount
29. Assessment of Autonomous Authority

Financial calculation determines:

How much is financially collectible?

Policy determines:

How much may be executed automatically?

These are separate.

Example:

Verified collectible:
₹9,00,000

Automated authority:
₹5,00,000

Result:

financial assessment:
₹9,00,000 collectible

policy decision:
HUMAN_APPROVAL_REQUIRED

The Policy Engine must not alter the underlying collectible amount merely because the autonomous authority is lower.

30. Example — Simple Partial Dispute

Input:

Gross invoice:
₹10,00,000

Valid adjustments:
₹0

Verified payments:
₹0

Verified disputed amount:
₹1,00,000

Calculation:

Current outstanding
=
₹10,00,000
-
₹0
-
₹0

=
₹10,00,000

Then:

Collectible
=
₹10,00,000
-
₹1,00,000

=
₹9,00,000

Therefore:

verified_collectible_amount = ₹9,00,000

This is a financial assessment, not yet permission to execute.

31. Example — Payment Already Received

Input:

Gross invoice:
₹10,00,000

Valid adjustments:
₹0

Verified payments:
₹2,00,000

Verified disputed amount:
₹1,00,000

Calculation:

Current outstanding
=
₹10,00,000
-
₹0
-
₹2,00,000

=
₹8,00,000

Then:

Collectible
=
₹8,00,000
-
₹1,00,000

=
₹7,00,000

Therefore:

verified_collectible_amount = ₹7,00,000
32. Example — Credit Note

Input:

Gross invoice:
₹10,00,000

Valid credit note:
₹1,00,000

Verified payments:
₹0

Verified disputed amount:
₹1,00,000

Calculation:

Current outstanding
=
₹10,00,000
-
₹1,00,000
-
₹0

=
₹9,00,000

Then:

Collectible
=
₹9,00,000
-
₹1,00,000

=
₹8,00,000

The exact treatment of a credit note must depend on whether the credit note already represents the commercial adjustment being disputed.

The same financial effect must never be deducted twice.

33. Example — Partial Payment After Recovery

Initial:

Collectible:
₹9,00,000

Recovery action:

Approved:
₹9,00,000

Verified customer payment:

₹5,00,000

Then:

Verified recovered:
₹5,00,000

and:

Remaining approved recovery:
₹4,00,000

The application must then determine the appropriate next state through the State Machine.

34. Example — Stale Proposal

Initial assessment:

Collectible:
₹9,00,000

Resolution proposal:

Recover:
₹9,00,000

Before execution:

Customer payment verified:
₹2,00,000

Recalculated current outstanding/collectible state may now be lower.

The original proposal is stale.

Expected behavior:

Old proposal
      ↓
REVALIDATION REQUIRED
      ↓
New financial assessment
      ↓
New policy evaluation if material

The system must not execute the stale amount.

35. Calculation Result Contract

The Financial Calculation Service should return a structured result conceptually similar to:

{
  "status": "VERIFIED",
  "currency": "INR",
  "gross_invoice_amount_minor": 100000000,
  "valid_adjustments_minor": 0,
  "verified_payments_minor": 0,
  "current_outstanding_amount_minor": 100000000,
  "claimed_disputed_amount_minor": 10000000,
  "verified_disputed_amount_minor": 10000000,
  "collectible_amount_minor": 90000000,
  "safely_recoverable_amount_minor": 90000000,
  "calculation_version": "v1.0",
  "evidence_ids": [
    "PO-7721",
    "GRN-1194"
  ]
}

The field:

safely_recoverable_amount_minor

represents the financially supported amount available to the recovery workflow.

It does not grant autonomous execution authority.

36. Integration with Policy Engine

The Policy Engine consumes the verified financial assessment.

Example:

Financial Calculation
        ↓
Collectible = ₹9,00,000
        ↓
Policy Engine
        ↓
Auto authority = ₹5,00,000
        ↓
HUMAN_APPROVAL_REQUIRED

The Policy Engine does not recompute the financial assessment independently.

37. Integration with State Machine

The State Machine uses financial results as inputs to determine whether a transition is valid.

The State Machine must not independently calculate:

collectible amount
disputed amount
recovered amount

It may consume the verified results produced by the Financial Calculation Service.

38. Integration with Recovery Executor

Before financial execution:

Recovery Proposal
        ↓
Current Financial Assessment
        ↓
Revalidation
        ↓
Policy Decision
        ↓
State Validation
        ↓
Execution

The Recovery Executor must use the validated amount from the current financial state.

It must not use an arbitrary client-provided amount.

39. Audit Requirements

Every material financial assessment should record:

case_id
invoice_id
calculation_version
input references
financial outputs
evidence references
timestamp
assessment status

Example:

COLLECTIBLE_AMOUNT_CALCULATED

must identify how the result was produced from verified financial inputs.

40. Failure Behavior

If the Financial Calculation Service cannot reliably determine a required amount:

FINANCIAL_ASSESSMENT_FAILED
        ↓
No autonomous financial execution
        ↓
Human review / correction

The service must fail closed.

It must not:

guess
round arbitrarily
copy customer claims
use stale values

as a substitute for missing financial truth.

41. Financial Calculation Test Requirements

The implementation must include deterministic tests covering:

basic invoice calculation
previous payment
multiple payments
credit note
multiple adjustments
simple partial dispute
multiple disputed lines
zero dispute
full dispute
insufficient evidence
conflicting evidence
duplicate payment
duplicate adjustment
stale assessment
over-recovery
negative values
currency mismatch
rounding behavior
42. Boundary Tests

The implementation must explicitly test:

₹0 invoice
₹0 payment
₹0 dispute
payment = invoice amount
payment = invoice amount + ₹1
dispute = outstanding amount
dispute = outstanding amount + ₹1
recovery = collectible amount
recovery = collectible amount + ₹1

Expected behavior must be deterministic.

43. Financial Calculation Principle

The purpose of the Financial Calculation Service is not to maximize the amount recovered.

Its purpose is to establish:

What amount is financially supported by the current verified state of the receivable?

The Policy Engine then determines whether and how that amount may be pursued.

44. Final Calculation Model

The authoritative financial model is:

                 GROSS INVOICE
                      │
                      ▼
             VALID ADJUSTMENTS
                      │
                      ▼
             VERIFIED PAYMENTS
                      │
                      ▼
             CURRENT OUTSTANDING
                      │
                      ▼
          VERIFIED DISPUTED / BLOCKED
                      │
                      ▼
                COLLECTIBLE
                      │
                      ▼
          POLICY / AUTHORITY CHECK
                      │
                      ▼
          APPROVED RECOVERY ACTION
                      │
                      ▼
            VERIFIED PAYMENT EVENTS
                      │
                      ▼
              RECOVERED AMOUNT
                      │
                      ▼
              REMAINING BALANCE

The financial calculation layer establishes monetary truth.

The Policy Engine establishes execution authority.

The State Machine establishes workflow validity.

The Recovery Executor performs the authorized external action.