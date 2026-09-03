# Solution Overview

## 1. Product

**Receivables Resolution Agent**

An AI-powered B2B receivables recovery system that identifies why an overdue invoice is stuck, verifies the underlying issue against available business evidence, determines the legitimately collectible amount, and executes bounded recovery actions through Razorpay.

The system is designed for finance and accounts-receivable teams that manage large volumes of overdue B2B invoices.

---

## 2. Core Product Idea

The central idea is:

> **Do not chase the invoice blindly. Resolve the blocker behind the invoice and recover the amount that is legitimately collectible.**

A conventional collection workflow may treat an overdue invoice as a single unpaid amount.

Receivables Resolution Agent instead decomposes the problem into:

```text
Overdue receivable
        ↓
Why is payment blocked?
        ↓
What does the evidence show?
        ↓
What amount is genuinely collectible?
        ↓
What intervention is appropriate?
        ↓
Is automated action permitted?
        ↓
Recover / defer / escalate

This allows the system to distinguish between money that can be recovered immediately and money that is genuinely blocked by an unresolved issue.

3. How the Product Works

The system follows a controlled recovery workflow.

Step 1 — Detect

Identify overdue or otherwise at-risk receivables.

Signals may include:

invoice due date,
payment failure,
customer communication,
promise-to-pay breach,
repeated failed recovery attempts,
unresolved commercial disputes.

The system creates or updates a recovery case for the receivable.

Step 2 — Triage

The Triage Agent analyzes the available case context and identifies the most likely reason payment is blocked.

Examples:

payment failure,
quantity dispute,
price dispute,
purchase-order mismatch,
GST/documentation issue,
milestone pending,
service-delivery dispute,
credit-note request,
promise-to-pay breach,
legal/high-risk condition.

The Triage Agent produces a structured classification rather than executing any financial action.

Step 3 — Evidence Analysis

The Evidence Agent examines the business evidence relevant to the identified issue.

Possible evidence sources include:

invoice,
invoice line items,
purchase order,
delivery/GRN records,
contracts,
milestone records,
customer communications,
payment history,
credit notes.

The system extracts facts and links conclusions to their supporting evidence.

For example:

Invoice:
100 licenses

Purchase Order:
100 licenses

Delivery Record:
90 licenses

Customer objection:
10 licenses not delivered

The system can therefore determine:

Invoice amount        ₹10,00,000
Evidence-supported
dispute               ₹1,00,000
Potentially collectible
amount                ₹9,00,000

The financial calculation itself is deterministic.

4. Collectible Amount Decomposition

A key product capability is distinguishing between:

Total receivable

The full amount represented by the invoice.

Disputed amount

The amount supported by evidence as genuinely contested or blocked.

Collectible amount

The amount established by deterministic financial calculation from the invoice,
verified payments, verified dispute information, and available evidence.

Collectible amount is a financial assessment, not policy authorization or
execution permission. A proposed recovery still requires Policy Engine and
State Machine validation, and human approval where required.

This enables partial recovery.

For example:

Invoice                     ₹10,00,000
Disputed                    ₹1,00,000
Collectible now             ₹9,00,000

The system does not require the entire invoice to be resolved before attempting to recover the undisputed portion.

5. Resolution Recommendation

The Resolution Agent uses the triage result and evidence assessment to recommend the next intervention.

Possible outcomes include:

CREATE_FULL_RECOVERY
CREATE_PARTIAL_RECOVERY
REQUEST_DOCUMENT
REQUEST_CORRECTION
WAIT_FOR_PROMISE
STOP_OUTREACH
ESCALATE_HUMAN
ESCALATE_LEGAL

The Resolution Agent produces a structured proposal.

It does not directly execute the action.

6. Deterministic Policy Control

Every proposed financial or customer-facing action passes through a deterministic Policy Engine before execution.

The Policy Engine evaluates constraints such as:

maximum automated recovery amount,
evidence sufficiency,
concession limits,
customer-contact limits,
quiet hours,
merchant-specific approval thresholds,
legal-risk locks,
current recovery-case state.

The LLM cannot bypass these controls.

The system therefore separates:

AI reasoning
    ↓
Recommendation
    ↓
Deterministic policy validation
    ↓
State-machine validation
    ↓
Execution
7. Partial Recovery Through Razorpay

When a partial recovery is approved, the system creates a Razorpay payment request for the approved collectible amount.

Example:

Parent Invoice
INV-1042
₹10,00,000

Verified disputed amount
₹1,00,000

Approved recovery amount
₹9,00,000

The recovery action contains application-level metadata linking the payment request back to the original receivable and recovery case.

The system does not treat payment-request creation as successful recovery.

The case remains in a pending state until a verified payment event is received.

8. Webhook-Driven Financial State

Razorpay payment events are treated as the source of truth for payment completion.

The workflow is:

Recovery approved
        ↓
Payment request created
        ↓
PAYMENT_PENDING
        ↓
Razorpay payment event
        ↓
Webhook verification
        ↓
Payment state updated
        ↓
Recovery case state updated

For example:

PAYMENT_PENDING
       ↓
Verified PAYMENT_CONFIRMED domain event
       ↓
PARTIALLY_RECOVERED

or:

PAYMENT_PENDING
       ↓
Verified PAYMENT_CONFIRMED domain event
       ↓
FULLY_RECOVERED

Duplicate webhook events must be handled idempotently.

9. Safe Failure and Escalation

The system is intentionally designed to stop when it cannot act safely.

Examples include:

Insufficient evidence

If the system cannot establish the disputed or collectible amount with sufficient evidence, it does not guess.

EVIDENCE_INSUFFICIENT
        ↓
HUMAN_REVIEW
Conflicting evidence

If relevant business records conflict:

EVIDENCE_CONFLICT
        ↓
NO_AUTOMATIC_RECOVERY
        ↓
HUMAN_REVIEW
Legal-risk condition

If customer communication indicates a significant legal-risk condition:

LEGAL_RISK
        ↓
AUTOMATION_LOCKED
        ↓
LEGAL_ESCALATION
Policy violation

If a proposed action exceeds merchant-defined authority:

POLICY_CHECK
      ↓
BLOCKED / HUMAN_APPROVAL_REQUIRED

The system should prefer safe escalation over unsafe automation.

10. Auditability

Every significant state change and financial decision is recorded.

An example case trace:

Invoice Overdue
      ↓
Objection Detected
      ↓
Evidence Retrieved
      ↓
Dispute Verified
      ↓
Collectible Amount Calculated
      ↓
Resolution Proposed
      ↓
Policy Check Passed
      ↓
Payment Request Created
      ↓
Payment Webhook Verified
      ↓
Recovery State Updated

Each audit event records enough structured information to answer:

what happened,
when it happened,
which component initiated it,
what evidence was used,
what policy version applied,
what state changed,
what external payment reference was involved.

The audit system records decision facts and provenance; it does not depend on exposing private LLM chain-of-thought.

11. Core Differentiation

The project is not designed to compete with basic payment reminder or outbound collection workflows.

Its differentiation is the resolution layer before recovery.

Traditional pattern:

Invoice overdue
      ↓
Reminder
      ↓
Reminder
      ↓
Escalation

Receivables Resolution Agent:

Invoice overdue
      ↓
Understand blocker
      ↓
Verify evidence
      ↓
Decompose collectible amount
      ↓
Choose bounded intervention
      ↓
Recover legitimate amount
      ↓
Resolve or escalate remainder

The product therefore focuses on reducing the amount of legitimately collectible revenue that remains unnecessarily blocked.

12. AI Boundary

AI is responsible for semantic work such as:

interpreting customer communications,
classifying the payment blocker,
extracting relevant facts,
identifying supporting evidence,
producing a resolution recommendation.

AI is not the authority for:

final financial calculations,
policy enforcement,
state transitions,
payment confirmation,
direct payment execution,
overriding safety controls.

The governing principle is:

The LLM can interpret and recommend; deterministic systems calculate, authorize, transition, and execute.

13. Track 03 Alignment

The product directly maps to the Track 03 requirements:

Track requirement	Receivables Resolution Agent
Detect revenue at risk	Detect overdue and blocked receivables
Determine the right intervention	Diagnose blocker and recommend resolution
Execute a bounded recovery workflow	Policy-gated Razorpay recovery
Show measured money recovered	Batch-level evaluation
Compliant escalation	Human/legal escalation paths
Stopping rules	Legal, evidence, contact, and financial limits
Audit trail	Immutable recovery-case event history
14. Measurable Product Outcome

The primary outcome is not the number of AI decisions produced.

It is:

How much legitimate receivable value was recovered safely?

The system will therefore measure:

total receivables at risk,
safely recoverable amount,
automatically recovered amount,
recovery rate,
resolution accuracy,
human escalation,
cycle-time reduction,
unsupported recovery attempts,
policy violations.

The target is not maximum automation.

The target is:

Maximum safe, evidence-supported recovery within defined merchant policies.

15. Future Extensions

The MVP focuses on resolving and recovering blocked B2B receivables.

Future capabilities may include:

revenue-friction analytics,
recurring root-cause detection,
upstream invoice-quality recommendations,
promise-to-pay intelligence,
customer-level recovery patterns,
adaptive recovery playbooks,
deeper ERP integrations,
additional communication channels.

These extensions are not required for the initial MVP and must not compromise the core recovery workflow.
