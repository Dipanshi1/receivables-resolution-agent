# Database Schema

## 1. Purpose

This document defines the PostgreSQL schema for the Receivables Resolution Agent.

The schema is derived from the domain model and is intended to provide:

- strong relational integrity,
- exact monetary representation,
- auditable financial state,
- traceable AI decisions,
- deterministic policy enforcement,
- reliable Razorpay integration,
- idempotent webhook processing, and
- reproducible evaluation.

The database is a persistent record of domain and workflow state.

AI components must not directly modify financial state through unrestricted database access.

---

# 2. Database Technology

**PostgreSQL**

The application will use PostgreSQL as the primary persistent datastore.

ORM:

**SQLAlchemy 2.x**

Migration system:

**Alembic**

---

# 3. Monetary Representation

All authoritative monetary amounts must use an exact representation.

For the MVP, monetary values are stored as:

```text
BIGINT

representing the smallest currency unit.

For INR:

₹1 = 100 paise

Example:

₹9,00,000
=
90,000,000 paise

Floating-point numeric types must not be used for authoritative monetary calculations.

Where currency-specific precision is required in a future multi-currency implementation, the model may be extended accordingly.

4. Identifier Strategy

The application should use UUIDs for internal primary keys.

Examples:

merchant.id
customer.id
invoice.id
recovery_case.id

Human-readable external references such as:

INV-1042
CASE-1042
PO-7721

are stored separately.

This prevents external business identifiers from becoming database primary keys.

5. Common Timestamp Convention

All persistent timestamps should be stored using:

TIMESTAMPTZ

and normalized to UTC.

The application converts timestamps into the merchant/user timezone only when presenting them or evaluating time-dependent policies.

6. Common Database Conventions
Primary keys
id UUID PRIMARY KEY
Foreign keys

Foreign keys must explicitly reference parent entities.

Audit timestamps

Tables representing mutable entities should generally include:

created_at
updated_at
Enumerated states

Application-level enums should be represented consistently using PostgreSQL enums or validated text values.

The exact SQLAlchemy implementation may use Python enums mapped to database enum types.

7. merchants
Purpose

Stores the business using the Receivables Resolution Agent.

Columns
Column	Type	Constraints	Description
id	UUID	PK	Internal identifier
name	VARCHAR(255)	NOT NULL	Merchant name
currency	CHAR(3)	NOT NULL	ISO currency code
created_at	TIMESTAMPTZ	NOT NULL	Creation timestamp
updated_at	TIMESTAMPTZ	NOT NULL	Last update timestamp
Indexes
PRIMARY KEY (id)
8. customers
Purpose

Stores the merchant's B2B customers.

Columns
Column	Type	Constraints	Description
id	UUID	PK	Internal identifier
merchant_id	UUID	FK, NOT NULL	Owning merchant
name	VARCHAR(255)	NOT NULL	Customer name
email	VARCHAR(320)	NULL	Customer email
phone	VARCHAR(32)	NULL	Customer phone
gstin	VARCHAR(32)	NULL	GST identifier where available
external_customer_id	VARCHAR(255)	NULL	Merchant/ERP identifier
created_at	TIMESTAMPTZ	NOT NULL	Creation timestamp
updated_at	TIMESTAMPTZ	NOT NULL	Last update timestamp
Foreign keys
merchant_id → merchants.id
Indexes
INDEX customers_merchant_id_idx
INDEX customers_merchant_external_id_idx
9. merchant_policies
Purpose

Stores versioned merchant-specific recovery rules.

Columns
Column	Type	Constraints	Description
id	UUID	PK	Policy identifier
merchant_id	UUID	FK, NOT NULL	Merchant
version	VARCHAR(32)	NOT NULL	Policy version
max_auto_recovery_amount	BIGINT	NOT NULL	Maximum automatic recovery
max_concession_percent	NUMERIC(5,2)	NOT NULL	Maximum concession percentage
max_concession_amount	BIGINT	NOT NULL	Maximum absolute concession
max_touchpoints	INTEGER	NOT NULL	Maximum outreach attempts
touchpoint_window_days	INTEGER	NOT NULL	Window for touchpoint limit
quiet_hours_start	TIME	NOT NULL	Contact restriction start
quiet_hours_end	TIME	NOT NULL	Contact restriction end
high_value_threshold	BIGINT	NOT NULL	Human-approval threshold
effective_from	TIMESTAMPTZ	NOT NULL	Policy activation
effective_to	TIMESTAMPTZ	NULL	Policy expiration
created_at	TIMESTAMPTZ	NOT NULL	Creation timestamp
Constraints
max_auto_recovery_amount >= 0
max_concession_percent >= 0
max_concession_percent <= 100
max_concession_amount >= 0
max_touchpoints >= 0
touchpoint_window_days > 0
high_value_threshold >= 0
Unique constraint
UNIQUE (merchant_id, version)
Important principle

Historical policy records must never be overwritten in a way that destroys the ability to reconstruct previous decisions.

10. invoices
Purpose

Stores customer financial obligations.

Columns
Column	Type	Constraints	Description
id	UUID	PK	Internal invoice identifier
merchant_id	UUID	FK, NOT NULL	Merchant
customer_id	UUID	FK, NOT NULL	Customer
invoice_number	VARCHAR(100)	NOT NULL	Merchant invoice number
currency	CHAR(3)	NOT NULL	Invoice currency
total_amount	BIGINT	NOT NULL	Original invoice amount
amount_paid	BIGINT	NOT NULL DEFAULT 0	Verified paid amount
issue_date	DATE	NOT NULL	Issue date
due_date	DATE	NOT NULL	Due date
status	VARCHAR(32)	NOT NULL	Invoice status
external_reference	VARCHAR(255)	NULL	ERP/external reference
created_at	TIMESTAMPTZ	NOT NULL	Creation timestamp
updated_at	TIMESTAMPTZ	NOT NULL	Last update timestamp
Constraints
total_amount >= 0
amount_paid >= 0
amount_paid <= total_amount
Unique constraint
UNIQUE (merchant_id, invoice_number)
Indexes
INDEX invoices_merchant_id_idx
INDEX invoices_customer_id_idx
INDEX invoices_due_date_idx
INDEX invoices_status_idx
11. invoice_lines
Purpose

Stores invoice-level line items.

Columns
Column	Type	Constraints	Description
id	UUID	PK	Line identifier
invoice_id	UUID	FK, NOT NULL	Parent invoice
line_number	INTEGER	NOT NULL	Line sequence
description	TEXT	NOT NULL	Item/service description
product_code	VARCHAR(100)	NULL	Product/service code
quantity	NUMERIC(18,4)	NOT NULL	Quantity
unit_price	BIGINT	NOT NULL	Unit price in minor units
tax_amount	BIGINT	NOT NULL DEFAULT 0	Tax amount
line_total	BIGINT	NOT NULL	Line total
created_at	TIMESTAMPTZ	NOT NULL	Creation timestamp
Constraints
quantity >= 0
unit_price >= 0
tax_amount >= 0
line_total >= 0
Unique constraint
UNIQUE (invoice_id, line_number)
12. recovery_cases
Purpose

Represents the operational recovery workflow associated with an invoice.

Columns
Column	Type	Constraints	Description
id	UUID	PK	Recovery case identifier
merchant_id	UUID	FK, NOT NULL	Merchant
customer_id	UUID	FK, NOT NULL	Customer
invoice_id	UUID	FK, NOT NULL	Invoice
status	VARCHAR(40)	NOT NULL	Current state
issue_type	VARCHAR(64)	NULL	Primary issue
risk_level	VARCHAR(32)	NULL	Current risk
claimed_disputed_amount	BIGINT	NOT NULL DEFAULT 0	Customer-claimed dispute
verified_disputed_amount	BIGINT	NULL	Evidence-supported dispute
collectible_amount	BIGINT	NULL	Evidence-supported collectible amount
safely_recoverable_amount	BIGINT	NULL	Amount currently safe to recover
recovered_amount	BIGINT	NOT NULL DEFAULT 0	Verified recovered amount
remaining_amount	BIGINT	NOT NULL DEFAULT 0	Remaining balance
resolution_confidence	NUMERIC(5,4)	NULL	AI confidence for resolution
touchpoint_count	INTEGER	NOT NULL DEFAULT 0	Recorded automated contact count
locked	BOOLEAN	NOT NULL DEFAULT FALSE	Automation lock
lock_reason	VARCHAR(128)	NULL	Lock reason
created_at	TIMESTAMPTZ	NOT NULL	Creation timestamp
updated_at	TIMESTAMPTZ	NOT NULL	Last update timestamp
Foreign keys
merchant_id → merchants.id
customer_id → customers.id
invoice_id → invoices.id
Constraints
claimed_disputed_amount >= 0
verified_disputed_amount IS NULL OR verified_disputed_amount >= 0
collectible_amount IS NULL OR collectible_amount >= 0
safely_recoverable_amount IS NULL OR safely_recoverable_amount >= 0
recovered_amount >= 0
remaining_amount >= 0
touchpoint_count >= 0
Important integrity rule

The application must prevent:

recovered_amount > invoice.total_amount

and:

recovery_action.amount > verified collectible amount

The second rule is primarily enforced by application policy logic.

13. disputes
Purpose

Stores commercial invoice disputes.

Columns
Column	Type	Constraints	Description
id	UUID	PK	Dispute identifier
case_id	UUID	FK, NOT NULL	Recovery case
type	VARCHAR(64)	NOT NULL	Dispute type
customer_claim	TEXT	NOT NULL	Customer's claim
claimed_amount	BIGINT	NULL	Customer-claimed amount
verified_amount	BIGINT	NULL	Evidence-supported amount
status	VARCHAR(32)	NOT NULL	Dispute status
opened_at	TIMESTAMPTZ	NOT NULL	Open timestamp
resolved_at	TIMESTAMPTZ	NULL	Resolution timestamp
Foreign key
case_id → recovery_cases.id
Index
INDEX disputes_case_id_idx
14. evidence
Purpose

Stores business evidence used by the recovery process.

Columns
Column	Type	Constraints	Description
id	UUID	PK	Evidence identifier
case_id	UUID	FK, NOT NULL	Recovery case
type	VARCHAR(64)	NOT NULL	Evidence type
source	VARCHAR(128)	NOT NULL	Source system
external_reference	VARCHAR(255)	NULL	Source identifier
content	TEXT	NULL	Text representation
structured_data	JSONB	NULL	Normalized facts
created_at	TIMESTAMPTZ	NOT NULL	Record timestamp
Foreign key
case_id → recovery_cases.id
Indexes
INDEX evidence_case_id_idx
INDEX evidence_type_idx
15. agent_runs
Purpose

Stores metadata about AI reasoning executions.

Columns
Column	Type	Constraints	Description
id	UUID	PK	Agent run identifier
case_id	UUID	FK, NOT NULL	Recovery case
agent_type	VARCHAR(64)	NOT NULL	Triage/Evidence/Resolution
model_name	VARCHAR(128)	NOT NULL	Model used
prompt_version	VARCHAR(64)	NOT NULL	Prompt version
input_hash	VARCHAR(128)	NOT NULL	Input fingerprint
output_json	JSONB	NULL	Structured model output
latency_ms	INTEGER	NULL	Model latency
token_usage	JSONB	NULL	Provider token metadata
success	BOOLEAN	NOT NULL	Whether run succeeded
error	TEXT	NULL	Error details
created_at	TIMESTAMPTZ	NOT NULL	Execution time
Foreign key
case_id → recovery_cases.id
Important principle

The table stores model execution metadata and structured outputs.

It must not be used to store or expose private model chain-of-thought.

16. resolution_proposals
Purpose

Stores AI-generated recovery recommendations before execution.

Columns
Column	Type	Constraints	Description
id	UUID	PK	Proposal identifier
case_id	UUID	FK, NOT NULL	Recovery case
agent_run_id	UUID	FK, NOT NULL	Source agent execution
action_type	VARCHAR(64)	NOT NULL	Proposed action
proposed_amount	BIGINT	NULL	Proposed monetary amount
reason_code	VARCHAR(128)	NOT NULL	Structured reason
confidence	NUMERIC(5,4)	NOT NULL	AI confidence
evidence_ids	JSONB	NOT NULL	Evidence references
status	VARCHAR(32)	NOT NULL	Proposal status
created_at	TIMESTAMPTZ	NOT NULL	Creation timestamp
Constraints
proposed_amount IS NULL OR proposed_amount >= 0
confidence >= 0
confidence <= 1
Foreign keys
case_id → recovery_cases.id
agent_run_id → agent_runs.id
17. policy_decisions
Purpose

Stores the deterministic Policy Engine result.

Columns
Column	Type	Constraints	Description
id	UUID	PK	Decision identifier
case_id	UUID	FK, NOT NULL	Recovery case
proposal_id	UUID	FK, NOT NULL	Evaluated proposal
decision	VARCHAR(40)	NOT NULL	Policy result
policy_version	VARCHAR(64)	NOT NULL	Applied policy
checks_json	JSONB	NOT NULL	Individual checks
blocking_reason	VARCHAR(128)	NULL	Blocking reason
created_at	TIMESTAMPTZ	NOT NULL	Decision timestamp
Foreign keys
case_id → recovery_cases.id
proposal_id → resolution_proposals.id
## 18. recovery_actions

Purpose

Stores recovery actions proposed for controlled execution, including actions
that are awaiting human authorization and actions that have been authorized
or executed by the application.


Columns
Column	Type	Constraints	Description
id	UUID	PK	Action identifier
case_id	UUID	FK, NOT NULL	Recovery case
proposal_id	UUID	FK, NOT NULL	Source proposal
policy_decision_id	UUID	FK, NOT NULL	Policy decision
type	VARCHAR(64)	NOT NULL	Action type
amount	BIGINT	NULL	Action amount
status	VARCHAR(40)	NOT NULL	Action status
external_provider	VARCHAR(64)	NULL	Provider
external_reference	VARCHAR(255)	NULL	Provider reference
reason	TEXT	NULL	Action reason
created_at	TIMESTAMPTZ	NOT NULL	Creation timestamp
executed_at	TIMESTAMPTZ	NULL	Execution timestamp
Constraints
amount IS NULL OR amount >= 0
Important rule

Important rule

A Recovery Action may only be created after the applicable policy and state
checks have been evaluated.

If the Policy Engine returns HUMAN_APPROVAL_REQUIRED, the Recovery Action
must be created with a non-executable pending-approval status.

A Recovery Action must not be executed until all required authorization
conditions, including human approval where required, have been satisfied.

19. payments
Purpose

Represents actual payment state associated with a recovery action.

Columns
Column	Type	Constraints	Description
id	UUID	PK	Payment record
invoice_id	UUID	FK, NOT NULL	Invoice
case_id	UUID	FK, NOT NULL	Recovery case
recovery_action_id	UUID	FK, NOT NULL	Recovery action
razorpay_payment_id	VARCHAR(128)	NULL	Razorpay payment identifier
razorpay_payment_link_id	VARCHAR(128)	NULL	Razorpay Payment Link identifier
amount	BIGINT	NOT NULL	Payment amount
currency	CHAR(3)	NOT NULL	Currency
status	VARCHAR(32)	NOT NULL	Payment status
paid_at	TIMESTAMPTZ	NULL	Verified payment time
created_at	TIMESTAMPTZ	NOT NULL	Creation timestamp
updated_at	TIMESTAMPTZ	NOT NULL	Last update
Constraints
amount > 0
Important principle

Payment state represents actual provider-confirmed payment status.

A payment request being created does not imply successful payment.

Indexes
INDEX payments_case_id_idx
INDEX payments_invoice_id_idx
INDEX payments_razorpay_payment_id_idx
INDEX payments_razorpay_link_id_idx
20. outreach
Purpose

Stores customer-contact attempts used for touchpoint enforcement.

Columns
Column	Type	Constraints	Description
id	UUID	PK	Outreach identifier
case_id	UUID	FK, NOT NULL	Recovery case
channel	VARCHAR(32)	NOT NULL	Communication channel
direction	VARCHAR(16)	NOT NULL	Inbound/outbound
purpose	VARCHAR(64)	NOT NULL	Communication purpose
message_reference	VARCHAR(255)	NULL	External message reference
status	VARCHAR(32)	NOT NULL	Delivery/processing state
sent_at	TIMESTAMPTZ	NULL	Send time
Foreign key
case_id → recovery_cases.id
Index
INDEX outreach_case_id_sent_at_idx

This supports deterministic queries such as:

How many automated touchpoints occurred within the last 14 days?

21. human_approvals
Purpose

Stores explicit human authorization for restricted recovery actions.

Columns
Column	Type	Constraints	Description
id	UUID	PK	Approval identifier
case_id	UUID	FK, NOT NULL	Recovery case
action_id	UUID	FK, NOT NULL	Specific recovery action
requested_amount	BIGINT	NULL	Amount requested
decision	VARCHAR(32)	NOT NULL	Approval decision
Supported decisions:

PENDING
APPROVED
REJECTED
EXPIRED
INVALIDATED
An APPROVED record authorizes only the exact action represented by its
action_fingerprint. Any modification to the action amount, action type,
proposal, or material execution parameters invalidates the approval.
approved_by	VARCHAR(128)	NULL	Human approver
action_fingerprint VARCHAR(128) NOT NULL
reason	TEXT	NULL	Approval/rejection reason
created_at	TIMESTAMPTZ	NOT NULL	Request timestamp
resolved_at	TIMESTAMPTZ	NULL	Resolution timestamp
Foreign keys
case_id → recovery_cases.id
action_id → recovery_actions.id
Important principle

Approval is bound to the exact action.

Changing the action or amount invalidates the prior authorization.

22. audit_events
Purpose

Provides the append-oriented operational history of each recovery case.

Columns
Column	Type	Constraints	Description
id	UUID	PK	Audit event identifier
case_id	UUID	FK, NOT NULL	Recovery case
event_type	VARCHAR(64)	NOT NULL	Event type
actor_type	VARCHAR(64)	NOT NULL	Source/component
actor_id	VARCHAR(128)	NULL	Specific actor
state_before	VARCHAR(40)	NULL	Previous state
state_after	VARCHAR(40)	NULL	Next state
payload_json	JSONB	NULL	Structured event information
policy_version	VARCHAR(64)	NULL	Applied policy
external_event_id	VARCHAR(255)	NULL	External idempotency/event ID
created_at	TIMESTAMPTZ	NOT NULL	Event time
Foreign key
case_id → recovery_cases.id
Indexes
INDEX audit_events_case_id_created_at_idx
INDEX audit_events_external_event_id_idx
Idempotency

Where an external event identifier exists, duplicate processing must be prevented by application/database constraints.

23. Table Relationships

The central relationship graph is:

merchants
   │
   ├── customers
   │      │
   │      └── invoices
   │             │
   │             ├── invoice_lines
   │             │
   │             └── recovery_cases
   │                    │
   │                    ├── disputes
   │                    ├── evidence
   │                    ├── agent_runs
   │                    │       │
   │                    │       └── resolution_proposals
   │                    │
   │                    ├── policy_decisions
   │                    ├── recovery_actions
   │                    │       │
   │                    │       ├── payments
   │                    │       └── human_approvals
   │                    │
   │                    ├── outreach
   │                    └── audit_events
   │
   └── merchant_policies
24. Recommended Foreign-Key Behavior

For core financial entities, deletion should normally be restricted.

Examples:

Merchant → Customer
Merchant → Invoice
Customer → Invoice
Invoice → RecoveryCase
Invoice → InvoiceLine
RecoveryCase → Payment
RecoveryCase → AuditEvent

Historical financial/audit data should not disappear because a parent record was deleted.

Soft deletion or archival may be introduced later if needed.

25. Uniqueness Requirements

Recommended uniqueness constraints:

merchant + invoice_number
merchant + policy_version
invoice + line_number

Razorpay/external references should be unique where the provider semantics guarantee uniqueness.

26. Recovery-Case Integrity

The application must ensure:

recovered_amount <= invoice.total_amount

and:

verified_disputed_amount <= invoice.total_amount

and:

collectible_amount <= invoice.total_amount - verified_disputed_amount

where those values are established.

For an executable recovery action:

recovery_action.amount <= verified_collectible_amount

and:

recovery_action.amount <= merchant_auto_recovery_limit

unless a valid human approval exists for the exact action.

A PolicyDecision of HUMAN_APPROVAL_REQUIRED is not sufficient authorization
for execution. Required human approval must also exist before the action can
be executed.

recovery_action.amount <=
verified_collectible_amount

and:

recovery_action.amount <=
merchant_auto_recovery_limit

unless a valid human approval exists.
## Golden Scenario Authorization Example

For the canonical MVP scenario:

Invoice total:
₹10,00,000

Verified disputed amount:
₹1,00,000

Collectible amount:
₹9,00,000

Default autonomous recovery authority:
₹5,00,000

The resulting ResolutionProposal may propose:

CREATE_PARTIAL_RECOVERY
₹9,00,000

The PolicyDecision must be:

HUMAN_APPROVAL_REQUIRED

The RecoveryAction may be created with:

status = PENDING_APPROVAL
amount = ₹9,00,000

No provider execution is permitted at this stage.

After valid human approval:

RecoveryAction.status = AUTHORIZED

Only then may the Razorpay provider adapter execute the recovery action.

27. Partial Recovery Accounting

For a simplified MVP case:

invoice_total
=
recovered_amount
+
disputed_outstanding
+
collectible_outstanding

Example:

Invoice:
₹10,00,000

Recovered:
₹9,00,000

Disputed outstanding:
₹1,00,000

Collectible outstanding:
₹0

The application must maintain this financial consistency deterministically.

28. Policy Version Integrity

Every material Policy Decision must record:

policy_version

The system must not reconstruct historical decisions using the merchant's latest policy if the applicable historical policy version is available.

29. AI Traceability

Every financial proposal generated by an AI component must be traceable to:

RecoveryCase
    ↓
AgentRun
    ↓
ResolutionProposal
    ↓
Evidence references
    ↓
PolicyDecision
    ↓
RecoveryAction

This enables complete reconstruction of how an automated decision was produced and authorized.

30. Webhook Idempotency

Razorpay webhook events may be delivered more than once.

The database/application must preserve an external event identifier where available.

Processing logic:

Webhook event
      ↓
Check external_event_id
      ↓
Already processed?
   ├── YES → ignore duplicate
   └── NO  → process and record

Duplicate external events must not create:

duplicate payments,
duplicate recovery actions,
duplicate state transitions, or
duplicate recovery amounts.
31. Recommended Index Strategy

Initial important indexes:

invoices(status)
invoices(due_date)
invoices(merchant_id)
invoices(customer_id)

recovery_cases(status)
recovery_cases(merchant_id, status)
recovery_cases(invoice_id)

evidence(case_id)
agent_runs(case_id)

resolution_proposals(case_id)
policy_decisions(case_id)

recovery_actions(case_id)
payments(case_id)
payments(razorpay_payment_id)

outreach(case_id, sent_at)

audit_events(case_id, created_at)

Indexes should be added based on actual query patterns rather than indiscriminately.

32. JSONB Usage

JSONB may be used for data that is naturally semi-structured, including:

evidence facts,
AI structured output,
policy check results,
token/provider metadata,
audit event payloads.

JSONB must not replace normal relational columns for frequently queried core financial fields such as:

invoice amount,
payment amount,
recovery status,
case status.
33. Transaction Boundaries

The following operations should be handled transactionally where practical:

Recovery approval
Policy decision
+
state transition
+
recovery action creation
Payment confirmation
Payment update
+
case state transition
+
invoice balance update
+
audit event
Human approval
Approval record
+
associated case/action state update
+
audit event

This prevents partially applied financial state.

34. Database Access Boundary

AI components should not receive unrestricted database credentials.

The preferred architecture is:

AI component
    ↓
Application service
    ↓
Repository/data access layer
    ↓
PostgreSQL

The application decides exactly what contextual data the model receives.

35. Schema Summary

The MVP database consists of:

merchants
customers
merchant_policies

invoices
invoice_lines

recovery_cases
disputes
evidence

agent_runs
resolution_proposals

policy_decisions
recovery_actions

payments
outreach
human_approvals

audit_events

This schema is designed to support the complete Track 03 workflow:

Revenue at Risk
      ↓
Diagnosis
      ↓
Evidence
      ↓
Resolution
      ↓
Policy
      ↓
Recovery
      ↓
Payment Confirmation
      ↓
Audit / Escalation

36. Implementation Principle

Database design must preserve the distinction between:

Customer claim
        ↓
Verified evidence
        ↓
Collectible assessment
        ↓
AI recommendation
        ↓
Policy authorization
        ↓
Recovery action
        ↓
Actual payment

No single database field should collapse these different concepts into one source of truth.