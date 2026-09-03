# Webhook Design

## 1. Purpose

This document defines the webhook architecture for receiving and processing Razorpay payment events.

The webhook layer is the boundary between:

```text
Razorpay
   ↓
Receivables Resolution Agent

Its responsibilities are to:

authenticate the event,
validate the event,
prevent duplicate processing,
map the event to the correct internal payment/recovery record,
update payment state,
generate domain events,
trigger valid State Machine transitions,
create audit records.

The webhook layer must never bypass:

financial validation,
policy,
authorization,
state validation,
reconciliation.
2. Core Principle

External payment events are untrusted until authenticated and validated.

The system must not update financial state merely because an HTTP request reached the webhook endpoint.

The processing model is:

Webhook Received
      ↓
Read Raw Body
      ↓
Verify Signature
      ↓
Read Event ID
      ↓
Deduplication Check
      ↓
Validate Event
      ↓
Resolve Internal Payment
      ↓
Validate Financial Data
      ↓
Persist Verified Payment Event
      ↓
Create Domain Event
      ↓
State Machine
      ↓
Audit Event

No financial state mutation may occur before the event passes the required trust and validation checks.

3. Webhook Endpoint

Endpoint:

POST /v1/webhooks/razorpay

This endpoint is intended for Razorpay.

It is not a frontend API.

The endpoint must not require frontend authentication mechanisms that would prevent Razorpay from delivering the webhook.

Authentication of the webhook is performed through provider signature verification.

4. Raw Request Body Requirement

The webhook signature must be verified against the exact raw request body received from Razorpay.

Correct:

Raw HTTP Body
      ↓
Signature Verification
      ↓
JSON Parsing

Incorrect:

HTTP Body
      ↓
Parse JSON
      ↓
Re-serialize JSON
      ↓
Signature Verification

The implementation must preserve the original raw bytes until signature verification is complete.

The webhook framework must therefore expose the raw request body to the verification layer.

5. Signature Header

The application reads:

X-Razorpay-Signature

The signature is verified using the configured webhook secret.

Conceptually:

expected_signature =
    HMAC_SHA256(
        webhook_secret,
        raw_request_body
    )

The received signature must match the expected signature according to the provider's documented verification procedure.

The implementation must use a constant-time comparison where supported.

6. Webhook Secret

The webhook secret is distinct from the Razorpay API key secret.

Configuration:

RAZORPAY_WEBHOOK_SECRET

The secret must:

never be committed to Git,
never be returned to clients,
never be written to logs,
never be embedded in source code,
only be accessible to the webhook verification component.

The secret must be stored through environment configuration or appropriate secret storage.

7. Signature Verification Failure

If signature verification fails:

Webhook
   ↓
Signature Invalid
   ↓
Reject

The system must not:

trust the payload,
parse it as trusted financial data,
update Payment records,
update Recovery Actions,
change Recovery Case state,
increase recovered amount,
create a successful recovery outcome.

The event should generate an appropriate security/integration log.

The raw payload must not be logged indiscriminately because webhook payloads may contain customer/payment information.

8. Event Identifier

The application should read:

x-razorpay-event-id

from the request headers.

This identifier should be used as the primary webhook deduplication key.

The event ID should be persisted with the webhook processing record.

The uniqueness constraint should be enforced at the database level.

Conceptually:

UNIQUE(provider, event_id)

This prevents concurrent webhook requests from both being treated as new events.

9. Idempotency

The webhook handler must ensure that the same provider event cannot create duplicate financial effects.

Conceptually:

Receive Event
      ↓
Read Event ID
      ↓
Already Processed?
   ┌──┴──┐
  YES    NO
   ↓      ↓
Return   Process
No-op

Duplicate events must not:

create duplicate Payment records,
increase recovered amount twice,
create duplicate domain events,
trigger duplicate Recovery Case transitions,
create duplicate recovery actions.

Idempotency must be enforced transactionally.

A simple application-level check followed by a separate insert is insufficient because two concurrent requests may pass the check simultaneously.

10. Webhook Event Record

The application should persist a webhook processing record.

Conceptual model:

WebhookEvent
------------
id
provider
event_id
event_type
received_at
signature_verified
processing_status
processed_at
error_code

Possible processing statuses:

RECEIVED
VERIFIED
PROCESSING
PROCESSED
DUPLICATE
REJECTED
FAILED

The implementation may combine this model with the integration/audit model where appropriate, but financial-effect idempotency must remain enforceable.

11. Event Processing States

Webhook processing should distinguish:

RECEIVED

from:

SIGNATURE_VERIFIED

from:

PROCESSED

A successfully verified webhook is not necessarily a successfully reconciled payment.

Example:

Signature valid
      ↓
Payment Link unknown
      ↓
No financial mutation
      ↓
Operational review

Therefore provider-event authenticity and business reconciliation are separate stages.

12. Event Validation

After signature verification, the JSON payload must be validated.

Validation should confirm:

event type exists,
expected provider payload structure exists,
required entity identifiers exist,
relevant payment/reference information exists,
amount information is coherent where required,
currency information is coherent where required.

Malformed events must not update financial state.

Provider payloads should be parsed into typed internal DTOs rather than being passed directly into domain models.

13. Supported Payment Link Events

The MVP should support Payment Link events relevant to the recovery workflow.

Primary events:

payment_link.paid
payment_link.partially_paid
payment_link.cancelled
payment_link.expired

The implementation may subscribe only to events required by the current workflow.

Additional provider events may be added later without changing the application's core payment/recovery model.

14. Primary Recovery Event — payment_link.paid

The primary golden-path event is:

payment_link.paid

Processing:

Razorpay
   ↓
payment_link.paid
   ↓
Verify Signature
   ↓
Validate Event
   ↓
Deduplication Check
   ↓
Locate Payment Link / Recovery Action
   ↓
Validate Payment
   ↓
Record Verified Payment
   ↓
Create PAYMENT_CONFIRMED Domain Event
   ↓
State Machine
   ↓
Audit Event

The event itself is evidence of a provider-side payment event.

The application must still validate the mapping, amount, currency, and financial consistency before applying the financial effect.

15. Payment Link Partially Paid

If:

payment_link.partially_paid

is received, the application records the verified amount actually paid.

Example:

Approved recovery:
₹9,00,000

Verified payment:
₹5,00,000

The application records:

recovered_amount += ₹5,00,000

subject to:

event idempotency,
payment uniqueness,
financial reconciliation,
over-recovery protection.

The Recovery Case remains incomplete if the relevant recovery balance is still outstanding.

16. Payment Link Cancelled

If:

payment_link.cancelled

is received:

Payment Link
      ↓
Cancelled

The application must not mark the recovery as successful.

The provider-side cancellation should be represented in the Payment/Recovery Action integration state.

Any replacement recovery action must pass through normal:

Financial Validation
      ↓
Policy
      ↓
Authorization
      ↓
State Machine

controls.

17. Payment Link Expired

If:

payment_link.expired

is received:

Payment Link
      ↓
Expired

The application must not interpret expiry as:

Invoice Forgiven

or:

Receivable Written Off

or:

Recovery Successfully Completed

It only means that the provider-side payment mechanism expired.

A new recovery action may be created only through the normal recovery workflow.

18. Event Ordering

The webhook handler must not assume that external events will always arrive in ideal chronological order.

For example:

Event A
   ↓
Event B
   ↓
Network delay
   ↓
B arrives first
   ↓
A arrives later

Therefore the system must use:

current provider state where required,
internal Payment state,
event timestamps where useful,
State Machine guards,
idempotency,
reconciliation rules.

The application must not blindly apply a state transition solely because an event arrived.

19. Payment Event vs Recovery State

Provider event status must not be copied directly into Recovery Case state.

Correct architecture:

Razorpay Event
      ↓
Webhook Handler
      ↓
Payment Record
      ↓
Domain Event
      ↓
Financial Reconciliation
      ↓
State Machine
      ↓
Recovery Case State

This preserves separation between:

Provider State
Payment State
Recovery Workflow State
20. Payment Identification

The webhook must identify the correct internal Payment and Recovery Action using verified provider references.

Relevant identifiers may include:

payment_link_id
payment_id
order_id where applicable
application reference_id
application metadata/notes where applicable

Mapping:

Provider Identifier
       ↓
Payment
       ↓
Recovery Action
       ↓
Recovery Case
       ↓
Invoice

A webhook that cannot be safely associated with an internal payment/recovery record must not mutate financial state.

21. Unknown Payment Link

If a valid webhook refers to a Payment Link unknown to the application:

Verified Event
      ↓
No Internal Mapping
      ↓
No Financial Mutation
      ↓
Record Integration Event
      ↓
Operational Review

The system must not create an arbitrary Recovery Case from an unknown provider event.

The event should remain available for investigation.

22. Provider Identifier Validation

Provider identifiers must be validated before use.

The application must not trust:

case_id
invoice_id
recovery_action_id

from webhook metadata as sufficient authorization.

The authoritative mapping must be established using records created by the application's own execution flow.

Provider metadata may assist lookup, but it must not manufacture authorization.

23. Payment Record Creation

A verified payment event should create or update an internal Payment record.

Conceptual fields:

Payment
-------
id
recovery_action_id
provider
provider_payment_id
provider_payment_link_id
amount_minor
currency
status
event_id
verified_at
created_at

Provider payment identifiers should be unique where appropriate.

For example:

UNIQUE(provider, provider_payment_id)

This provides an additional protection against duplicate payment ingestion.

24. Payment Uniqueness

The application must protect against duplicate payment records.

Potential duplicate keys include:

provider + event_id
provider + payment_id

Both event-level and payment-level deduplication are valuable because:

one event

and:

one provider payment

represent different uniqueness concerns.

25. Amount Reconciliation

For every verified payment:

payment_amount_minor

must be associated with the correct:

currency
Payment Link
Recovery Action
Recovery Case

The application must validate that:

payment_amount_minor > 0

where required by the provider event semantics.

The application must also prevent invalid balances such as:

recovered_amount > invoice_amount

or:

recovered_amount > applicable recovery balance

unless the business domain explicitly supports overpayment handling.

The MVP should fail closed on unexpected overpayment rather than silently assigning the excess to the recovery action.

26. Currency Validation

Payment currency must match the currency expected by the associated Recovery Action.

For the MVP:

INR

is the primary currency.

The webhook handler must not silently convert currency.

A currency mismatch must not be treated as a successful recovery.

27. Payment Confirmation Rule

The application may transition toward recovered states only after the payment event has passed all required checks:

signature verified,
event structure validated,
event ID deduplicated,
payment identifier validated,
internal mapping resolved,
amount validated,
currency validated,
payment uniqueness validated,
financial reconciliation passed.

Only then may the system generate:

PAYMENT_CONFIRMED

as an internal domain event.

AI output cannot replace any of these conditions.

28. Payment Confirmation Is a Domain Event

PAYMENT_CONFIRMED is a domain event.

It is not a persistent Recovery Case state.

The State Machine consumes the event and determines the resulting state.

Example:

Verified Payment
      ↓
PAYMENT_CONFIRMED
      ↓
State Machine
      ↓
PARTIALLY_RECOVERED

or:

Verified Payment
      ↓
PAYMENT_CONFIRMED
      ↓
State Machine
      ↓
FULLY_RECOVERED

This preserves the distinction between:

Event

and:

State
29. Full Recovery Transition

If verified cumulative recovered value reaches the relevant recoverable balance:

PAYMENT_PENDING
      ↓
Verified Payment
      ↓
Financial Reconciliation
      ↓
PAYMENT_CONFIRMED
      ↓
State Machine
      ↓
FULLY_RECOVERED

The exact transition is controlled by the State Machine.

The webhook handler must not directly assign:

FULLY_RECOVERED
30. Partial Recovery Transition

If verified cumulative payment is greater than zero but the relevant recovery balance remains unresolved:

PAYMENT_PENDING
      ↓
Verified Payment
      ↓
Financial Reconciliation
      ↓
PAYMENT_CONFIRMED
      ↓
State Machine
      ↓
PARTIALLY_RECOVERED

Example:

Invoice:
₹10,00,000

Verified dispute:
₹1,00,000

Approved recovery:
₹9,00,000

Verified payment:
₹5,00,000

The system records:

Recovered:
₹5,00,000

Remaining approved recovery:
₹4,00,000

Disputed:
₹1,00,000

These balances are calculated by the Financial Calculation Service.

31. Financial Recalculation

After a verified payment is persisted, the application should recalculate the current financial position.

Conceptually:

Verified Payment
      ↓
Financial Calculation Service
      ↓
Current Outstanding
      ↓
Collectible
      ↓
Recovered
      ↓
Remaining

The webhook handler should not contain authoritative financial formulas.

This keeps payment ingestion separate from financial calculation.

32. Recovery Amount Reconciliation

For the canonical scenario:

Invoice:
₹10,00,000

Verified disputed:
₹1,00,000

Approved recovery:
₹9,00,000

After verified ₹9L payment:

Recovered:
₹9,00,000

Remaining disputed:
₹1,00,000

If verified payment is only ₹5L:

Recovered:
₹5,00,000

Remaining approved recovery:
₹4,00,000

Remaining disputed:
₹1,00,000

The webhook subsystem does not independently decide these commercial balances.

The Financial Calculation Service remains authoritative.

33. Replay Protection

Replay protection must combine:

Event ID Deduplication
+
Payment ID Deduplication
+
Signature Verification
+
Current-State Validation
+
Financial Reconciliation

A previously processed event must not create another financial effect.

Replayed valid events should be safely acknowledged without repeating:

Payment creation,
recovered-amount updates,
state transitions,
recovery actions.
34. Transaction Boundary

The financial effect of a webhook should be processed transactionally where possible.

Conceptual transaction:

BEGIN TRANSACTION

Create / claim WebhookEvent
        ↓
Create / update Payment
        ↓
Update required financial state
        ↓
Create Domain Event
        ↓
Create Audit Event

COMMIT

The exact transaction structure may vary according to the application architecture.

The critical requirement is:

A webhook must not be considered financially processed if the application cannot establish a consistent persisted result.

Database constraints should provide an additional layer of protection against concurrent duplicate processing.

35. Concurrent Webhook Handling

The application must assume that the same event may be delivered concurrently.

Example:

Request A ─────┐
               ├── same event_id
Request B ─────┘

Only one request may create the financial effect.

The implementation should use appropriate database mechanisms such as:

unique constraints,
transactional inserts,
row locking where necessary,
atomic upserts.

Application-level locking without database enforcement is insufficient.

36. Fast Acknowledgement

The webhook endpoint should avoid unnecessary long-running processing during the HTTP request.

A practical architecture may be:

HTTP Request
      ↓
Read Raw Body
      ↓
Verify Signature
      ↓
Persist / Claim Event
      ↓
Return 2xx
      ↓
Process Event

where the runtime provides reliable asynchronous/background processing.

However, acknowledgement must not be returned before the system has safely persisted enough information to guarantee that the event will not be lost.

If the application cannot reliably persist/claim the event, it should not acknowledge successful processing.

37. Webhook Retry Behavior

The application must assume that Razorpay may retry webhook delivery.

Therefore the system must be:

safe to retry
safe to duplicate
safe to receive again

without creating duplicate financial effects.

Provider retry behavior must be treated as an expected operating condition rather than an exceptional edge case.

38. Failure Handling
Signature failure
WEBHOOK_SIGNATURE_INVALID

Action:

Reject
No financial mutation
Payload failure
WEBHOOK_PAYLOAD_INVALID

Action:

Reject
No financial mutation
Operational logging
Unknown resource
WEBHOOK_RESOURCE_UNMAPPED

Action:

No financial mutation
Persist integration event
Operational review
Duplicate event
DUPLICATE_WEBHOOK

Action:

No duplicate financial effect
Safe acknowledgement
Financial mismatch
WEBHOOK_FINANCIAL_MISMATCH

Action:

Stop automatic reconciliation
No invalid balance update
Operational / human review
Processing failure
WEBHOOK_PROCESSING_FAILED

Action:

Do not create an inconsistent financial result
Allow safe retry where appropriate
Record failure
39. Unknown Event Types

If the signature is valid but the event type is not currently supported:

Signature Valid
      ↓
Event Valid
      ↓
Unsupported Event Type
      ↓
No Financial Mutation
      ↓
Record Event
      ↓
Safe Acknowledgement where appropriate

The application must not interpret unknown events as payment confirmation.

Unknown events should remain observable for future integration support.

40. Webhook Audit Events

The webhook subsystem should generate audit/integration events such as:

WEBHOOK_RECEIVED
WEBHOOK_SIGNATURE_VERIFIED
WEBHOOK_SIGNATURE_REJECTED
WEBHOOK_DUPLICATE_DETECTED
WEBHOOK_PAYLOAD_INVALID
WEBHOOK_RESOURCE_UNMAPPED

PAYMENT_LINK_PAID_RECEIVED
PAYMENT_LINK_PARTIALLY_PAID_RECEIVED
PAYMENT_LINK_CANCELLED_RECEIVED
PAYMENT_LINK_EXPIRED_RECEIVED

PAYMENT_CONFIRMED
PAYMENT_RECONCILIATION_FAILED

The final implementation may reduce event noise where appropriate.

Material financial events must remain auditable.

41. Webhook State Transition Rule

A webhook handler must never directly assign an arbitrary Recovery Case state.

Incorrect:

case.status = "FULLY_RECOVERED"

Correct:

Webhook
   ↓
Verified Payment
   ↓
PAYMENT_CONFIRMED Domain Event
   ↓
Financial Reconciliation
   ↓
State Machine
   ↓
Allowed Transition

The State Machine remains the sole authority over Recovery Case state transitions.

42. Legal and Safety Boundary

A payment webhook does not override legal or safety controls.

If a case has:

legal_lock = true

or:

automation_locked = true

the webhook may still record a legitimate external payment event.

However, the webhook must not use that event as permission to:

create another recovery action,
initiate new outreach,
remove the lock,
bypass policy,
authorize additional recovery.

Locks remain controlled by the domain workflow.

43. Payment After Case Closure

If a valid payment event arrives after the case has reached a terminal or otherwise changed state:

Webhook
   ↓
Verified Payment
   ↓
Current Case State Check

The payment should still be recorded if it is a legitimate provider event and can be safely reconciled.

However, the State Machine must determine whether the payment:

changes the recovery outcome,
requires reconciliation,
represents an overpayment,
requires operational review.

The webhook handler must not force an invalid state transition.

44. Provider Truth vs Application Truth

The system separates authority by concern.

Razorpay

Authoritative for:

provider payment events,
provider payment identifiers,
provider-side Payment Link state.
Application

Authoritative for:

invoice,
dispute classification,
collectible amount,
safely recoverable amount,
recovery action,
policy,
human approval,
Recovery Case state.
Financial Calculation Service

Authoritative for:

current outstanding,
verified recovered amount,
remaining amount,
financial reconciliation.

The webhook connects these systems but does not replace any of them.

45. Testing Requirements

The implementation must include tests for:

valid signature
invalid signature
modified payload
missing signature
duplicate event
concurrent duplicate event
unknown event
malformed payload
unknown payment link
unknown payment
payment_link.paid
payment_link.partially_paid
payment_link.cancelled
payment_link.expired
payment ID duplication
event ID duplication
partial payment reconciliation
full payment reconciliation
currency mismatch
amount mismatch
overpayment
out-of-order events
replayed event
payment after case closure
financial reconciliation failure

Critical safety tests:

invalid webhook cannot mutate financial state

duplicate webhook cannot increase recovered amount twice

unknown payment cannot mutate arbitrary case

webhook cannot bypass legal lock

webhook cannot bypass State Machine

webhook cannot create a recovery action

webhook cannot authorize a new recovery

webhook cannot mark payment successful without verified provider event
46. Local Development

Webhook handling must be testable locally.

The implementation should provide a development workflow that allows:

Generate/Test Webhook Payload
        ↓
Generate Valid Signature
        ↓
Send Request
        ↓
Verify Signature
        ↓
Process Event
        ↓
Inspect Payment
        ↓
Inspect Recovery Case
        ↓
Inspect Audit Trail

For actual Razorpay Test Mode delivery, the endpoint must be publicly reachable.

The exact tunneling/public-development mechanism should be configured separately from the domain architecture.

47. Mock Webhook Provider

The benchmark environment should not depend on real Razorpay webhook delivery.

A mock provider should be able to generate:

payment_link.paid
payment_link.partially_paid
payment_link.cancelled
payment_link.expired
duplicate events
out-of-order events
malformed events
financial mismatch
provider failure

The mock events must pass through the same application-level webhook processing boundary where practical.

This ensures that benchmark behavior exercises the same reconciliation and State Machine logic.

48. Golden Webhook Flow

For the canonical ₹9,00,000 recovery:

Razorpay Payment Link
        ↓
Customer Payment
        ↓
payment_link.paid
        ↓
X-Razorpay-Signature Verified
        ↓
x-razorpay-event-id Checked
        ↓
Payment Link Mapped
        ↓
Payment Validated
        ↓
Payment Record Created
        ↓
Financial Reconciliation
        ↓
PAYMENT_CONFIRMED Domain Event
        ↓
State Machine
        ↓
PARTIALLY_RECOVERED
        ↓
Audit Event

The final state depends on the verified financial balance.

49. Golden Partial-Payment Flow

For a ₹9L approved recovery where the customer pays ₹5L:

Payment Link
      ↓
payment_link.partially_paid
      ↓
Signature Verification
      ↓
Idempotency
      ↓
Payment Mapping
      ↓
Verified ₹5L Payment
      ↓
Financial Reconciliation
      ↓
PAYMENT_CONFIRMED
      ↓
State Machine
      ↓
PARTIALLY_RECOVERED

The system records:

Recovered:
₹5L

Remaining approved recovery:
₹4L

Original disputed amount:
₹1L
50. Critical Invariants

The following must always hold:

Invalid Signature
    →
No Financial Mutation
Duplicate Event
    →
No Duplicate Financial Effect
Unknown Payment
    →
No Arbitrary Case Mutation
Payment Link Created
    ≠
Payment Confirmed
Payment Confirmed
    ≠
Recovery Case State
Provider Event
    →
Domain Event
    →
State Machine
Webhook
    ≠
Policy Authorization
Webhook
    ≠
Human Approval
Webhook
    ≠
New Recovery Action
LLM Output
    ≠
Payment Confirmation
Provider Payment Amount
    →
Verified Payment Record
    →
Financial Calculation
51. Webhook Processing Summary

The complete processing pipeline is:

Razorpay
    ↓
HTTP Webhook
    ↓
Raw Body
    ↓
Signature Verification
    ↓
Event ID
    ↓
Deduplication
    ↓
Payload Validation
    ↓
Provider Reference Resolution
    ↓
Payment Validation
    ↓
Financial Reconciliation
    ↓
Verified Payment Record
    ↓
PAYMENT_CONFIRMED Domain Event
    ↓
State Machine
    ↓
Recovery Case State
    ↓
Audit Event

The webhook subsystem is therefore responsible for establishing:

Authenticity
+
Uniqueness
+
Provider-to-Application Mapping
+
Payment Validity
+
Financial Reconciliation Trigger

It is not responsible for:

Commercial dispute interpretation
Policy authorization
Human approval
Recovery recommendation
Recovery strategy
Arbitrary state mutation
52. Core Webhook Principle

The webhook is the trusted bridge from verified external payment events into the application's controlled recovery workflow.

The governing architecture is:

AI
    ↓
Interpretation / Recommendation

Financial Calculation
    ↓
Financial Truth

Policy Engine
    ↓
Permission

Human Approval
    ↓
Explicit Authorization where required

State Machine
    ↓
Workflow Validity

Razorpay
    ↓
External Payment Execution

Webhook
    ↓
Verified External Payment Event

Financial Reconciliation
    ↓
Application Financial State

State Machine
    ↓
Recovery Outcome

Audit
    ↓
Traceability

The webhook must never become a mechanism for bypassing application policy, authorization, financial controls, or State Machine rules.

The core invariant is:

Authenticate
    ↓
Validate
    ↓
Deduplicate
    ↓
Reconcile
    ↓
Emit Domain Event
    ↓
Transition
    ↓
Audit

Only verified external payment evidence can establish that money was actually received.