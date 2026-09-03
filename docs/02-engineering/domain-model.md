# Domain Model

## 1. Purpose

This document defines the core business entities used by the Receivables Resolution Agent.

The domain model represents the financial and operational objects involved in detecting, diagnosing, resolving, and recovering overdue B2B receivables.

The model deliberately separates:

- financial records,
- recovery workflow state,
- AI reasoning,
- evidence,
- policy decisions,
- financial execution, and
- audit history.

---

# 2. Domain Principles

## 2.1 Invoice and Recovery Case are different concepts

An **Invoice** represents the financial obligation.

A **Recovery Case** represents the operational workflow attempting to recover that obligation.

One invoice may have one active recovery case at a time for a given recovery workflow, but the invoice can remain a persistent financial record independently of the recovery process.

---

## 2.2 AI output is not financial truth

AI components produce structured interpretations and recommendations.

Financial truth is established through:

- persisted financial records,
- deterministic calculations,
- policy validation,
- valid state transitions, and
- verified external payment events.

---

## 2.3 Evidence must remain traceable

A material conclusion about a disputed or collectible amount must be traceable to the business evidence used to establish it.

---

## 2.4 Payment and payment-request actions are different

A recovery action may request payment.

A Payment represents actual payment state.

Creating a payment request does not imply that money was received.

---

## 2.5 Recovery and settlement are different

Recovery concerns collecting money from the customer.

Settlement refers to the payment provider's downstream transfer of collected funds to the merchant.

This project primarily models receivable recovery.

---

# 3. Entity Overview

Core entities:

```text
Merchant
Customer
MerchantPolicy
Invoice
InvoiceLine
RecoveryCase
Dispute
Evidence
AgentRun
ResolutionProposal
PolicyDecision
RecoveryAction
Payment
Outreach
HumanApproval
AuditEvent
4. Merchant
Purpose

Represents the business using the Receivables Resolution Agent.

Key attributes
id
name
currency
created_at
updated_at

A merchant may have one or more customer accounts and one or more policy versions.

5. Customer
Purpose

Represents a business customer that owes money to the merchant.

Key attributes
id
merchant_id
name
email
phone
gstin
external_customer_id
created_at
updated_at
Relationship
Merchant 1 ─── N Customer
6. Merchant Policy
Purpose

Represents the deterministic rules governing autonomous recovery for a merchant.

Key attributes
id
merchant_id

max_auto_recovery_amount

max_concession_percent
max_concession_amount

max_touchpoints
touchpoint_window_days

quiet_hours_start
quiet_hours_end

high_value_threshold

version

effective_from
effective_to

created_at
Principle

Policies are versioned.

A historical recovery decision must remain explainable under the policy version that was active when the decision occurred.

7. Invoice
Purpose

Represents the customer's financial obligation to the merchant.

Key attributes
id
merchant_id
customer_id

invoice_number
currency

total_amount
amount_paid

issue_date
due_date

status

external_reference

created_at
updated_at

The Invoice is the primary financial object.

8. Invoice Line
Purpose

Represents an individual line item within an invoice.

Key attributes
id
invoice_id

line_number
description
product_code

quantity
unit_price
tax_amount
line_total
Relationship
Invoice 1 ─── N InvoiceLine

Line-level information supports quantity, price, and delivery disputes.

9. Recovery Case
Purpose

Represents the operational recovery workflow for an invoice.

Key attributes
id
merchant_id
customer_id
invoice_id

status

issue_type
risk_level

claimed_disputed_amount
verified_disputed_amount

collectible_amount
safely_recoverable_amount
recovered_amount
remaining_amount

resolution_confidence

touchpoint_count

locked
lock_reason

created_at
updated_at
Principle

Amounts produced during AI analysis are not automatically authoritative.

The application must distinguish between:

Customer claim
        ↓
Evidence assessment
        ↓
Verified financial assessment
        ↓
Approved recovery action
        ↓
Actual recovered amount
10. Recovery Case Status

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

The state-transition rules are defined separately in state-machine.md.

11. Issue Type

The primary issue classification is one of:

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

The system may later support additional classifications.

12. Dispute
Purpose

Represents a commercial objection associated with a Recovery Case.

Key attributes
id
case_id

type

customer_claim
claimed_amount
verified_amount

status

opened_at
resolved_at
Important distinction

claimed_amount represents what the customer says is disputed.

verified_amount represents what the available evidence supports as genuinely disputed.

These values must not be implicitly treated as identical.

13. Evidence
Purpose

Represents a business record used to support or challenge a recovery assessment.

Evidence types
INVOICE
PURCHASE_ORDER
GRN
DELIVERY_RECORD
CONTRACT
MILESTONE_RECORD
CUSTOMER_EMAIL
PAYMENT_RECORD
CREDIT_NOTE
Key attributes
id
case_id

type
source
external_reference

content
structured_data

created_at

Evidence must retain provenance.

14. Evidence Finding

A material conclusion extracted from evidence should be represented as a structured finding.

Conceptually:

Evidence
   ↓
Finding
   ↓
Claim / fact
   ↓
Supporting evidence

Example:

Claim:
90 licenses delivered

Source:
GRN-1194

Status:
SUPPORTED

The implementation may represent findings as JSONB within the evidence record initially, with a separate table introduced if the model becomes sufficiently complex.

15. Agent Run
Purpose

Records an individual execution of an AI reasoning component.

Key attributes
id
case_id

agent_type
model_name
prompt_version

input_hash
output_json

latency_ms
token_usage

success
error

created_at
Purpose beyond logging

This enables:

debugging,
prompt/version tracking,
reproducibility,
evaluation analysis,
comparison between model configurations.
16. Resolution Proposal
Purpose

Represents an action recommendation produced by the AI reasoning layer.

Key attributes
id
case_id
agent_run_id

action_type

proposed_amount
reason_code

confidence

evidence_ids

status

created_at

Possible actions include:

CREATE_FULL_RECOVERY
CREATE_PARTIAL_RECOVERY
REQUEST_DOCUMENT
REQUEST_CORRECTION
WAIT_FOR_PROMISE
STOP_OUTREACH
ESCALATE_HUMAN
ESCALATE_LEGAL

A Resolution Proposal is not executable by itself.

17. Policy Decision
Purpose

Represents the deterministic decision produced by the Policy Engine for a Resolution Proposal.

Key attributes
id
case_id
proposal_id

decision

policy_version

checks_json

blocking_reason

created_at

Possible decisions:

APPROVED
DEFERRED
HUMAN_APPROVAL_REQUIRED
BLOCKED
STOPPED
18. Recovery Action
Purpose

Represents an operational action actually initiated by the system.

Key attributes
id
case_id
proposal_id
policy_decision_id

type
amount

status

external_provider
external_reference

reason

created_at
executed_at

A Recovery Action can only be created/executed when the relevant policy and state requirements are satisfied.

19. Payment
Purpose

Represents actual payment state associated with a Recovery Action.

Key attributes
id

invoice_id
case_id
recovery_action_id

razorpay_payment_id
razorpay_payment_link_id

amount
currency

status

paid_at

created_at
updated_at

The Payment entity represents actual payment state, not merely a requested recovery.

20. Outreach
Purpose

Records customer-contact attempts associated with a recovery case.

Key attributes
id
case_id

channel
direction
purpose

message_reference
status

sent_at

Possible channels:

EMAIL
WHATSAPP
SMS
VOICE

The MVP may simulate outbound communication while preserving the domain model required for touchpoint enforcement.

21. Human Approval
Purpose

Records explicit human authorization for actions outside autonomous authority.

Key attributes
id
case_id
action_id

requested_amount

decision

approved_by
reason

created_at
resolved_at

Approval must be bound to the exact action and amount.

22. Audit Event
Purpose

Represents an immutable record of a material workflow action, decision, or state transition.

Key attributes
id
case_id

event_type

actor_type
actor_id

state_before
state_after

payload_json

policy_version

external_event_id

created_at

Examples:

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
23. Entity Relationships

The primary domain relationship is:

Merchant
   │
   ├── Customer
   │      │
   │      └── Invoice
   │             │
   │             ├── InvoiceLine
   │             │
   │             └── RecoveryCase
   │                    │
   │                    ├── Dispute
   │                    ├── Evidence
   │                    ├── AgentRun
   │                    ├── ResolutionProposal
   │                    ├── PolicyDecision
   │                    ├── RecoveryAction
   │                    │       │
   │                    │       └── Payment
   │                    │
   │                    ├── Outreach
   │                    ├── HumanApproval
   │                    └── AuditEvent
   │
   └── MerchantPolicy
24. Financial Value Flow

The financial value represented by the domain progresses through:

Invoice Amount
      ↓
Outstanding Amount
      ↓
Customer Claimed Dispute
      ↓
Verified Disputed Amount
      ↓
Verified Collectible Amount
      ↓
Approved Recovery Amount
      ↓
Actual Recovered Amount

These values must not be conflated.

25. Domain Rules
Rule 1

An Invoice is a financial record.

A Recovery Case is an operational workflow.

Rule 2

A customer's claim is not automatically a verified dispute.

Rule 3

An LLM recommendation is not a policy decision.

Rule 4

A policy decision is not a payment.

Rule 5

A payment request is not a confirmed payment.

Rule 6

Only verified payment evidence can establish successful recovery.

Rule 7

Material financial decisions require evidence provenance.

Rule 8

Financial calculations are deterministic.

Rule 9

Recovery amounts cannot exceed verified collectible amounts.

Rule 10

Legal locks and policy restrictions cannot be bypassed by AI components.

26. Financial Invariants

At any valid recovery state:

recovered_amount >= 0
verified_disputed_amount >= 0
collectible_amount >= 0

And:

recovered_amount <= invoice_amount

Recovery execution must satisfy:

recovery_action_amount <= verified_collectible_amount

where applicable.

The system must prevent negative or inconsistent balances.

27. Domain Boundary

The MVP is responsible for:

Receivable diagnosis
Evidence analysis
Recovery decisioning
Policy enforcement
Recovery execution orchestration
Payment-state tracking
Escalation
Auditability

The MVP is not responsible for:

Full accounting
Provider-side settlement
Legal adjudication
ERP replacement
Government tax validation
General-purpose customer support
28. Architectural Principle

The domain model intentionally separates:

What is owed
        ↓
Why it is stuck
        ↓
What evidence says
        ↓
What AI recommends
        ↓
What policy permits
        ↓
What action occurred
        ↓
What payment actually happened

This separation is fundamental to the reliability of the system.