# MVP Implementation Plan

## 1. Project

**Receivables Resolution Agent**

Razorpay Buildathon:

**Track 03 — AI Revenue Recovery**

---

# 2. MVP Objective

Build a working end-to-end B2B receivables recovery system that can:

```text
Detect
  ↓
Diagnose
  ↓
Analyze Evidence
  ↓
Determine Collectible Amount
  ↓
Recommend Resolution
  ↓
Validate Policy
  ↓
Execute Bounded Recovery
  ↓
Verify Payment
  ↓
Update Recovery State
  ↓
Audit / Escalate

The MVP must prioritize correctness and safety over feature count.

3. Primary Golden Scenario

The primary end-to-end scenario is:

B2B Invoice
₹10,00,000

Customer disputes:
₹1,00,000

Evidence supports:
₹1,00,000 dispute

Collectible:
₹9,00,000

Workflow:

OVERDUE
    ↓
TRIAGING
    ↓
QUANTITY_DISPUTE
    ↓
EVIDENCE_ANALYSIS
    ↓
VERIFIED FINANCIAL ASSESSMENT
    ↓
CREATE_PARTIAL_RECOVERY
    ↓
POLICY CHECK
    ↓
HUMAN_APPROVAL_REQUIRED
    ↓
FINANCE APPROVAL
    ↓
RECOVERY AUTHORIZED
    ↓
RAZORPAY PAYMENT LINK
    ↓
CUSTOMER TEST PAYMENT
    ↓
VERIFIED WEBHOOK
    ↓
PARTIALLY_RECOVERED

The complete audit trace must be visible.Because the default automated recovery authority is ₹5,00,000, the ₹9,00,000 recovery requires human approval before execution. The ₹9,00,000 amount remains fully collectible; only the execution authority is restricted.

4. MVP Workstreams

Implementation is divided into the following workstreams.

M01 Project Foundation
M02 Database
M03 Domain Model
M04 State Machine
M05 Financial Calculation
M06 Policy Engine
M07 AI Contracts
M08 Evidence Pipeline
M09 Recovery Orchestrator
M10 Razorpay Integration
M11 Webhooks
M12 Audit System
M13 Human Approval / Escalation
M14 Backend API
M15 Frontend
M16 Evaluation
M17 Security / Hardening
M18 Demo
5. M01 — Project Foundation
Required

Set up:

Python project,
package structure,
dependency management,
environment configuration,
linting,
formatting,
type checking,
test framework,
Docker configuration,
local PostgreSQL,
basic application startup.
Acceptance
[ ] Backend starts locally
[ ] PostgreSQL starts locally
[ ] Health endpoint works
[ ] pytest runs
[ ] linting runs
[ ] formatting runs
[ ] type checking runs
[ ] environment configuration loads
6. M02 — Database

Implement:

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
Required
SQLAlchemy models,
Alembic migrations,
foreign keys,
indexes,
constraints,
exact monetary representation.
Acceptance
[ ] Fresh database can be created from migrations
[ ] All required relationships exist
[ ] Monetary values use exact representation
[ ] Core integrity constraints exist
[ ] Seed data can be loaded
7. M03 — Domain Model

Implement domain/application services for:

invoice management,
recovery cases,
disputes,
evidence,
payments,
recovery actions.

Financial and recovery rules must not be scattered through API routes.

8. M04 — State Machine

Implement the deterministic Recovery Case State Machine.

Required states:

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

Implement explicit domain events and transition guards.

Acceptance
[ ] Valid transitions work
[ ] Invalid transitions fail
[ ] Legal locks prevent recovery
[ ] Payment confirmation requires verified event
[ ] State transitions are auditable
[ ] State machine does not calculate financial values
9. M05 — Financial Calculation

Implement deterministic financial calculations.

Required concepts:

claimed disputed amount
verified disputed amount
collectible amount
safely recoverable amount
recovered amount
remaining amount
Rules
use exact minor units,
no floating-point authoritative arithmetic,
reject invalid negative amounts,
prevent over-recovery,
preserve financial consistency.
Acceptance
[ ] Unit tests cover all calculations
[ ] Boundary values are tested
[ ] No floating-point monetary calculations
[ ] Reconciliation invariants pass
10. M06 — Policy Engine

Implement a deterministic Policy Engine.

Required checks:

evidence sufficiency
evidence conflict
collectible amount
financial authority
concession limits
touchpoint limits
quiet hours
legal lock
human approval
state validity

Required decisions:

APPROVED
DEFERRED
HUMAN_APPROVAL_REQUIRED
BLOCKED
STOPPED
Default demo policy
Maximum automated recovery:
₹5,00,000

Maximum concession:
min(
    5% of invoice amount,
    ₹25,000
)

Maximum automated touchpoints:
3 within 14 days

These are prototype merchant-policy defaults, not claims about universal Razorpay policy.

Acceptance
[ ] Policy evaluation is deterministic
[ ] One-rupee boundary tests pass
[ ] Legal lock passes
[ ] Touchpoint limit passes
[ ] Concession cap passes
[ ] Human approval threshold passes
[ ] Policy failure fails closed
11. M07 — AI Contracts

Implement typed adapters for:

TriageAgent
EvidenceAgent
ResolutionAgent

Each must:

receive typed input,
return typed output,
validate output schema,
record AgentRun metadata,
reject malformed output.

AI must not directly access Razorpay or mutate financial state.

12. M08 — Evidence Pipeline

Implement:

Evidence ingestion
       ↓
Evidence normalization
       ↓
Evidence retrieval
       ↓
Evidence Agent
       ↓
Evidence Assessment

Support initial evidence types:

INVOICE
PURCHASE_ORDER
GRN
DELIVERY_RECORD
CONTRACT
MILESTONE_RECORD
CUSTOMER_EMAIL
PAYMENT_RECORD
CREDIT_NOTE

The MVP may use structured synthetic records and small text documents.

No vector database is required unless a demonstrated retrieval requirement emerges.

13. M09 — Recovery Orchestrator

Implement the controlled workflow:

Case
 ↓
Triage
 ↓
Evidence
 ↓
Financial Calculation
 ↓
Resolution
 ↓
Policy
 ↓
State Machine
 ↓
Execution

The orchestrator must not replace:

Policy Engine,
State Machine,
Financial Calculation Service,
Razorpay adapter.

It coordinates them.

14. M10 — Razorpay Integration

Implement a dedicated:

RazorpayProvider

behind an application-level payment-provider interface.

MVP capability:

Create Payment Link
Fetch Payment Link where required
Provider event handling

The application should attach its own:

reference_id
notes / metadata

to connect:

Invoice
→ Recovery Case
→ Recovery Action
→ Razorpay Payment Link

The implementation must follow the current Razorpay API contract documented in the engineering specifications.

15. M11 — Webhooks

Implement:

POST /v1/webhooks/razorpay

Required:

raw-body signature verification
event validation
x-razorpay-event-id handling
idempotency
provider-to-internal mapping
payment reconciliation
state transition
audit event

Support the Payment Link events required by the MVP, including:

payment_link.paid
payment_link.partially_paid
payment_link.cancelled
payment_link.expired

No webhook may directly assign arbitrary Recovery Case state.

16. M12 — Audit System

Implement append-oriented audit events.

The audit system must reconstruct:

Evidence
 ↓
AI Result
 ↓
Financial Assessment
 ↓
Resolution
 ↓
Policy
 ↓
Recovery
 ↓
Payment
 ↓
Outcome

Required views:

case timeline
policy decision
recovery action
payment event
safety event
human approval

Do not store private LLM chain-of-thought.

17. M13 — Human Approval and Escalation

Implement:

HUMAN_REVIEW
LEGAL_ESCALATION
HUMAN_APPROVAL_REQUIRED
EVIDENCE_REVIEW

Human approvals must be bound to:

case
proposal
action
amount
approver

Modified proposals require new approval.

18. M14 — Backend API

Implement the API contract defined in:

docs/02-engineering/api-contracts.md

Core endpoints:

POST /v1/invoices

POST /v1/recovery-cases
GET  /v1/recovery-cases
GET  /v1/recovery-cases/{id}

POST /v1/recovery-cases/{id}/triage
POST /v1/recovery-cases/{id}/evidence
POST /v1/recovery-cases/{id}/resolve
POST /v1/recovery-cases/{id}/policy-check
POST /v1/recovery-cases/{id}/execute

POST /v1/recovery-cases/{id}/approvals
POST /v1/recovery-cases/{id}/escalate

GET /v1/recovery-cases/{id}/audit

GET /v1/dashboard/summary

POST /v1/evaluations
GET /v1/evaluations/{id}

POST /v1/webhooks/razorpay

Every mutation must enforce authorization, policy, and state rules.

19. M15 — Frontend

Implement four primary views.

Dashboard

Show:

revenue at risk,
safely recoverable amount,
recovered amount,
cases needing attention,
case list.
Case Detail

Show:

invoice,
customer,
issue,
disputed amount,
collectible amount,
evidence,
AI proposal,
policy result,
recovery state.
Audit Trace

Show the complete chronological decision/event history.

Benchmark

Show:

cases,
revenue at risk,
safely recoverable amount,
recovered amount,
recovery rate,
accuracy,
safety violations,
escalations,
audit completeness.
20. M16 — Evaluation

Implement:

MockPaymentProvider
Benchmark Runner
Metric Calculation
Per-Case Evaluation
Aggregate Reporting

The benchmark must support:

50-case minimum
100-case target

and the scenario distribution defined in:

docs/03-evaluation/scenario-matrix.md
21. M17 — Security and Hardening

Implement and test:

authentication
authorization
merchant isolation
input validation
secret handling
prompt injection defense
AI output validation
financial validation
state validation
webhook verification
webhook idempotency
approval binding
stale proposal protection
audit protection
22. M18 — Demo

The final demo must show:

Golden path
₹10L invoice
   ↓
₹1L verified dispute
   ↓
₹9L collectible
   ↓
policy
   ↓
Razorpay Payment Link
   ↓
test payment
   ↓
verified webhook
   ↓
partial recovery
Safety path
legal risk / conflicting evidence
   ↓
automation stops
   ↓
human/legal escalation
Batch path
50–100 cases
   ↓
financial metrics
   ↓
accuracy metrics
   ↓
safety metrics
   ↓
audit metrics
23. Implementation Order

Implementation must follow this order unless an explicit dependency requires otherwise:

1. Foundation
2. Database
3. Domain model
4. State machine
5. Financial calculation
6. Policy Engine
7. AI contracts
8. Evidence pipeline
9. Orchestrator
10. Razorpay adapter
11. Webhooks
12. Audit
13. Human approval/escalation
14. API
15. Frontend
16. Evaluation
17. Security hardening
18. Demo
24. Definition of Done

The MVP is not complete when the application merely starts.

It is complete when:

[ ] Golden recovery works end-to-end
[ ] Partial recovery works
[ ] Legal stop works
[ ] Conflicting evidence works
[ ] Human approval works
[ ] Razorpay Test Mode payment works
[ ] Webhook verification works
[ ] Webhook idempotency works
[ ] Policy tests pass
[ ] State-machine tests pass
[ ] Financial tests pass
[ ] AI schema tests pass
[ ] Security tests pass
[ ] Benchmark runs
[ ] 50+ benchmark cases execute
[ ] Per-case results are generated
[ ] Aggregate metrics are generated
[ ] Audit traces are complete
[ ] No secrets are committed
[ ] README/setup works from a clean environment
25. Explicit Non-Goals

Do not implement these as part of MVP unless an explicit decision changes the scope:

production IVR
production WhatsApp/SMS infrastructure
full ERP integration
Kubernetes
Kafka
microservices
separate vector database
autonomous legal reasoning
autonomous policy creation
general-purpose accounting
general-purpose customer support
production payment credentials
26. Implementation Rule

When a feature is not required by this MVP document or its referenced specifications:

Do not implement it merely because it sounds impressive.

Prefer completing the core recovery loop and its tests over adding additional AI capabilities.

27. MVP Success Standard

The MVP must demonstrate:

Understand the blocker
        ↓
Verify the evidence
        ↓
Calculate the collectible amount
        ↓
Recommend the right intervention
        ↓
Apply deterministic policy
        ↓
Execute only when authorized
        ↓
Verify actual payment
        ↓
Recover or escalate
        ↓
Record the complete audit trail

The system should optimize for:

Safe, measurable, evidence-supported recovery.