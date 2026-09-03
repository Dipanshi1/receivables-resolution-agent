# System Architecture

## 1. Purpose

This document defines the high-level architecture of the Receivables Resolution Agent.

The architecture is designed for Razorpay Buildathon Track 03 — AI Revenue Recovery.

The system must demonstrate:

- revenue at risk detection,
- semantic issue understanding,
- evidence-grounded resolution,
- deterministic financial assessment,
- bounded autonomous recovery,
- human approval when required,
- Razorpay payment execution,
- verified payment confirmation,
- safe escalation,
- complete auditability,
- reproducible evaluation.

The architecture maintains strict separation between:

- AI reasoning,
- evidence processing,
- financial calculation,
- policy enforcement,
- human authorization,
- state management,
- payment execution,
- external payment verification,
- auditability.

The central architectural principle is:

> **The LLM can interpret and recommend; deterministic systems calculate, authorize, transition, execute, and verify.**

---

# 2. Architectural Goals

The system must provide:

1. measurable revenue recovery,
2. evidence-grounded AI reasoning,
3. deterministic financial controls,
4. bounded autonomous execution,
5. safe human escalation,
6. reliable Razorpay integration,
7. webhook-driven payment verification,
8. complete auditability,
9. reproducible evaluation,
10. straightforward local development.

---

# 3. Architecture Style

## 3.1 Modular Monolith

The MVP uses a modular-monolith architecture.

The primary deployable components are:

```text
Frontend
   +
Backend
   +
PostgreSQL

The backend is internally divided into explicit logical modules.

Backend
│
├── API
├── Recovery
├── AI
├── Evidence
├── Financial
├── Policy
├── State
├── Approval
├── Razorpay
├── Webhook
├── Audit
└── Evaluation

Modules communicate through explicit application/service interfaces.

They must not bypass domain boundaries through uncontrolled direct access.

4. High-Level Architecture
                         ┌──────────────────────┐
                         │     Finance User     │
                         │      Dashboard       │
                         └──────────┬───────────┘
                                    │
                              HTTPS / JSON
                                    │
                                    ▼
                         ┌──────────────────────┐
                         │    Next.js Frontend  │
                         └──────────┬───────────┘
                                    │
                                    ▼
                         ┌──────────────────────┐
                         │    FastAPI Backend   │
                         │       API Layer      │
                         └──────────┬───────────┘
                                    │
                                    ▼
                         ┌──────────────────────┐
                         │ Recovery Orchestrator│
                         └──────────┬───────────┘
                                    │
              ┌─────────────────────┼─────────────────────┐
              │                     │                     │
              ▼                     ▼                     ▼
       ┌─────────────┐       ┌─────────────┐      ┌─────────────┐
       │   AI Layer  │       │  Financial  │      │Policy Layer │
       │             │       │ Calculation │      │             │
       │ Triage      │       │   Service   │      │ Policy      │
       │ Evidence    │       └──────┬──────┘      │ Approval    │
       │ Resolution  │              │             │ Safety      │
       └──────┬──────┘              │             └──────┬──────┘
              │                     │                    │
              └─────────────────────┼────────────────────┘
                                    │
                                    ▼
                         ┌──────────────────────┐
                         │    State Machine     │
                         └──────────┬───────────┘
                                    │
                                    ▼
                         ┌──────────────────────┐
                         │   Human Approval     │
                         │    when required     │
                         └──────────┬───────────┘
                                    │
                                    ▼
                         ┌──────────────────────┐
                         │   Recovery Executor  │
                         └──────────┬───────────┘
                                    │
                                    ▼
                         ┌──────────────────────┐
                         │    Razorpay APIs     │
                         │ Payment Requests     │
                         └──────────┬───────────┘
                                    │
                                    │ customer payment
                                    ▼
                         ┌──────────────────────┐
                         │  Razorpay Webhooks   │
                         └──────────┬───────────┘
                                    │
                                    ▼
                         ┌──────────────────────┐
                         │ Webhook Verification │
                         │ + Event Processing   │
                         └──────────┬───────────┘
                                    │
                                    ▼
                         ┌──────────────────────┐
                         │ Payment Reconciliation│
                         │ + Domain Event       │
                         └──────────┬───────────┘
                                    │
                          ┌─────────┴─────────┐
                          ▼                   ▼
                   ┌─────────────┐     ┌─────────────┐
                   │ PostgreSQL  │     │ Audit Layer │
                   │             │     │             │
                   │ Domain Data │     │ Audit Events│
                   │ Financial   │     │ Decisions   │
                   │ State       │     │ History     │
                   └─────────────┘     └─────────────┘
5. Core Architectural Layers

The system is organized into the following layers:

Presentation
      ↓
API
      ↓
Application / Orchestration
      ↓
Domain Services
      ↓
Persistence / External Adapters

The major domain control path is:

AI Recommendation
      ↓
Financial Validation
      ↓
Policy Authorization
      ↓
Human Approval if required
      ↓
State Validation
      ↓
Recovery Execution
      ↓
External Payment
      ↓
Webhook Verification
      ↓
Financial Reconciliation
      ↓
Audit
6. Frontend Layer
Technology
Next.js
TypeScript
Responsibilities

The frontend presents:

revenue at risk,
collectible amount,
safely recoverable amount,
recovered amount,
outstanding balance,
recovery cases,
case details,
evidence,
AI recommendations,
policy decisions,
approval requests,
payment status,
escalation status,
audit traces,
benchmark results.

The frontend is a presentation and interaction layer.

It does not contain authoritative financial or policy logic.

6.1 Frontend Restrictions

The frontend must not directly access:

LLM providers,
PostgreSQL,
Razorpay credentials,
internal policy services,
internal state services,
financial calculation services.

All operations go through the backend API.

Frontend
   ↓
Authenticated API
   ↓
Backend Application Services
7. API Layer
Technology
FastAPI

The API layer provides:

authentication/context handling,
recovery-case APIs,
invoice APIs,
evidence APIs,
resolution APIs,
policy-check APIs,
human approval APIs,
execution APIs,
escalation APIs,
audit APIs,
dashboard APIs,
evaluation APIs,
Razorpay webhook endpoint.

The API layer should remain thin.

It should:

validate request structure,
establish authenticated merchant context,
enforce API-level authorization,
delegate to application services,
serialize the response.

Business rules should not primarily live inside HTTP route handlers.

8. Recovery Orchestrator

The Recovery Orchestrator coordinates the recovery workflow.

Its responsibilities include:

loading the current Recovery Case,
determining the next workflow step,
invoking the appropriate AI component,
validating AI output,
invoking evidence processing,
invoking deterministic financial calculation,
generating a Resolution Proposal,
submitting the proposal to the Policy Engine,
requesting human approval when required,
invoking the State Machine,
invoking the Recovery Executor,
recording audit events.

The orchestrator coordinates components.

It does not replace their authority.

In particular:

Orchestrator
    ≠
Policy Engine
Orchestrator
    ≠
State Machine
Orchestrator
    ≠
Financial Calculation Service
9. AI Layer

The AI layer contains three reasoning components:

AI Layer
│
├── Triage Agent
├── Evidence Agent
└── Resolution Agent
Triage Agent

Determines the likely reason for non-payment.

Input
  ↓
Customer / Invoice / Case Context
  ↓
Triage Agent
  ↓
Issue Classification
Evidence Agent

Interprets business evidence and extracts structured candidate facts.

Evidence
  ↓
Evidence Agent
  ↓
Claims / Facts / Conflicts / Missing Evidence
Resolution Agent

Produces a structured recommendation.

Verified Case Context
  ↓
Resolution Agent
  ↓
Resolution Proposal

The AI layer stops at recommendation.

10. AI Trust Boundary

AI output is treated as untrusted application input.

                LLM
                 │
                 ▼
          Structured Output
                 │
                 ▼
          Schema Validation
                 │
                 ▼
        Semantic Validation
                 │
                 ▼
      Financial Validation
                 │
                 ▼
        Policy Validation
                 │
                 ▼
        State Validation
                 │
                 ▼
        Potential Execution

The LLM cannot directly:

execute Razorpay,
create payment requests,
authorize recovery,
modify financial balances,
mark payments successful,
modify policy,
override legal locks,
transition case state.
11. Evidence Layer

The Evidence layer provides the information required to resolve a Recovery Case.

Initial evidence types include:

Invoice,
Invoice Line Items,
Purchase Order,
GRN / Delivery Record,
Contract,
Milestone Record,
Customer Communication,
Payment History,
Credit Note.

The Evidence layer is responsible for:

retrieving relevant evidence,
normalizing structured facts,
preserving source references,
identifying missing evidence,
identifying conflicting evidence,
providing evidence context to AI components.

Evidence provenance must be preserved.

Material claims should be traceable to their supporting evidence.

12. Financial Calculation Service

The Financial Calculation Service is the authoritative source for financial assessment.

It is deterministic and independent of the LLM.

It calculates:

current outstanding,
verified disputed amount,
collectible amount,
safely recoverable amount,
recovered amount,
remaining balance.

Conceptually:

Evidence / Verified Facts
          ↓
Financial Calculation Service
          ↓
Verified Financial Assessment

The AI may extract financial facts.

The AI does not establish authoritative financial state.

13. Financial Authority vs Execution Authority

A critical architectural distinction is:

Collectible
    ≠
Authorized for Autonomous Execution

Example:

Invoice                  ₹10,00,000
Verified dispute          ₹1,00,000
Collectible                ₹9,00,000
Autonomous authority       ₹5,00,000

The financial system may determine:

Collectible = ₹9,00,000

But the Policy Engine determines:

₹9,00,000 > ₹5,00,000

Therefore:

HUMAN_APPROVAL_REQUIRED

The existence of collectible cash does not automatically authorize the system to recover it autonomously.

14. Policy Layer

The Policy Engine enforces deterministic merchant and system controls.

It evaluates:

financial authority,
concession limits,
evidence sufficiency,
legal/safety restrictions,
outreach limits,
quiet hours,
human approval requirements,
current state,
execution eligibility.

Possible policy outcomes include:

APPROVED
DEFERRED
HUMAN_APPROVAL_REQUIRED
BLOCKED
STOPPED

These are policy decisions.

They are not Recovery Case states.

Policy decisions must be versioned and auditable.

15. Human Approval Layer

Human approval is a controlled authorization boundary.

The system requests human approval when, for example:

the proposed recovery exceeds autonomous authority,
a concession exceeds the automatic limit,
evidence is insufficient,
evidence conflicts,
a policy exception is requested,
high-value recovery requires approval,
an operational exception requires review.

Approval must bind to the exact Recovery Action.

Conceptually:

Resolution Proposal
       ↓
Policy Engine
       ↓
HUMAN_APPROVAL_REQUIRED
       ↓
Human Review
       ↓
Exact Recovery Action Approval
       ↓
RECOVERY_AUTHORIZED

A material change to:

amount,
proposal,
action,
case,
financial assessment,

invalidates the previous approval and requires re-evaluation.

16. State Machine

The State Machine is the authoritative controller of Recovery Case state.

Core states:

OVERDUE
TRIAGING
ISSUE_IDENTIFIED
EVIDENCE_ANALYSIS
RESOLUTION_READY
POLICY_REVIEW
HUMAN_REVIEW
RECOVERY_INITIATED
PAYMENT_PENDING
PARTIALLY_RECOVERED
FULLY_RECOVERED
LEGAL_ESCALATION
AUTOMATION_LOCKED
EXECUTION_FAILED
CLOSED

The State Machine validates:

current state,
allowed transitions,
transition preconditions,
execution eligibility.

The LLM cannot directly transition state.

17. Domain Events vs States

Payment confirmation is a domain event.

It is not a persistent Recovery Case state.

Conceptually:

PAYMENT_PENDING
      ↓
Verified PAYMENT_CONFIRMED event
      ↓
Financial Reconciliation
      ↓
State Machine
      ↓
PARTIALLY_RECOVERED
or
FULLY_RECOVERED

Similarly, policy outcomes such as:

HUMAN_APPROVAL_REQUIRED

are not themselves Recovery Case states.

They are decisions/events that drive the workflow.

18. Recovery Executor

The Recovery Executor is the only application component responsible for invoking an external payment operation.

It receives an already validated Recovery Action.

Before execution it must verify:

Current case state is valid
        +
Current financial assessment is valid
        +
Recovery amount is valid
        +
Policy authorization is current
        +
Human approval is valid if required
        +
No legal/safety lock exists
        +
Action has not already executed

Only then may it invoke the payment provider.

The executor must not accept an arbitrary amount directly from:

the frontend,
the LLM,
customer input,
stale proposals.
19. Razorpay Integration Layer

All Razorpay-specific implementation is isolated behind a provider adapter.

Conceptually:

Recovery Executor
       ↓
PaymentProvider Interface
       ↓
RazorpayProvider
       ↓
Razorpay APIs

The rest of the application should not depend directly on Razorpay SDK implementation details.

This provides:

easier testing,
provider abstraction,
simpler mocking,
clearer business/provider separation,
easier future provider changes.
20. Razorpay Responsibilities

Razorpay is responsible for external payment-provider operations.

The application is responsible for:

determining what amount may be recovered,
determining why it may be recovered,
enforcing policy,
authorizing execution,
tracking Recovery Actions,
reconciling verified payments,
updating business state.

Razorpay is therefore not the source of truth for:

dispute classification,
collectible calculation,
merchant policy,
case state.
21. Payment Flow

Canonical payment flow:

Verified Financial Assessment
          ↓
Resolution Proposal
          ↓
Policy Engine
          ↓
Approval if Required
          ↓
State Machine
          ↓
Recovery Executor
          ↓
Razorpay Payment Link
          ↓
PAYMENT_PENDING
          ↓
Customer Payment
          ↓
Razorpay Webhook
          ↓
Webhook Verification
          ↓
Verified Payment Record
          ↓
PAYMENT_CONFIRMED Domain Event
          ↓
Financial Reconciliation
          ↓
State Machine
          ↓
PARTIALLY_RECOVERED / FULLY_RECOVERED

Creating a Payment Link does not mean money has been recovered.

Only a verified external payment event can establish recovery.

22. Webhook Trust Boundary

The Razorpay webhook endpoint is a security and financial trust boundary.

Processing sequence:

Incoming Webhook
       ↓
Read Raw Body
       ↓
Verify Signature
       ↓
Read Event ID
       ↓
Deduplication
       ↓
Payload Validation
       ↓
Resolve Internal Payment / Action
       ↓
Financial Reconciliation
       ↓
Persist Verified Payment
       ↓
Emit PAYMENT_CONFIRMED if applicable
       ↓
State Machine
       ↓
Audit

Invalid or unauthenticated events must not mutate financial state.

Duplicate events must not create duplicate financial effects.

23. PostgreSQL Layer

PostgreSQL stores persistent domain state.

Core entities include:

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
WebhookEvent

Financial state changes should be handled transactionally where appropriate.

The database must enforce important invariants through:

constraints,
unique indexes,
transactions,
row-level locking where required.
24. Audit Layer

The Audit layer records material business and system events.

The audit trail should make a Recovery Case explainable end-to-end.

Example:

INVOICE_OVERDUE
      ↓
TRIAGE_COMPLETED
      ↓
EVIDENCE_RETRIEVED
      ↓
DISPUTE_ASSESSED
      ↓
COLLECTIBLE_AMOUNT_CALCULATED
      ↓
RESOLUTION_PROPOSED
      ↓
POLICY_CHECKED
      ↓
HUMAN_APPROVAL_REQUIRED
      ↓
HUMAN_APPROVAL_GRANTED
      ↓
RECOVERY_AUTHORIZED
      ↓
PAYMENT_LINK_CREATED
      ↓
PAYMENT_CONFIRMED
      ↓
PARTIAL_RECOVERY_COMPLETED

Each material event should capture:

case identifier,
timestamp,
actor/component,
event type,
state before,
state after where applicable,
relevant structured payload,
policy version where applicable,
external provider references where applicable.

The audit layer must not become a mutable substitute for domain state.

25. Human Review Package

When human intervention is required, the system should present a structured case package containing:

Case
Invoice
Customer
Issue
Evidence
Evidence conflicts
Financial assessment
AI recommendation
Policy decision
Requested action
Requested amount
Reason for approval
Risk flags
Audit history

The human should not need to reconstruct the case manually from raw logs.

26. Evaluation Layer

The evaluation layer runs synthetic recovery cases independently from the production dashboard.

Conceptually:

Synthetic Dataset
       ↓
Case Runner
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
Recovery Simulation
       ↓
Metrics
       ↓
Evaluation Report

Ground truth must remain isolated from inference.

The system must never provide ground-truth answers directly to the AI during evaluation.

27. System Trust Zones

The architecture contains three major trust zones.

Zone 1 — Untrusted Inputs
Customer email
Documents
External text
Merchant notes
LLM output

These may contain:

incorrect information,
incomplete information,
malicious instructions,
prompt injection.
Zone 2 — Controlled Application Logic
Evidence Validation
Financial Calculation
Policy Engine
Human Approval
State Machine
Recovery Executor

These components enforce deterministic controls.

Zone 3 — External Financial Provider
Razorpay

The application communicates with Razorpay through the controlled adapter.

Payment confirmation returns through the verified webhook boundary.

28. Security Boundaries

The most sensitive application transition is:

AI Recommendation
       ↓
Financial Execution

This transition is protected by:

Schema Validation
       +
Semantic Validation
       +
Financial Validation
       +
Evidence Validation
       +
Policy Validation
       +
Human Approval if Required
       +
State Validation
       +
Execution Idempotency
       ↓
Recovery Executor

Only after these controls pass can the executor communicate with Razorpay.

29. Golden Scenario

Canonical scenario:

Invoice:
₹10,00,000

Verified dispute:
₹1,00,000

Collectible:
₹9,00,000

Autonomous authority:
₹5,00,000

Flow:

OVERDUE
   ↓
TRIAGING
   ↓
ISSUE_IDENTIFIED
   ↓
EVIDENCE_ANALYSIS
   ↓
RESOLUTION_READY
   ↓
POLICY_REVIEW
   ↓
HUMAN_APPROVAL_REQUIRED
   ↓
HUMAN_REVIEW
   ↓
RECOVERY_AUTHORIZED
   ↓
RECOVERY_INITIATED
   ↓
PAYMENT_PENDING
   ↓
Razorpay Payment Link
   ↓
Customer Payment
   ↓
Verified Razorpay Webhook
   ↓
PAYMENT_CONFIRMED Domain Event
   ↓
Financial Reconciliation
   ↓
PARTIALLY_RECOVERED

Result:

Invoice:
₹10,00,000

Recovered:
₹9,00,000

Verified disputed / unresolved:
₹1,00,000

The critical architectural distinction is:

₹9L collectible
       ≠
₹9L automatically authorized

Because the autonomous authority is ₹5L, human approval is required.

30. Unsafe Scenario — Conflicting Evidence

If material evidence conflicts:

Invoice
PO
GRN
Customer Communication
       ↓
Triage
       ↓
Evidence Analysis
       ↓
CONFLICT DETECTED
       ↓
Financial Assessment Cannot Safely Establish Recovery
       ↓
Resolution Restricted
       ↓
Policy / State Machine
       ↓
HUMAN_REVIEW

No unsupported Razorpay recovery action should be created.

31. Legal-Risk Scenario

If a qualifying legal/high-risk signal is detected:

Customer Communication
       ↓
Safety Detection
       ↓
LEGAL_RISK
       ↓
AUTOMATION_LOCKED
       ↓
Automated Recovery → STOP
       ↓
Prohibited Outreach → STOP
       ↓
LEGAL_ESCALATION
       ↓
Human Review

The AI cannot remove the lock.

A legal lock must be enforced outside the LLM.

32. Failure Isolation

A failure in one component must not result in unsafe financial execution.

AI Failure
AI Failure
   ↓
No Valid Recommendation
   ↓
No Recovery Execution
Evidence Failure
Evidence Unavailable
   ↓
No Unsupported Inference
   ↓
Human Review
Financial Calculation Failure
Financial Assessment Failure
   ↓
No Authoritative Amount
   ↓
No Financial Execution
Policy Failure
Policy Check Failure
   ↓
No Authorization
   ↓
No Executor Call
State Machine Failure
Invalid State Transition
   ↓
No Execution
Razorpay Failure
Provider Failure
   ↓
Execution Failed / Retry
   ↓
No Payment Confirmation
Webhook Failure
Webhook Failure
   ↓
No Verified Payment Event
   ↓
Payment Remains Unconfirmed
33. Concurrency and Consistency

Sensitive operations must be protected against:

duplicate Recovery Actions,
simultaneous state transitions,
stale financial assessments,
stale approvals,
duplicate webhook events,
concurrent payment processing.

Appropriate mechanisms include:

PostgreSQL transactions,
unique constraints,
idempotency keys,
row-level locking where required,
optimistic/version checks,
exact action fingerprints.

A Recovery Action must be revalidated immediately before execution.

A payment webhook must be idempotent.

34. Stale Data Protection

A proposal or approval may become stale if financial state changes.

Examples:

Payment received
Credit note issued
Dispute changed
Policy changed
Recovery amount changed
Case state changed

Therefore:

Stored Proposal
      ↓
Current Financial Assessment
      ↓
Current Policy
      ↓
Current Approval
      ↓
Current State

must be revalidated before execution.

A stale proposal must not authorize execution.

35. Observability

The MVP should provide sufficient observability without introducing a large distributed observability stack.

At minimum, record:

request ID
case ID
agent run ID
proposal ID
policy decision ID
recovery action ID
approval ID
payment ID
Razorpay external reference
state transition
error category

Sensitive secrets must never be logged.

Unnecessary customer information must not be logged.

36. Deployment Architecture

Initial deployment:

                 Internet
                    │
                    ▼
             Next.js Frontend
                    │
                    ▼
               FastAPI API
                    │
          ┌─────────┴─────────┐
          ▼                   ▼
      PostgreSQL           LLM Provider
          │
          ▼
     Domain / Audit Data
          │
          ▼
     Recovery Executor
          │
          ▼
      Razorpay APIs
          │
          ▼
   Razorpay Webhook
          │
          ▼
      FastAPI Webhook

The architecture does not require:

Kubernetes,
Kafka,
separate microservices,
distributed event buses,
vector databases,
service meshes,

for the MVP.

These may be introduced later only if justified by an actual scaling requirement.

37. Why a Modular Monolith

The system has multiple logical domains but does not require separately deployed services for the MVP.

A modular monolith provides:

fast iteration,
simpler local development,
explicit module boundaries,
low deployment overhead,
easier debugging,
easier testing,
easier code review,
lower infrastructure complexity.

The architectural goal is separation of responsibility, not maximum service count.

38. Component Responsibility Matrix
Component	Primary Responsibility	Financial Authority	Can Execute Payment?	Can Change Case State?
Frontend	Presentation / interaction	No	No	No
API	Request boundary	No	No	No
Orchestrator	Workflow coordination	No	No	No
Triage Agent	Issue classification	No	No	No
Evidence Agent	Evidence interpretation	No	No	No
Resolution Agent	Action recommendation	No	No	No
Financial Service	Financial assessment	Yes	No	No
Policy Engine	Authorization rules	No	No	No
Human Approval	Explicit authorization	No	No	No
State Machine	State authority	No	No	Yes
Recovery Executor	Controlled execution	No	Yes	Via State Machine
Razorpay Adapter	Provider communication	Provider-side only	Yes	No
Webhook Processor	Provider event verification	Payment event evidence	No	Via State Machine
Audit Service	Immutable event history	No	No	No
39. Architectural Non-Negotiables

The following rules must not be violated without an explicit architecture decision.

AI

LLM outputs are untrusted recommendations.

AI cannot directly execute payment operations.

AI cannot bypass policy.

AI cannot bypass human approval.

AI cannot override legal locks.

Financial

Financial calculations are deterministic.

Authoritative financial values use exact monetary representation.

AI cannot increase collectible or safely recoverable amounts.

Recovery cannot exceed authoritative financial limits.

Policy

Policy validation is deterministic.

Human approval requirements are determined outside the LLM.

Policy decisions are auditable and versioned.

State

State transitions are deterministic.

The LLM cannot directly mutate Recovery Case state.

Payment confirmation is a domain event, not a case state.

Payment

Only the Recovery Executor can initiate provider-side payment operations.

The frontend cannot directly call Razorpay.

The AI cannot call Razorpay.

Payment Link creation does not equal payment recovery.

Payment success requires verified external payment evidence.

Webhooks

Webhook signatures must be verified.

Webhook processing must be idempotent.

Unknown or invalid events must not mutate financial state.

Duplicate webhook events must not create duplicate financial effects.

Audit

Material financial events must be auditable.

Material authorization decisions must be auditable.

Material state transitions must be auditable.

Evaluation

Ground truth must not enter inference.

Evaluation must distinguish AI recommendation quality from deterministic financial correctness.

40. Architectural Invariants

The following invariants must hold:

AI Recommendation
    ≠
Authorization
Collectible Amount
    ≠
Autonomous Authority
Policy Decision
    ≠
Recovery Case State
Payment Link Created
    ≠
Payment Recovered
Provider Payment Event
    ≠
Application Financial State
Customer Instruction
    ≠
System Instruction
Evidence Claim
    ≠
Verified Financial Fact

until deterministic validation establishes the relevant fact.

41. End-to-End Control Model

The complete system follows:

INTERPRET
    ↓
AI Layer

VALIDATE
    ↓
Schema + Evidence Validation

CALCULATE
    ↓
Financial Calculation Service

RECOMMEND
    ↓
Resolution Agent

AUTHORIZE
    ↓
Policy Engine
    ↓
Human Approval if Required

TRANSITION
    ↓
State Machine

EXECUTE
    ↓
Recovery Executor
    ↓
Razorpay

VERIFY
    ↓
Webhook Verification

RECONCILE
    ↓
Financial State

AUDIT
    ↓
Immutable Event History

This separation is the core safety architecture of the system.

42. Architecture Summary

The Receivables Resolution Agent is intentionally designed as a controlled AI system rather than an autonomous LLM with unrestricted financial access.

                    ┌─────────────────┐
                    │   Finance User  │
                    └────────┬────────┘
                             │
                             ▼
                    ┌─────────────────┐
                    │    Frontend     │
                    └────────┬────────┘
                             │
                             ▼
                    ┌─────────────────┐
                    │   FastAPI API   │
                    └────────┬────────┘
                             │
                             ▼
                    ┌─────────────────┐
                    │  Orchestrator   │
                    └────────┬────────┘
                             │
             ┌───────────────┼────────────────┐
             ▼               ▼                ▼
        ┌─────────┐    ┌────────────┐   ┌────────────┐
        │ AI Layer│    │ Financial  │   │  Evidence  │
        │         │    │ Calculation│   │   Layer    │
        └────┬────┘    └──────┬─────┘   └─────┬──────┘
             │                │               │
             └────────────────┼───────────────┘
                              │
                              ▼
                       ┌─────────────┐
                       │   Policy    │
                       │   Engine    │
                       └──────┬──────┘
                              │
                              ▼
                       ┌─────────────┐
                       │   Human     │
                       │  Approval   │
                       │ if required │
                       └──────┬──────┘
                              │
                              ▼
                       ┌─────────────┐
                       │    State    │
                       │   Machine   │
                       └──────┬──────┘
                              │
                              ▼
                       ┌─────────────┐
                       │  Recovery   │
                       │  Executor   │
                       └──────┬──────┘
                              │
                              ▼
                         Razorpay
                              │
                              ▼
                          Webhook
                              │
                              ▼
                    Verified Payment
                              │
                              ▼
                       Reconciliation
                              │
                     ┌────────┴────────┐
                     ▼                 ▼
                PostgreSQL          Audit

The architectural principle is:

AI provides semantic intelligence. Deterministic systems control money, authorization, state, execution, verification, and audit.

This architecture allows the system to demonstrate meaningful AI-driven revenue recovery while keeping financial execution bounded, explainable, testable, and safe.