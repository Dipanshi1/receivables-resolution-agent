# MVP Scope

## 1. Purpose

This document defines the minimum product that must be fully working for the Razorpay Buildathon Track 03 submission.

The MVP must demonstrate the complete revenue-recovery loop:

```text
Revenue at Risk
      ↓
Problem Diagnosis
      ↓
Evidence Analysis
      ↓
Recovery Decision
      ↓
Policy Validation
      ↓
Bounded Recovery Action
      ↓
Payment Confirmation
      ↓
Measured Recovery
      ↓
Audit / Escalation

The MVP is intentionally narrower than a full enterprise receivables platform.

The objective is to build one complete, reliable, testable financial workflow rather than a large collection of partially implemented features.

2. MVP Product Definition

The MVP is:

An AI-assisted B2B receivables resolution system that analyzes overdue invoices and supporting business evidence, determines the evidence-supported collectible amount, proposes a recovery action, validates that action against deterministic merchant policies, executes an approved recovery action through Razorpay, verifies payment through webhook events, and safely escalates cases that cannot be resolved automatically.

3. Primary MVP User
Finance / Accounts Receivable Operator

The primary user must be able to:

view revenue at risk,
inspect recovery cases,
understand why a receivable is blocked,
review evidence,
see the collectible and disputed amounts,
see the recommended action,
see whether the action is approved, blocked, deferred, or requires approval,
inspect payment/recovery status, and
inspect the audit trail.
4. MVP Functional Capabilities
MVP-01 — Revenue-at-Risk Detection

The system must identify an overdue or otherwise configured at-risk receivable and create a Recovery Case.

Required inputs
merchant,
customer,
invoice,
invoice line items,
due date,
payment status,
relevant communications.
Required output

A Recovery Case with:

case identifier,
invoice identifier,
amount at risk,
trigger reason,
initial state.
MVP-02 — AI Triage

The system must classify the likely reason that the receivable is not being recovered.

Supported initial issue types:

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

The Triage Agent must return structured output.

It must not directly execute financial actions.

MVP-03 — Evidence Analysis

The system must analyze relevant evidence associated with the case.

Initial evidence types:

INVOICE
PURCHASE_ORDER
DELIVERY_RECORD
GRN
CONTRACT
MILESTONE_RECORD
CUSTOMER_EMAIL
PAYMENT_RECORD
CREDIT_NOTE

The system must:

retrieve relevant evidence,
extract structured facts,
associate findings with evidence references,
identify missing evidence,
identify conflicting evidence.
MVP-04 — Collectible Amount Determination

The system must distinguish between:

TOTAL RECEIVABLE
DISPUTED AMOUNT
COLLECTIBLE AMOUNT
RECOVERED AMOUNT
REMAINING BALANCE

Example:

Total receivable      ₹10,00,000
Verified dispute       ₹1,00,000
Collectible amount     ₹9,00,000

The authoritative monetary calculation must be deterministic.

The LLM may extract facts but must not be the final authority for arithmetic.

MVP-05 — Resolution Recommendation

The Resolution Agent must produce a structured recovery proposal.

Supported initial actions:

CREATE_FULL_RECOVERY
CREATE_PARTIAL_RECOVERY
REQUEST_DOCUMENT
REQUEST_CORRECTION
WAIT_FOR_PROMISE
STOP_OUTREACH
ESCALATE_HUMAN
ESCALATE_LEGAL

The proposal must contain:

action,
amount where applicable,
reason,
evidence references,
confidence,
human-approval requirement where known.

The proposal is not itself an authorization.

MVP-06 — Deterministic Policy Engine

Every executable recovery action must pass through the Policy Engine.

Initial policy controls:

Financial authority

Maximum amount permitted for automated recovery.

Evidence support

Recovery amount must not exceed the verified collectible amount.

Concession cap

Automated concessions must remain within configured merchant limits.

Outreach limit

Automated customer-contact attempts must remain within configured limits.

Quiet hours

Customer-facing actions must respect merchant-defined contact windows.

Legal lock

High-risk/legal conditions must stop autonomous recovery and outreach.

Human approval

Actions outside autonomous authority must require explicit human approval.

MVP-07 — Deterministic State Machine

The system must control Recovery Case state transitions.

Initial states:

OVERDUE
TRIAGING
ISSUE_IDENTIFIED
EVIDENCE_ANALYSIS
RESOLUTION_READY
POLICY_REVIEW
RECOVERY_INITIATED
PAYMENT_PENDING
PARTIALLY_RECOVERED
FULLY_RECOVERED
HUMAN_REVIEW
LEGAL_ESCALATION
AUTOMATION_LOCKED
EXECUTION_FAILED
CLOSED

The LLM must not directly mutate recovery state.

MVP-08 — Razorpay Recovery Execution

For an approved recovery action, the backend must use Razorpay test-mode capabilities to create the appropriate payment request.

The MVP must support the canonical partial-recovery scenario.

Example:

Parent invoice:
₹10,00,000

Verified disputed amount:
₹1,00,000

Proposed recovery:
₹9,00,000

Execution authorization:
Human approval required because the recovery amount exceeds the default autonomous authority of ₹5,00,000.

The recovery request must retain an application-level reference to:

merchant,
invoice,
recovery case,
recovery action,
recovery amount,
recovery reason.

The application must not treat payment-request creation as successful payment.

MVP-09 — Razorpay Webhook Processing

The system must process payment events from Razorpay.

The webhook workflow must:

receive the event,
verify authenticity,
validate the payload,
check idempotency,
identify the associated recovery action,
update the payment record,
perform a valid state transition, and
create an audit event.

A verified payment event is required before the system can classify the recovery as successful.

MVP-10 — Partial Recovery

The system must support a receivable where only part of the invoice can be recovered immediately.
The recovery amount may be determined before execution. Actual recovered amount is recorded only after verified payment evidence.

If the recovery amount exceeds configured autonomous authority, human approval is required before execution.
Example:

Invoice total          ₹10,00,000
Recovered               ₹9,00,000
Remaining disputed      ₹1,00,000

The final case state must be:

PARTIALLY_RECOVERED

unless the remaining balance is subsequently resolved and paid.

MVP-11 — Human Approval

The MVP must support human approval for actions that are legitimate but outside the configured autonomous authority.

The approval must be bound to:

specific recovery case,
specific proposal,
specific action,
specific amount,
approver,
timestamp.

Changing the action or amount invalidates the previous approval.

MVP-12 — Safe Escalation

The MVP must support at least:

Human review

For cases that cannot be safely resolved automatically.

Legal escalation

For cases containing a high-risk/legal signal.

Evidence escalation

For cases with insufficient or conflicting evidence.

MVP-13 — Stopping Rules

The MVP must implement deterministic stopping controls.

Initial controls:

Legal stop

High-risk/legal condition:

STOP AUTOMATION
STOP AUTOMATED OUTREACH
ESCALATE
Touchpoint stop

Maximum configured number of automated outreach attempts reached:

STOP OUTREACH
ESCALATE
Financial stop

Action exceeds automated financial authority:

NO AUTOMATIC EXECUTION
HUMAN APPROVAL REQUIRED
Evidence stop

Collectible amount cannot be established reliably:

NO AUTOMATIC RECOVERY
HUMAN REVIEW
MVP-14 — Audit Trail

The system must record material workflow events.

At minimum:

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

Each material event must retain enough information to reconstruct the case history.

5. MVP User Interface

The MVP frontend requires four primary views.

View 1 — Recovery Dashboard

Display:

total revenue at risk,
safely recoverable amount,
recovered amount,
cases requiring human attention,
blocked cases,
recent recoveries,
recovery-case list.
View 2 — Recovery Case Detail

Display:

invoice details,
customer,
amount at risk,
issue classification,
disputed amount,
collectible amount,
evidence,
proposed resolution,
policy decision,
recovery status,
remaining balance.
View 3 — Audit Trace

Display the chronological case event history.

Example:

Invoice overdue
      ↓
Objection detected
      ↓
Evidence retrieved
      ↓
Dispute verified
      ↓
Collectible amount calculated
      ↓
Policy evaluated
      ↓
Human approval required
      ↓
Human approval granted
      ↓
Recovery authorized
      ↓
Payment request created
      ↓
Payment confirmed
      ↓
Partial recovery completed
View 4 — Benchmark Results

Display:

number of cases,
total receivables,
safely recoverable amount,
automatically recovered amount,
recovery rate,
resolution accuracy,
unsupported recovery rate,
policy violation rate,
escalation rate,
cycle-time reduction.
6. MVP Evaluation

The MVP must be evaluated on a synthetic batch.

Minimum:

50 cases

Target:

100 cases

The benchmark should contain multiple case categories, including:

payment failures,
quantity disputes,
PO mismatches,
documentation issues,
milestone disputes,
price disputes,
partial disputes,
promise-to-pay failures,
legal/high-risk cases,
ambiguous/conflicting evidence.
7. MVP Safety Requirements

The following must have deterministic tests:

1. Recovery cannot exceed verified collectible amount.

2. Legal lock prevents automated recovery.

3. Legal lock prevents automated outreach.

4. Concession cap cannot be exceeded.

5. Touchpoint limit cannot be exceeded.

6. Human approval is required when autonomous authority is exceeded.

7. Payment cannot become confirmed without verified payment evidence.

8. Duplicate webhook events do not produce duplicate effects.

9. Invalid state transitions are rejected.

10. LLM output cannot directly mutate financial state.

11. LLM output cannot bypass the Policy Engine.

12. Insufficient/conflicting evidence cannot trigger unsupported recovery.
8. MVP Golden Scenario

The MVP must successfully demonstrate this end-to-end flow:

₹10,00,000 B2B invoice
        ↓
Customer disputes ₹1,00,000
        ↓
Triage Agent identifies quantity dispute
        ↓
Evidence Agent verifies:
100 ordered
90 delivered
        ↓
Deterministic calculation:
₹1,00,000 disputed
₹9,00,000 collectible
        ↓
Resolution Agent recommends:
CREATE_PARTIAL_RECOVERY
₹9,00,000
        ↓
Policy Engine evaluates:
₹9,00,000 exceeds autonomous authority
        ↓
HUMAN_APPROVAL_REQUIRED
        ↓
Finance approval granted
        ↓
RECOVERY_AUTHORIZED
        ↓
Razorpay payment request created
        ↓
Customer pays
        ↓
Verified Razorpay webhook
        ↓
PARTIALLY_RECOVERED
        ↓
₹9,00,000 recovered
₹1,00,000 remains disputed
        ↓
Complete audit trace
### Golden Scenario Authorization Rule

The ₹9,00,000 amount is the evidence-supported collectible amount, not an automatically authorized recovery amount.

Because the default autonomous recovery authority is ₹5,00,000, the Policy Engine must require explicit human approval before the ₹9,00,000 recovery can be executed.

Human approval must be bound to the specific recovery case, proposal, action, and amount.
9. MVP Failure Scenarios

The demonstration must also include at least one safe-failure path.

Recommended safe-failure demonstration

Customer communication contains a legal-risk signal.

Expected behavior:

Legal risk detected
        ↓
Automation locked
        ↓
No further automated outreach
        ↓
No automated recovery
        ↓
Human / legal escalation
        ↓
Audit event recorded

A second recommended failure case:

Conflicting evidence
        ↓
Collectible amount cannot be established
        ↓
Automatic recovery blocked
        ↓
Human review
10. Explicitly Out of MVP

The following are intentionally excluded from the first implementation:

Communication infrastructure
production IVR,
production WhatsApp integration,
production SMS infrastructure,
automated voice calling.
Enterprise integrations
full ERP integrations,
full accounting-suite integrations,
production GST verification,
production procurement-system integrations.
Advanced AI infrastructure
large autonomous multi-agent networks,
unrestricted agent-to-agent conversations,
long-term autonomous memory,
autonomous legal reasoning,
autonomous financial policy creation.
Enterprise platform concerns
full multi-tenant SaaS architecture,
complex distributed microservices,
production-scale event streaming,
advanced observability platforms.
Additional product directions
customer churn prediction,
fraud detection,
general-purpose financial assistant,
autonomous accounting,
full contract-management platform.

These may be considered only after the MVP passes its functional and evaluation gates.

11. Post-MVP Enhancements

After the MVP is stable, the following can be considered.

P1 — Revenue Friction Analytics

Identify recurring causes of delayed revenue.

Example:

32% → PO mismatch
21% → payment failure
18% → quantity dispute
14% → documentation
P1 — Root-Cause Prevention

Use historical cases to identify upstream business-process changes that could reduce future receivables risk.

P1 — Promise-to-Pay Intelligence

Track customer payment commitments and automatically detect missed promises.

P2 — Adaptive Recovery Strategies

Use historical outcomes to recommend more effective interventions while remaining inside deterministic policies.

P2 — Additional communication channels

Add controlled email, WhatsApp, SMS, or voice execution only after the core recovery workflow is stable.

12. Definition of MVP Complete

The MVP is complete only when all of the following are true:

[ ] One end-to-end recovery case works.

[ ] One partial-recovery case works.

[ ] One legal-stop case works.

[ ] One insufficient-evidence case works.

[ ] Razorpay test-mode payment execution works.

[ ] Razorpay webhook verification works.

[ ] Duplicate webhook handling works.

[ ] Policy invariants have automated tests.

[ ] State transitions have automated tests.

[ ] Audit trail reconstructs the case.

[ ] At least 50 benchmark cases can be evaluated.

[ ] Target benchmark is 100 cases.

[ ] Recovery metrics are generated automatically.

[ ] No unsupported recovery action is permitted.

[ ] No policy violation is permitted.
13. MVP Philosophy

The MVP prioritizes:

CORRECTNESS
    >
SAFE AUTOMATION
    >
MEASURABLE RECOVERY
    >
EXPLAINABILITY
    >
FEATURE COUNT

The objective is not to maximize the number of AI features.

The objective is to demonstrate a reliable closed-loop revenue-recovery system that can reason about messy B2B receivables while keeping financial execution deterministic and bounded.


## This is an important milestone

Now the product has a **hard boundary**.

The central MVP is:

```text
OVERDUE INVOICE
      ↓
AI DIAGNOSIS
      ↓
EVIDENCE
      ↓
COLLECTIBLE AMOUNT
      ↓
POLICY
      ↓
RAZORPAY RECOVERY
      ↓
WEBHOOK
      ↓
RECOVERY RESULT
      ↓
AUDIT / ESCALATION

Everything else is secondary.