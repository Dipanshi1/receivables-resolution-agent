# Receivables Resolution Agent — Architecture

## 1. System Overview

Receivables Resolution Agent is a modular-monolith application for AI-assisted B2B receivables resolution.

The system combines:

- AI-based semantic reasoning,
- deterministic financial calculations,
- deterministic policy enforcement,
- deterministic state management,
- Razorpay payment execution,
- verified payment webhooks,
- human escalation, and
- auditability.

The primary architecture is:

```text
Finance User
     ↓
Next.js Frontend
     ↓
FastAPI Backend
     ↓
Recovery Orchestrator
     │
     ├── Triage Agent
     ├── Evidence Service / Agent
     ├── Financial Calculation
     ├── Resolution Agent
     ├── Policy Engine
     ├── State Machine
     ├── Human Approval / Escalation
     ├── Audit Service
     └── Recovery Executor
                ↓
         Razorpay Adapter
                ↓
          Razorpay APIs
                ↓
        Razorpay Webhooks
                ↓
        Webhook Verification
                ↓
        Payment / State Update
2. Architectural Principle

The core system boundary is:

AI interprets and recommends; deterministic systems calculate, authorize, transition, execute, and verify.

This principle governs the entire implementation.

3. Trust Boundaries
Untrusted
Customer communications
Uploaded documents
External business content
Frontend input
LLM output
Razorpay webhook before verification
Controlled
Input validation
Evidence processing
Financial Calculation Service
Policy Engine
State Machine
Human Approval
Webhook Verification
Financial Execution
Recovery Executor
      ↓
Razorpay Adapter
      ↓
Razorpay
4. Core Workflow

The canonical workflow is:

At-Risk Receivable
       ↓
Triage
       ↓
Evidence Analysis
       ↓
Deterministic Financial Assessment
       ↓
Resolution Proposal
       ↓
Policy Validation
       ↓
State Validation
       ↓
Recovery Execution
       ↓
Payment Confirmation
       ↓
Recovery Outcome
       ↓
Audit

Exceptional conditions branch into:

Human Review
Legal Escalation
Automation Lock
Execution Failure
5. AI Layer

The MVP contains three bounded reasoning components:

Triage Agent
Evidence Agent
Resolution Agent

They may:

classify issues,
extract facts,
assess evidence,
recommend actions.

They may not:

execute Razorpay operations,
confirm payment,
directly modify financial state,
bypass policy,
bypass the State Machine,
remove safety locks.
6. Financial Calculation Boundary

Financial calculations are deterministic.

Examples:

Verified disputed amount
Collectible amount
Safely recoverable amount
Recovered amount
Remaining amount

For INR, monetary values are represented internally using minor units.

Floating-point arithmetic must not be used for authoritative financial calculations.

7. Policy Boundary

Every executable recovery action passes through the Policy Engine.

The Policy Engine evaluates:

Evidence sufficiency
Evidence conflict
Collectible amount
Automated financial authority
Concession limits
Outreach limits
Quiet hours
Legal locks
Human approval requirements
Current state

Possible outcomes:

APPROVED
DEFERRED
HUMAN_APPROVAL_REQUIRED
BLOCKED
STOPPED
8. State Boundary

The State Machine is the only authority for Recovery Case state transitions.

Core states include:

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

Invalid transitions must be rejected.

The LLM cannot directly mutate state.

9. Payment Boundary

The Recovery Executor may communicate with Razorpay only after:

Valid Proposal
      +
Financial Revalidation
      +
Policy Approval
      +
Valid State
      +
Required Human Approval

Razorpay operations are isolated behind a provider adapter.

10. Payment Confirmation Boundary

The system does not consider a payment successful merely because a Payment Link was created.

The confirmation path is:

Razorpay Webhook
      ↓
Raw Body Signature Verification
      ↓
Event Validation
      ↓
Event Idempotency
      ↓
Payment Mapping
      ↓
Financial Reconciliation
      ↓
State Machine
      ↓
Audit Event
11. Human-in-the-Loop Boundary

Human involvement is required when:

evidence is insufficient,
evidence conflicts,
recovery exceeds autonomous authority,
a concession exceeds configured authority,
legal/high-risk conditions occur,
execution cannot safely continue.

Human approval is bound to:

Case
+
Proposal
+
Action
+
Amount
+
Approver

A modified action requires new validation and approval.

12. Data Layer

PostgreSQL is the primary datastore.

Major domain entities:

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

The database preserves separation between:

Customer Claim
Verified Evidence
Collectible Assessment
AI Recommendation
Policy Decision
Recovery Action
Actual Payment
13. Audit Layer

Material decisions and state changes are recorded as append-oriented audit events.

The audit trail must reconstruct:

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
Recovery Action
   ↓
Payment Event
   ↓
Verified Payment
   ↓
Recovery Outcome

Private model chain-of-thought is not stored or exposed.

14. Evaluation Architecture

The benchmark uses the same application-level recovery workflow with a mock payment provider.

Benchmark Dataset
       ↓
Recovery Orchestrator
       ↓
AI + Deterministic Controls
       ↓
MockPaymentProvider
       ↓
Case Outcome
       ↓
Evaluator
       ↓
Metrics

Live Razorpay Test Mode is used for selected end-to-end demonstrations, not for the entire benchmark batch.

15. Provider Abstraction

The payment domain depends on an application-level provider interface:

PaymentProvider
      │
      ├── RazorpayProvider
      │
      └── MockPaymentProvider

This allows:

real Razorpay Test Mode integration,
deterministic benchmark execution,
provider-independent domain logic.
16. Deployment Shape

The initial deployment is intentionally simple:

Internet
   ↓
Next.js Frontend
   ↓
FastAPI Backend
   ↓
PostgreSQL

FastAPI Backend
   ↓
LLM Provider

FastAPI Backend
   ↓
Razorpay APIs

Razorpay
   ↓
FastAPI Webhook Endpoint

The MVP does not require Kubernetes, Kafka, or microservices.

17. Architectural Invariants

The following are non-negotiable:

1. AI output is untrusted.
2. Financial calculations are deterministic.
3. Policy validation is deterministic.
4. State transitions are deterministic.
5. AI cannot directly call Razorpay.
6. Payment success requires verified external evidence.
7. Legal locks cannot be bypassed.
8. Unsupported recovery cannot execute.
9. Duplicate webhook events cannot create duplicate financial effects.
10. Frontend cannot directly mutate financial state.
11. Critical failures fail closed.
12. Material financial decisions are auditable.
18. Source Documents

The detailed engineering architecture is defined in:

docs/02-engineering/architecture.md
docs/02-engineering/system-components.md
docs/02-engineering/domain-model.md
docs/02-engineering/database-schema.md
docs/02-engineering/state-machine.md
docs/02-engineering/policy-engine.md
docs/02-engineering/ai-contracts.md
docs/02-engineering/api-contracts.md
docs/02-engineering/razorpay-integration.md
docs/02-engineering/webhook-design.md
docs/02-engineering/audit-system.md
docs/02-engineering/security-model.md

This root document is a concise architectural map; the detailed engineering documents remain the implementation references.

19. Architectural Principle

The system is intentionally designed so that:

AI understands the problem.
       ↓
Evidence establishes what is supported.
       ↓
Deterministic code calculates the financial result.
       ↓
Policy determines what is permitted.
       ↓
State Machine determines what can happen next.
       ↓
Razorpay executes approved payment operations.
       ↓
Verified events establish payment truth.
       ↓
Audit records the complete workflow.