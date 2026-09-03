# Razorpay Integration

## 1. Purpose

This document defines how the Receivables Resolution Agent integrates with Razorpay for approved customer-payment recovery actions.

Razorpay is treated as the payment execution and payment-event provider.

The application's core domain remains responsible for:

- receivable state,
- dispute state,
- collectible-amount assessment,
- merchant policy,
- recovery workflow,
- recovery-case state,
- audit history.

Razorpay is not the source of truth for the application's commercial dispute classification or collectible-amount calculation.

---

# 2. Integration Boundary

The integration boundary is:

```text
Recovery Case
      ↓
Resolution Proposal
      ↓
Financial Validation
      ↓
Policy Engine
      ↓
State Machine
      ↓
Recovery Executor
      ↓
Razorpay Integration Adapter
      ↓
Razorpay APIs

The frontend must never call Razorpay directly.

AI components must never call Razorpay directly.

Only the backend's Razorpay Integration Adapter may access Razorpay credentials and provider APIs.

3. Environment

The MVP uses:

Razorpay Test Mode

Test credentials must be supplied through environment variables or secret storage.

Example:

RAZORPAY_KEY_ID
RAZORPAY_KEY_SECRET
RAZORPAY_WEBHOOK_SECRET

Actual credentials must never be:

committed to Git,
returned by an API,
exposed to the frontend,
written to logs,
embedded in source code.

The frontend only receives safe provider-facing information such as the Payment Link URL when required.

4. Provider Operations Required by the MVP

The MVP should use the smallest provider surface necessary to demonstrate the recovery workflow.

Primary operations:

Create Payment Link
Fetch Payment Link where required
Receive and process Payment Link webhook events

Provider-specific operations must remain inside the Razorpay Integration Adapter.

The domain layer must not depend directly on Razorpay SDK types.

5. Payment Link Creation

The primary provider operation is creation of a Razorpay Payment Link.

Conceptually:

Recovery Executor
      ↓
Razorpay Adapter
      ↓
Create Payment Link

The Payment Link request may contain provider-supported information such as:

amount,
currency,
description,
reference ID,
customer information,
expiry,
notes,
notification configuration.

The exact provider request schema must be implemented against the current Razorpay API documentation rather than duplicated throughout the application.

6. Application-Level Recovery Reference

Every Payment Link created by the recovery system must be traceable to the application's financial workflow.

Generate a unique application reference.

Example:

RRA-CASE-1042-REC-001

The reference should identify the recovery action without embedding unnecessary sensitive information.

Recommended provider metadata:

{
  "reference_id": "RRA-CASE-1042-REC-001",
  "notes": {
    "merchant_id": "MER-001",
    "invoice_id": "INV-1042",
    "recovery_case_id": "CASE-1042",
    "recovery_action_id": "REC-001",
    "recovery_type": "UNDISPUTED_AMOUNT"
  }
}

Provider field limits and allowed characters must be validated by the adapter before the request is sent.

The application must not assume that arbitrary metadata can be sent to the provider.

7. Recovery Action as the Authoritative Payment Instruction

The amount sent to Razorpay must come from the validated RecoveryAction.

It must not come directly from:

frontend input,
raw LLM output,
customer communication,
stale proposal data,
client-provided financial fields.

The execution path is:

Resolution Proposal
      ↓
Financial Calculation Service
      ↓
Policy Engine
      ↓
Human Approval if required
      ↓
Recovery Action
      ↓
Revalidation
      ↓
Razorpay Adapter

The Recovery Action is therefore the authoritative application-level payment instruction.

8. Canonical Partial-Recovery Scenario

Example:

Parent invoice:
₹10,00,000

Verified disputed amount:
₹1,00,000

Verified collectible amount:
₹9,00,000

Default autonomous authority:
₹5,00,000

The application calculates:

₹10,00,000
-
₹1,00,000
=
₹9,00,000 collectible

The Resolution Agent recommends:

CREATE_PARTIAL_RECOVERY
₹9,00,000

The Policy Engine evaluates:

₹9,00,000 > ₹5,00,000 autonomous authority

Therefore:

HUMAN_APPROVAL_REQUIRED

After valid human approval:

Recovery Action:
₹9,00,000

Only then may the Recovery Executor create the Razorpay Payment Link.

This distinction is critical:

Collectible Amount
        ≠
Autonomous Authority
        ≠
Approved Recovery Action
        ≠
Payment Confirmation
9. Payment Link Creation Preconditions

Before creating a Payment Link, the backend must verify:

Recovery Case is in an executable state.
Resolution Proposal is current.
Financial assessment is current.
Policy Decision exists.
Policy Decision authorizes the action.
Required human approval exists where applicable.
Human approval is bound to the exact Recovery Action.
Recovery amount <= verified collectible amount.
Recovery amount <= safely recoverable amount.
Recovery amount <= autonomous authority unless valid human approval exists.
Case is not legally locked.
Case is not automation locked.
No conflicting recovery action exists.
Recovery Action has not already been executed.
Idempotency requirements are satisfied.
Provider reference is valid.
Currency is valid.

If any critical check fails, the system must fail closed.

10. Financial Amount

The amount sent to Razorpay must come from the validated Recovery Action.

Example:

Validated Recovery Action:
₹9,00,000

The provider request receives the corresponding required minor-unit representation.

The implementation must never use floating-point arithmetic for authoritative financial values.

All internal monetary values use integer minor units.

For INR:

₹1 = 100 paise
11. Currency

The MVP is primarily designed around:

INR

The Razorpay request must use the validated recovery currency.

The application must not silently convert currencies.

Future multi-currency support requires explicit:

exchange-rate rules,
rounding rules,
accounting rules,
reconciliation rules.

Multi-currency recovery is outside the MVP.

12. Payment Description

The Payment Link description should identify the payment purpose without exposing unnecessary internal system information.

Example:

Payment for undisputed amount against invoice INV-1042

Internal identifiers should primarily be represented through structured references/metadata where supported.

The description must not be treated as authoritative financial data.

13. Customer Information

Customer information may be supplied to Razorpay where required by the integration.

The application must not assume that supplying customer contact information guarantees how information will appear on the hosted payment page.

Provider behavior must be verified against the current Razorpay documentation during implementation.

The application's customer record remains authoritative for internal customer identity.

14. Notifications

Payment Link notification behavior must be explicitly configured.

Notifications must not be enabled accidentally as a side effect of the recovery action.

The selected configuration must comply with merchant communication policy.

The application should distinguish:

Payment execution

from:

Customer communication

Creating a Payment Link must not implicitly authorize unrelated outreach.

15. Expiry

Payment Links may have an expiry configuration.

The application should use a bounded expiry consistent with the recovery workflow.

Example:

Created:
2026-08-30 10:00 UTC

Expiry:
2026-09-06 10:00 UTC

The exact default expiry should be configurable.

An expired Payment Link does not mean that the receivable has been:

forgiven,
written off,
recovered,
disputed,
legally resolved.

It represents an expired payment mechanism.

A new recovery action may be required.

16. Application Recovery State vs Provider State

The application must track its own Recovery Action state independently of Razorpay's Payment Link state.

Application lifecycle:

RECOVERY_INITIATED
        ↓
PAYMENT_PENDING
        ↓
Verified Payment Event
        ↓
PARTIALLY_RECOVERED
or
FULLY_RECOVERED

Provider-side Payment Link status may independently represent concepts such as:

issued
partially paid
paid
expired
cancelled

These provider states must not be copied blindly into the application domain.

The Integration Adapter translates provider events into application-level events.

17. Payment Link vs Application Partial Recovery

The project must distinguish two concepts.

Application-level partial recovery

The application determines:

Invoice:
₹10L

Verified dispute:
₹1L

Collectible:
₹9L

This is a business-domain decision.

Provider-level partial payment

A Payment Link may support one or more payments depending on the provider configuration.

This is a payment-provider behavior.

These concepts are not interchangeable.

The application must never represent a commercial dispute merely by enabling a provider's partial-payment feature.

18. MVP Partial-Payment Decision

For the primary golden scenario, the recommended behavior is:

Application determines:
₹9,00,000 is the approved recovery amount

        ↓

Create Payment Link
for ₹9,00,000

        ↓

Customer pays

        ↓

Verified payment event

        ↓

Application records:
₹9,00,000 recovered

        ↓

₹1,00,000 remains disputed

This keeps the provider/payment layer simple while making the application's partial-recovery concept explicit.

Provider-native partial-payment functionality may be used in future scenarios where the merchant explicitly wants installment-style payment behavior.

It is not required for the canonical MVP flow.

19. Payment Confirmation

Creating a Payment Link does not confirm payment.

The application must wait for a verified external payment event.

Conceptually:

Payment Link Created
        ↓
PAYMENT_PENDING
        ↓
Customer Payment
        ↓
Provider Event
        ↓
Webhook Verification
        ↓
Payment Record
        ↓
PAYMENT_CONFIRMED domain event

Only after verified payment evidence may the application increase recovered_amount.

20. Webhook Trust Boundary

Razorpay webhook data is external input.

The processing flow is:

Razorpay
   ↓
Webhook Endpoint
   ↓
Raw Payload Capture
   ↓
Signature Verification
   ↓
Payload Validation
   ↓
Idempotency Check
   ↓
Payment / Recovery Lookup
   ↓
Payment Record Update
   ↓
Domain Event
   ↓
State Machine
   ↓
Audit Event

The application must not trust an unauthenticated webhook.

Detailed webhook processing is defined separately in:

docs/02-engineering/webhook-design.md
21. Payment Identification

Webhook processing must identify the correct internal Payment and Recovery Action using verified provider identifiers and application references.

Relevant provider identifiers should be stored where applicable:

razorpay_payment_link_id
razorpay_payment_id
order_id

The integration maintains:

Razorpay identifier
        ↓
Internal Payment
        ↓
Recovery Action
        ↓
Recovery Case
        ↓
Invoice

A webhook must never be allowed to update an arbitrary case solely because a client supplied a case ID.

22. Multiple Payments

If the provider workflow produces multiple successful payments associated with one Payment Link, each payment event must be represented independently.

The application must aggregate only verified payment amounts.

Conceptually:

Payment 1 = ₹3L
Payment 2 = ₹2L
Payment 3 = ₹4L

Verified recovered:
₹9L

The application must derive recovered amounts from verified Payment records.

It must not treat a Payment Link as a simple binary:

paid / unpaid
23. Recovery Amount Reconciliation

For the canonical case:

Invoice:
₹10,00,000

Verified dispute:
₹1,00,000

Approved recovery:
₹9,00,000

After a verified ₹9L payment:

Recovered:
₹9,00,000

Remaining disputed:
₹1,00,000

If only ₹5L is paid:

Recovered:
₹5,00,000

Remaining approved recovery:
₹4,00,000

Remaining disputed:
₹1,00,000

These values must be calculated deterministically by the Financial Calculation Service.

The Razorpay adapter must not perform authoritative receivable calculations.

24. Payment Failure

If a customer payment attempt fails:

PAYMENT_PENDING
        ↓
Payment Failure Event
        ↓
Execution Failure / Payment Failure Handling

The application must not mark the case recovered.

A retry must pass through the normal:

Financial Revalidation
        ↓
Policy Validation
        ↓
Authorization Validation
        ↓
State Validation
        ↓
Execution

path.

25. Payment Link Expiry

If the Payment Link expires before sufficient payment is received:

PAYMENT_PENDING
        ↓
Payment Link Expired

The application must not interpret this as:

payment successful

or:

receivable written off

A new recovery action may be created only through normal workflow validation.

26. Payment Link Cancellation

Provider-side cancellation may be used only where:

the selected Razorpay API supports the operation,
the current provider state permits it, and
application policy permits cancellation.

The application must not assume that every Payment Link can always be cancelled in every provider state.

Provider capabilities must be verified against the current Razorpay API behavior during implementation.

27. External API Failure

If Razorpay returns an error:

Recovery Action
        ↓
Provider Failure
        ↓
Execution Failure Handling

No payment confirmation is generated.

An external API failure must never produce:

PARTIALLY_RECOVERED

or:

FULLY_RECOVERED

without verified payment evidence.

Provider failures should be classified as:

retryable
non-retryable
human-review-required

using explicit application rules.

28. Idempotent Recovery Execution

The Recovery Executor must support application-level idempotency.

Example:

recover-case-1042-proposal-001

The idempotency record should bind the request to:

merchant
case
recovery action
request parameters
result

If the same request is received again:

same idempotency key
        ↓
existing result

must be returned instead of creating a duplicate external payment action.

Conflicting reuse of the same idempotency key must fail.

29. Provider Reference Uniqueness

Every Payment Link created for a Recovery Action should use a unique application reference.

Example:

RRA-CASE-1042-REC-001

The adapter must validate the reference against the provider's current requirements, including:

length,
allowed characters,
uniqueness constraints.

Provider-specific limits must not be hard-coded throughout the domain layer.

30. Test Mode Strategy

The MVP should primarily use Razorpay Test Mode.

Real Razorpay Test Mode should be used for selected end-to-end demonstrations.

The benchmark must not depend on live provider APIs.

Recommended split:

Real Razorpay Test Mode
        ↓
Golden E2E demonstration

MockPaymentProvider
        ↓
50–100 case benchmark

This avoids unnecessary provider calls and allows deterministic evaluation.

31. Payment Provider Abstraction

The application should define a provider interface:

PaymentProvider
      │
      ├── RazorpayProvider
      │
      └── MockPaymentProvider

Conceptual interface:

create_payment_link(action)
    -> PaymentLinkResult

get_payment_link(provider_reference)
    -> PaymentLinkResult

verify_webhook(raw_payload, signature)
    -> VerifiedWebhookEvent

The rest of the application depends on this interface rather than Razorpay SDK implementation details.

32. Razorpay Adapter Responsibilities

The Razorpay Adapter is responsible for:

provider authentication,
request formatting,
provider response normalization,
provider-specific validation,
provider reference handling,
provider error classification,
webhook signature verification,
mapping provider events into application events.

The adapter must not decide whether a recovery is financially permitted.

That decision belongs to the Policy Engine.

The adapter must not:

calculate collectible amount,
authorize recovery,
bypass human approval,
change Recovery Case state directly,
mark a payment as financially recovered without verified event processing.
33. Recovery Executor Responsibilities

The Recovery Executor sits above the Razorpay Adapter.

Policy Decision
      ↓
State Validation
      ↓
Financial Revalidation
      ↓
Recovery Executor
      ↓
Razorpay Adapter

The Recovery Executor verifies that the action is authorized before invoking the provider.

The adapter assumes that the executor has already established application-level authorization, but the executor must never skip the domain checks.

34. Provider Error Mapping

Provider errors should be normalized into application-level categories.

Examples:

RAZORPAY_AUTH_ERROR
RAZORPAY_VALIDATION_ERROR
RAZORPAY_RATE_LIMIT
RAZORPAY_NETWORK_ERROR
RAZORPAY_SERVER_ERROR
RAZORPAY_RESOURCE_ERROR

The application then determines whether the error is:

retryable
non-retryable
human-review-required

Retries must be bounded.

Every retry must revalidate:

current financial assessment,
policy authorization,
human approval,
legal lock,
automation lock,
case state,
action validity.
35. Recovery-to-Payment Mapping

A Recovery Action may produce zero or more provider payment records depending on the provider workflow.

Primary model:

Recovery Case
      ↓
Recovery Action
      ↓
Payment Link
      ↓
One or more verified Payments

Each Payment must remain attributable to the Recovery Action.

This enables:

reconciliation,
idempotency,
auditability,
partial-payment handling,
accurate recovered-amount calculation.
36. Financial Source-of-Truth Model

Source of truth is separated by concern.

Application

Authoritative for:

invoice/recovery domain,
commercial dispute classification,
collectible assessment,
safely recoverable amount,
merchant policy,
recovery action,
case state.
Razorpay

Authoritative for:

provider-side payment events,
provider payment identifiers,
provider payment status,
Payment Link lifecycle.
Application Reconciliation

The application combines verified provider events with application domain state to establish the recovery outcome.

Therefore:

Razorpay says payment occurred
        +
Application verifies mapping and event integrity
        +
Financial Calculation Service updates balances
        ↓
Recovery outcome
37. Audit Requirements

Every Razorpay interaction that materially affects a recovery case should generate an audit event.

Examples:

PAYMENT_LINK_CREATE_REQUESTED
PAYMENT_LINK_CREATED
PAYMENT_LINK_CREATION_FAILED
PAYMENT_EVENT_RECEIVED
PAYMENT_CONFIRMED
PAYMENT_FAILED
PAYMENT_LINK_EXPIRED

Audit records should retain relevant provider references.

The audit trail must distinguish:

requested
created
received
verified
confirmed
failed

rather than collapsing all provider activity into a single status.

38. Security Requirements

Razorpay secrets must:

exist only in environment/secret storage,
never be sent to the frontend,
never be included in logs,
never be stored in source control.

Webhook secrets have the same requirements.

Only the Razorpay Integration Adapter may access provider credentials.

The frontend may receive only the minimum provider information required for the payment experience.

39. Demo Requirements

The MVP demonstration should use a real Razorpay Test Mode flow for at least one golden-path recovery.

Recommended demonstration:

Invoice:
₹10,00,000

Verified dispute:
₹1,00,000

Collectible:
₹9,00,000

Autonomous authority:
₹5,00,000

        ↓

Policy:
HUMAN_APPROVAL_REQUIRED

        ↓

Finance approval:
₹9,00,000

        ↓

Recovery Action:
AUTHORIZED

        ↓

Razorpay Payment Link

        ↓

Test Payment

        ↓

Verified Webhook

        ↓

Payment Record

        ↓

PARTIALLY_RECOVERED

The demo must visibly show the distinction between:

AI recommendation
        ↓
Policy decision
        ↓
Human authorization
        ↓
Payment execution
        ↓
Verified recovery

A second demo should show a safety failure path.

Example:

Conflicting evidence
        ↓
Human Review
        ↓
No automatic payment

or:

Legal risk
        ↓
Automation Lock
        ↓
Legal Escalation
40. Evaluation Requirements

The benchmark must not depend on live Razorpay APIs.

The evaluation environment should use:

MockPaymentProvider

to simulate:

successful payment,
partial payment,
failed payment,
expired payment request,
duplicate payment event,
provider API failure,
duplicate execution request.

The benchmark must use the same application-level payment interface as the live Razorpay integration.

This ensures that:

Benchmark Path

and:

Real Provider Path

share the same Recovery Executor and domain authorization boundaries.

Only the provider implementation changes.

41. Non-Goals

The MVP does not attempt to implement:

provider-side merchant settlement reconciliation,
payment-network dispute adjudication,
full ERP payment reconciliation,
production payment orchestration across multiple providers,
bank-transfer settlement workflows,
automatic transfers to linked accounts,
production Razorpay credentials,
provider-specific accounting as a replacement for application accounting.

Razorpay payment and settlement concepts remain distinct from the application's B2B receivables recovery model.

42. Integration Failure Invariants

The following must always hold:

Provider API failure
    ≠
Payment confirmation
Payment Link creation
    ≠
Payment confirmation
Payment confirmation
    ≠
Automatic full recovery
Collectible amount
    ≠
Autonomous authority
Policy approval
    ≠
Payment success
Provider status
    ≠
Application Recovery Case status
LLM recommendation
    ≠
Financial authorization
43. Integration Summary

The complete payment execution model is:

Overdue Receivable
       ↓
Evidence Analysis
       ↓
Financial Calculation
       ↓
Collectible Amount
       ↓
Resolution Proposal
       ↓
Policy Engine
       ↓
Human Approval if Required
       ↓
State Machine
       ↓
Recovery Executor
       ↓
Razorpay Adapter
       ↓
Payment Link
       ↓
Customer Payment
       ↓
Razorpay Webhook
       ↓
Webhook Verification
       ↓
Payment Record
       ↓
Verified Payment Domain Event
       ↓
Financial Recalculation
       ↓
State Machine
       ↓
PARTIALLY_RECOVERED / FULLY_RECOVERED
       ↓
Audit Trail

The provider handles payment execution and provider-side payment events.

The application controls the receivables-resolution workflow.

44. Core Integration Principle

Razorpay executes approved payment collection.

The Receivables Resolution Agent determines:

why the receivable is blocked,
what amount is financially eligible for recovery,
whether that recovery is safely recoverable,
whether autonomous execution is permitted,
whether human approval is required,
and what application state follows verified payment.

The application never treats creation of a payment request as proof of successful recovery.

The governing principle is:

AI interprets
      ↓
Financial system calculates
      ↓
Policy authorizes
      ↓
State Machine validates transition
      ↓
Razorpay executes
      ↓
Webhook proves external payment event
      ↓
Application reconciles
      ↓
Audit records the result