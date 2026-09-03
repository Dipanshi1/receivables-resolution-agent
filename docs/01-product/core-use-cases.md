# Core Use Cases

## 1. Purpose

This document defines the core operational use cases that Receivables Resolution Agent must support.

The use cases are derived from the Track 03 objective:

> Detect revenue at risk, determine the right intervention, and execute a bounded recovery workflow.

The system is intentionally designed around B2B receivables where payment may be blocked by operational, commercial, documentation, or payment issues.

---

# 2. Actors

## 2.1 Finance / Accounts Receivable Operator

The primary human user.

Responsibilities include:

- monitoring outstanding receivables,
- reviewing exceptions,
- approving actions outside automated authority,
- handling escalated cases, and
- resolving cases that cannot be safely automated.

---

## 2.2 Receivables Resolution Agent

The AI-assisted workflow responsible for:

- identifying the likely reason for non-payment,
- analyzing relevant evidence,
- determining a proposed resolution,
- recommending the appropriate recovery action, and
- preparing cases for automated or human handling.

The agent does not directly control financial execution.

---

## 2.3 Policy Engine

A deterministic component responsible for:

- enforcing merchant-defined limits,
- validating proposed recovery amounts,
- enforcing stopping rules,
- detecting prohibited actions,
- determining whether human approval is required, and
- preventing unsafe financial execution.

---

## 2.4 State Machine

A deterministic component responsible for controlling valid recovery-case state transitions.

---

## 2.5 Razorpay

The payment execution layer used for approved recovery actions.

Payment completion is confirmed through verified Razorpay events rather than assumptions made by the application.

---

## 2.6 Human Reviewer

A finance or operations user who handles:

- ambiguous evidence,
- conflicting records,
- policy exceptions,
- high-value actions,
- legal-risk cases, or
- cases requiring judgment beyond the automated workflow.

---

# 3. UC-01 — Detect At-Risk Receivable

## Objective

Identify a receivable that requires recovery attention.

## Trigger

One or more of the following occurs:

- invoice reaches its due date without payment,
- payment attempt fails,
- customer misses a promised payment date,
- a receivable remains unresolved after previous recovery attempts, or
- another configured signal identifies a recovery risk.

## Input

- invoice,
- customer,
- payment status,
- due date,
- recovery history,
- relevant communication history.

## Expected behavior

The system creates or updates a Recovery Case.

The case begins in:

```text
OVERDUE

or another appropriate initial state based on the triggering condition.

Output

A Recovery Case containing:

invoice reference,
customer reference,
amount at risk,
reason for triggering recovery,
current state,
recovery history.
Acceptance criteria
No recovery case is silently created without an associated receivable.
Duplicate detection does not create duplicate active cases for the same recovery condition.
The case receives an auditable creation event.
Financial amounts are represented using exact monetary values.
4. UC-02 — Triage Reason for Non-Payment
Objective

Determine the likely reason an invoice remains unpaid.

Trigger

A new recovery case enters the triage workflow.

Input
invoice data,
payment information,
customer communications,
previous recovery history.
Expected behavior

The Triage Agent classifies the primary issue.

Possible classifications include:

PAYMENT_FAILURE
QUANTITY_DISPUTE
PRICE_DISPUTE
PO_MISMATCH
GST_DOCUMENTATION
MILESTONE_PENDING
SERVICE_DELIVERY_DISPUTE
CREDIT_NOTE_REQUEST
PROMISE_TO_PAY
LEGAL_RISK
UNKNOWN
Output

A structured triage result containing:

issue type,
concise explanation,
confidence,
relevant risk flags,
whether additional evidence analysis is required.
Acceptance criteria
Output must conform to a predefined schema.
Unknown or ambiguous cases must not be forced into an unrelated category.
The Triage Agent cannot directly execute a financial action.
High-risk/legal signals must be surfaced for safety evaluation.
5. UC-03 — Gather Relevant Evidence
Objective

Collect the business records required to evaluate the reason for non-payment.

Trigger

The triage result indicates that additional evidence is required.

Input

Potential evidence sources include:

invoice,
invoice lines,
purchase order,
delivery/GRN records,
contract,
milestone records,
customer communications,
payment history,
credit notes,
other merchant-configured business records.
Expected behavior

The system retrieves the evidence relevant to the identified issue.

Output

An evidence set containing:

evidence identifier,
source type,
source reference,
extracted or normalized facts,
relevance,
provenance.
Acceptance criteria
Every material resolution claim must be traceable to one or more evidence items.
Missing evidence must be explicitly represented.
Duplicate evidence should not artificially increase confidence.
Retrieval failure must not be treated as evidence that the claim is false or true.
6. UC-04 — Verify Commercial or Operational Objection
Objective

Determine whether the customer's stated objection is supported by the available business evidence.

Trigger

Evidence has been collected.

Input
customer objection,
invoice,
purchase order,
delivery records,
contract/milestone information,
relevant communications.
Expected behavior

The Evidence Agent extracts structured facts and determines whether the objection is:

SUPPORTED
PARTIALLY_SUPPORTED
UNSUPPORTED
CONFLICTING
INSUFFICIENT_EVIDENCE
Example
Invoice:
100 licenses

Purchase Order:
100 licenses

Delivery record:
90 licenses

Customer objection:
10 licenses not delivered

Expected result:

SUPPORTED
Acceptance criteria
Evidence must be cited for material conclusions.
Conflicting evidence must be surfaced rather than silently resolved.
Missing evidence must prevent unsupported financial conclusions.
The LLM must not directly modify invoice financial values.
7. UC-05 — Determine Collectible Amount
Objective

Determine what portion of an overdue receivable is supported as collectible.

Trigger

Evidence analysis produces sufficiently reliable facts.

Input
invoice amount,
line-item facts,
verified dispute amount,
payment history,
relevant commercial evidence.
Expected behavior

The system separates:

Total receivable
Disputed amount
Collectible amount
Recovered amount
Remaining collectible amount
Example
Invoice                 ₹10,00,000
Verified dispute         ₹1,00,000
Collectible amount       ₹9,00,000
Critical requirement

The LLM must not perform the authoritative financial calculation.

The LLM extracts facts.

Deterministic application logic calculates monetary values.

Acceptance criteria
Calculated amounts must reconcile with the invoice.
Recovery amount must never exceed verified collectible amount.
Unsupported or ambiguous amounts must not be used for autonomous recovery.
Partial recovery must be supported.
8. UC-06 — Propose Recovery Resolution
Objective

Determine the appropriate next action for the receivable.

Trigger

The collectible amount and evidence assessment are available.

Input
issue classification,
evidence assessment,
collectible amount,
customer context,
current case state,
merchant policy context.
Expected behavior

The Resolution Agent creates a structured proposal.

Possible proposals include:

CREATE_FULL_RECOVERY
CREATE_PARTIAL_RECOVERY
REQUEST_DOCUMENT
REQUEST_CORRECTION
WAIT_FOR_PROMISE
STOP_OUTREACH
ESCALATE_HUMAN
ESCALATE_LEGAL
Acceptance criteria
Proposal contains a specific action.
Monetary proposals contain an exact amount or explicitly indicate that no amount can safely be determined.
Proposal references supporting evidence.
Proposal cannot directly execute the action.
Invalid or malformed AI output is rejected.
9. UC-07 — Validate Resolution Against Policy
Objective

Determine whether a proposed recovery action is permitted.

Trigger

A Resolution Proposal is produced.

Input
proposed action,
proposed amount,
recovery case,
merchant policy,
evidence assessment,
current timestamp,
recovery history.
Expected behavior

The deterministic Policy Engine evaluates:

evidence sufficiency,
collectible amount,
automated recovery limit,
concession limit,
outreach count,
quiet hours,
legal lock,
human approval requirements,
current case state.
Possible outcomes
APPROVED
DEFERRED
HUMAN_APPROVAL_REQUIRED
BLOCKED
STOPPED
Acceptance criteria
LLM output cannot bypass policy evaluation.
Policy decisions are deterministic for identical inputs.
The policy version is recorded.
Every blocked or deferred action has an explicit reason.
10. UC-08 — Execute Approved Recovery
Objective

Execute a recovery action that has passed policy validation.

Trigger

Policy Engine returns:

APPROVED
Input
approved recovery action,
recovery case,
verified collectible amount,
execution context.
Expected behavior

The system calls the Razorpay integration to create the appropriate payment request.

For partial recovery:

Parent invoice:
₹10,00,000

Approved recovery:
₹9,00,000

Remaining disputed amount:
₹1,00,000

The application records a reference linking the recovery action to the parent receivable.

Acceptance criteria
Execution is possible only from a valid state.
Financial amount is revalidated before execution.
External payment references are persisted.
Payment-link creation does not itself mark the receivable as recovered.
An audit event is written.
11. UC-09 — Confirm Recovery Through Razorpay Webhook
Objective

Update the recovery state using verified external payment events.

Trigger

A Razorpay payment event is received.

Expected behavior

The webhook handler:

verifies the webhook signature,
validates the event structure,
checks idempotency,
identifies the associated recovery action,
updates payment status,
triggers a valid state transition, and
records an audit event.
Acceptance criteria
Invalid webhook signatures are rejected.
Duplicate events are processed idempotently.
A payment cannot be marked successful solely because a payment request was created.
The recovery case is updated only after verified payment evidence.
External event identifiers are recorded.
12. UC-10 — Handle Partial Recovery
Objective

Correctly represent a case where only part of the original receivable is recovered.

Example
Original invoice:       ₹10,00,000
Recovered:                ₹9,00,000
Remaining dispute:        ₹1,00,000
Expected behavior

The case becomes:

PARTIALLY_RECOVERED

The remaining disputed portion continues through its own resolution or escalation path.

Acceptance criteria
Recovered amount is calculated deterministically.
Remaining balance is correct.
The original invoice is not incorrectly marked fully paid.
The audit trail records the partial recovery.
The remaining disputed amount remains traceable.
13. UC-11 — Stop Automation for Legal or High-Risk Conditions
Objective

Prevent automated recovery when the customer communication introduces a high-risk or legal condition.

Trigger

A customer communication contains a qualifying legal/high-risk signal.

Examples:

legal notice,
lawyer/counsel involvement,
court action,
police complaint,
fraud allegation,
explicit instruction to stop automated contact.
Expected behavior

The system:

LOCK AUTOMATION
      ↓
STOP AUTOMATED OUTREACH
      ↓
STOP AUTOMATED RECOVERY
      ↓
ESCALATE
Acceptance criteria
The legal lock cannot be overridden by the LLM.
No subsequent automated recovery action can bypass the lock.
The reason for the lock is recorded.
The case is available to a human reviewer.
14. UC-12 — Enforce Outreach Limits
Objective

Prevent excessive automated customer contact.

Example policy
Maximum touchpoints:
3

Time window:
14 days
Expected behavior

Before every outbound action, the Policy Engine checks the touchpoint history.

If the limit has been reached:

STOP_OUTREACH

The case may then be routed to human review.

Acceptance criteria
The fourth automated touchpoint is rejected.
Touchpoint count is calculated from recorded events rather than model claims.
The blocking decision is auditable.
Quiet hours and other contact rules are enforced.
15. UC-13 — Enforce Financial Concession Limits
Objective

Prevent the AI from granting unauthorized discounts or concessions.

Example policy
Maximum concession:
min(
    5% of invoice amount,
    ₹25,000
)
Expected behavior

If a proposal exceeds the merchant's automated authority:

HUMAN_APPROVAL_REQUIRED

or:

BLOCKED

depending on policy configuration.

Acceptance criteria
The limit is enforced deterministically.
LLM instructions cannot override the limit.
Human approval, when required, is tied to the exact action and amount.
The approval state is auditable.
16. UC-14 — Handle Insufficient Evidence
Objective

Prevent the system from inventing a collectible amount when the available evidence is inadequate.

Example

Available information:

Invoice:
₹10,00,000

Customer:
"About ₹2–3 lakh is disputed."

PO:
Missing

GRN:
Missing
Expected behavior

The system does not guess the exact collectible amount.

Instead:

EVIDENCE_INSUFFICIENT
        ↓
HUMAN_REVIEW
Acceptance criteria
No automatic financial action is executed.
Missing evidence is shown to the user.
The system identifies what evidence is required.
The case remains fully auditable.
17. UC-15 — Handle Conflicting Evidence
Objective

Prevent automatic recovery when important business evidence materially conflicts.

Example
GRN:
90 units delivered

Customer email:
80 units delivered
Expected behavior
EVIDENCE_CONFLICT
        ↓
NO_AUTOMATIC_RECOVERY
        ↓
HUMAN_REVIEW
Acceptance criteria
Conflicting values are preserved.
The system identifies the sources of the conflict.
The AI cannot silently select one value as truth.
No unsupported recovery action is executed.
18. UC-16 — Human Approval
Objective

Allow a finance operator to approve a legitimate action that is outside autonomous authority.

Example
Verified collectible:
₹9,00,000

Automated authority:
₹5,00,000

The system requests approval.

The human sees:

proposed amount,
reason,
supporting evidence,
policy rule requiring approval,
current case state.
Acceptance criteria
Approval is tied to one specific proposal.
Changing the amount invalidates the prior approval.
The approver is recorded.
Approval generates an audit event.
Rejected actions cannot be executed.
19. UC-17 — Graceful Execution Failure
Objective

Handle failures in external payment execution without incorrectly marking revenue as recovered.

Example

Razorpay API is temporarily unavailable.

Expected behavior
RECOVERY_APPROVED
        ↓
EXECUTION_FAILED
        ↓
RETRYABLE_ERROR

If retries are exhausted:

HUMAN_REVIEW
Acceptance criteria
Payment failure does not become payment success.
Retry behavior follows configured limits.
Failed execution is visible to the operator.
The case retains an audit record of the failure.
20. UC-18 — Audit Every Material Decision
Objective

Provide complete traceability for recovery actions.

Material events include
RECOVERY_CASE_CREATED
TRIAGE_COMPLETED
EVIDENCE_RETRIEVED
EVIDENCE_CONFLICT_DETECTED
DISPUTE_VERIFIED
COLLECTIBLE_AMOUNT_CALCULATED
RESOLUTION_PROPOSED
POLICY_CHECKED
HUMAN_APPROVAL_REQUESTED
HUMAN_APPROVAL_GRANTED
RECOVERY_INITIATED
PAYMENT_LINK_CREATED
PAYMENT_CONFIRMED
PARTIAL_RECOVERY_COMPLETED
LEGAL_LOCK_APPLIED
ESCALATED_TO_HUMAN
EXECUTION_FAILED
CASE_CLOSED
Acceptance criteria

Every material financial decision must be traceable to:

the case,
the actor/component,
the time,
the relevant evidence,
the applicable policy version,
the state transition,
the external payment reference where applicable.
21. UC-19 — Batch Recovery Evaluation
Objective

Measure system performance across multiple receivables rather than relying on a single demonstration case.

Input

A benchmark dataset containing at least 50 synthetic B2B cases.

Target benchmark size:

100 cases
Expected behavior

For each case the system executes the relevant workflow and compares the result to ground truth.

Metrics include
recovery rate,
resolution accuracy,
collectible-amount accuracy,
policy violation rate,
unsupported recovery rate,
human escalation rate,
cycle-time reduction.
Acceptance criteria
Ground truth is not exposed to the inference system.
Every test case produces a result.
Per-case outcomes are retained.
Aggregate metrics are reproducible.
Safety violations are reported separately from recovery performance.
22. UC-20 — Identify Revenue Friction Patterns
Status

Post-MVP enhancement

Objective

Use historical recovery cases to identify recurring operational causes of delayed revenue.

Example:

32% of delayed receivables:
PO mismatch

21%:
payment failure

18%:
quantity dispute

The system can surface patterns and recommend upstream process improvements.

This capability is not required for the initial MVP.

23. Use-Case Priority
P0 — Mandatory MVP
UC-01  Detect At-Risk Receivable
UC-02  Triage Reason for Non-Payment
UC-03  Gather Relevant Evidence
UC-04  Verify Commercial/Operational Objection
UC-05  Determine Collectible Amount
UC-06  Propose Recovery Resolution
UC-07  Validate Resolution Against Policy
UC-08  Execute Approved Recovery
UC-09  Confirm Recovery Through Razorpay Webhook
UC-10  Handle Partial Recovery
UC-11  Legal/High-Risk Stop
UC-12  Outreach Limits
UC-13  Financial Concession Limits
UC-14  Insufficient Evidence
UC-15  Conflicting Evidence
UC-16  Human Approval
UC-17  Execution Failure
UC-18  Audit Trail
UC-19  Batch Evaluation
P1 — Strong post-MVP enhancements
UC-20  Revenue Friction Analytics
Promise-to-pay intelligence
Root-cause prevention
Adaptive recovery playbooks
24. Core Product Invariants

Across all use cases, the following principles must remain true:

Invariant 1

The AI cannot directly execute a financial action.

Invariant 2

A recovery amount cannot exceed the verified collectible amount.

Invariant 3

A payment cannot be considered successful without verified payment evidence.

Invariant 4

Legal/high-risk locks prevent autonomous financial actions and automated outreach.

Invariant 5

Policy limits cannot be overridden by the LLM.

Invariant 6

Conflicting or insufficient evidence cannot produce an autonomous recovery amount.

Invariant 7

Every material financial decision must be auditable.

Invariant 8

Financial amounts must be calculated deterministically.

Invariant 9

Valid state transitions are controlled by the state machine.

Invariant 10

Benchmark ground truth must never be supplied to the inference path.