# System Components

## 1. Purpose

This document defines the responsibilities, inputs, outputs, dependencies, and boundaries of the components that make up the Receivables Resolution Agent.

The purpose is to ensure that each component has a clearly defined role and that no component—especially an AI component—has unrestricted authority over financial state or money movement.

The system follows this principle:

> **Semantic reasoning may be probabilistic; financial control must be deterministic.**

---

# 2. Component Architecture

The MVP consists of the following logical components:

```text
Frontend
   │
   ▼
API Layer
   │
   ▼
Recovery Orchestrator
   │
   ├── Triage Agent
   ├── Evidence Service / Evidence Agent
   ├── Resolution Agent
   ├── Policy Engine
   ├── State Machine
   ├── Recovery Executor
   ├── Human Approval / Escalation
   ├── Audit Service
   └── Evaluation Runner
                │
                ▼
        Razorpay Integration
                │
                ▼
            Webhooks
                │
                ▼
            PostgreSQL
3. Frontend
Responsibility

Provide the finance and accounts-receivable user interface.

Technology

Next.js + TypeScript + React.

Primary capabilities
recovery dashboard,
recovery-case list,
recovery-case detail,
evidence inspection,
resolution proposal display,
policy decision display,
human approval interface,
escalation interface,
payment/recovery status,
audit timeline,
evaluation metrics.
Inputs

Frontend receives information through the backend API.

Outputs

Frontend sends user-initiated actions to the backend API.

Examples:

Approve recovery
Reject proposal
Request human review
View case
Filter cases
View audit trace
Must not

The frontend must never:

access the database directly,
access LLM credentials,
access Razorpay credentials,
directly execute financial APIs,
directly modify financial state.

All such actions pass through the backend.

4. API Layer
Responsibility

Expose application APIs and provide the external interface of the backend.

Technology

FastAPI.

Responsibilities
HTTP request handling,
authentication/authorization boundary where implemented,
input validation,
response serialization,
routing,
API-level error handling,
webhook endpoint exposure.
Must not

The API layer should not contain substantial business logic.

For example, route handlers should not directly calculate collectible amounts or directly call the LLM and Razorpay in sequence.

Instead:

API Route
   ↓
Application Service
   ↓
Domain / Integration Components
5. Recovery Orchestrator
Responsibility

Coordinate the recovery workflow.

The Recovery Orchestrator is the application-level coordinator that moves a Recovery Case through the defined workflow.

Responsibilities
Load the current case.
Determine the next permitted operation.
Invoke the appropriate AI component.
Validate AI output.
invoke evidence processing where required.
Create resolution proposals.
submit proposals to the Policy Engine.
request human approval when necessary.
request valid state transitions.
invoke the Recovery Executor after approval.
record workflow outcomes.
Must not

The orchestrator must not bypass:

policy validation,
state validation,
webhook-based payment confirmation,
audit recording.

It coordinates these controls; it does not replace them.

6. Triage Agent
Responsibility

Determine the likely reason a receivable is overdue or blocked.

AI Role

Semantic classification and structured interpretation.

Inputs
invoice context,
customer information,
payment state,
customer communications,
previous recovery history.
Outputs

Structured TriageResult.

Example:

{
  "issue_type": "QUANTITY_DISPUTE",
  "confidence": 0.96,
  "summary": "Customer disputes 10 undelivered licenses",
  "requires_evidence_analysis": true,
  "risk_flags": []
}
Responsibilities
identify primary issue,
identify relevant risk flags,
determine whether evidence analysis is required.
Must not

The Triage Agent must not:

calculate authoritative financial amounts,
change invoice balances,
create payment requests,
approve concessions,
mark an invoice as paid,
change policy,
directly transition to a financial success state.
7. Evidence Service
Responsibility

Retrieve, normalize, and prepare business evidence for analysis.

Inputs

Potential sources:

Invoice
Invoice Lines
Purchase Order
GRN / Delivery Record
Contract
Milestone Record
Customer Communication
Payment History
Credit Note
Responsibilities
retrieve relevant records,
normalize structured facts,
preserve provenance,
identify missing evidence,
identify duplicate evidence,
expose relevant evidence to the Evidence Agent,
retain source references.
Output

An evidence context that can be consumed by the Evidence Agent.

Must not

The Evidence Service must not silently manufacture missing facts.

A missing record must remain explicitly missing.

8. Evidence Agent
Responsibility

Interpret evidence and determine whether the customer's objection is supported.

AI Role

Semantic reasoning over heterogeneous business information.

Inputs
customer objection,
invoice,
PO,
GRN,
contract,
milestone information,
relevant communications,
payment history.
Outputs

Structured EvidenceAssessment.

Example:

{
  "finding": "PARTIALLY_SUPPORTED",
  "claims": [
    {
      "claim": "10 licenses were not delivered",
      "status": "SUPPORTED",
      "evidence_ids": [
        "E-001",
        "E-002"
      ]
    }
  ],
  "confidence": 0.94,
  "requires_human_review": false
}
Responsibilities
connect customer claims to evidence,
extract structured facts,
identify support/contradiction,
identify evidence gaps,
identify conflicts,
produce evidence references.
Must not

The Evidence Agent must not:

directly change invoice amounts,
directly authorize recovery,
ignore contradictory evidence,
invent missing records,
directly call Razorpay.
9. Financial Calculation Service
Responsibility

Perform authoritative monetary calculations.

This is intentionally a deterministic component and not an AI agent.

Examples

Calculate:

disputed amount,
collectible amount,
recovered amount,
remaining amount,
concession amount,
balances.
Example

Input:

Quantity invoiced = 100
Quantity delivered = 90
Unit price = ₹9,000

Deterministic calculation:

Disputed quantity = 10

Disputed amount = ₹90,000

Collectible amount =
Invoice amount - verified disputed amount
Must not

The Financial Calculation Service must not use an LLM to perform authoritative arithmetic.

All calculations must use exact monetary representations.

10. Resolution Agent
Responsibility

Recommend the appropriate next action.

Inputs
triage result,
evidence assessment,
calculated collectible amount,
recovery history,
customer context,
merchant policy context.
Outputs

Structured ResolutionProposal.

Example:

{
  "action": "CREATE_PARTIAL_RECOVERY",
  "amount": 900000,
  "reason_code": "UNDISPUTED_AMOUNT",
  "confidence": 0.93,
  "evidence_ids": [
    "E-001",
    "E-002"
  ]
}
Must not

The Resolution Agent must not:

directly execute payment actions,
bypass policy,
bypass the state machine,
alter merchant policy,
mark payments as successful,
override a legal lock.

It produces a proposal only.

11. Policy Engine
Responsibility

Determine whether a proposed action is permitted.

Technology

Deterministic application logic.

Inputs
Recovery Case,
Resolution Proposal,
merchant policy,
evidence assessment,
current time,
prior actions,
current state.
Policy dimensions
Evidence sufficiency
Financial authority
Concession limits
Outreach limits
Quiet hours
Legal lock
Human approval requirements
State validity
Outputs
APPROVED
DEFERRED
HUMAN_APPROVAL_REQUIRED
BLOCKED
STOPPED
Must not

The Policy Engine must not rely on LLM output to enforce safety rules.

Policy decisions must be reproducible for identical inputs.

12. State Machine
Responsibility

Control valid Recovery Case state transitions.

Inputs
current state,
domain event,
policy decision,
payment event,
human decision.
Outputs

A valid next state or a transition rejection.

Example
RESOLUTION_READY
       ↓
POLICY_APPROVED
       ↓
RECOVERY_INITIATED
Must not

The State Machine must not allow:

OVERDUE → FULLY_RECOVERED

without the required preceding events.

The LLM must never directly mutate state.

13. Recovery Executor
Responsibility

Execute an approved recovery action.

Inputs
approved Resolution Proposal,
Policy Decision,
valid Recovery Case state,
execution metadata.
Responsibilities
revalidate the execution request,
call the Razorpay integration layer,
store external references,
create recovery-action records,
trigger appropriate state transitions.
Must not

The executor must not accept a proposal that has:

failed policy validation,
failed state validation,
missing human approval where required,
invalid financial amount,
legal lock.
14. Razorpay Integration Adapter
Responsibility

Isolate Razorpay-specific operations from the core domain.

Responsibilities
authenticate with Razorpay,
create Payment Links or supported payment requests,
pass reference/metadata information,
retrieve provider results where required,
expose normalized payment-provider responses.
Architecture boundary
Domain
   ↓
Razorpay Integration Adapter
   ↓
Razorpay APIs

The domain layer should not depend directly on SDK-specific implementation details.

15. Webhook Handler
Responsibility

Process external Razorpay events.

Flow
Razorpay
   ↓
Webhook Endpoint
   ↓
Signature Verification
   ↓
Payload Validation
   ↓
Idempotency Check
   ↓
Payment Lookup
   ↓
Payment State Update
   ↓
State Machine
   ↓
Audit Event
Must not

The webhook handler must not:

trust an unauthenticated event,
process a duplicate event as a new payment,
directly mark arbitrary invoices as paid,
bypass the state machine.
16. Human Approval Service
Responsibility

Manage actions requiring explicit human authorization.

Inputs
recovery case,
resolution proposal,
policy decision.
Outputs
APPROVED
REJECTED
PENDING
Approval binding

Approval must be associated with the exact:

case,
proposal,
action,
amount,
approver.

If the proposal changes, approval must no longer be considered valid.

17. Escalation Service
Responsibility

Move cases that cannot safely proceed automatically into the appropriate human workflow.

Escalation types
HUMAN_REVIEW
LEGAL_ESCALATION
EVIDENCE_REVIEW
APPROVAL_REQUIRED
Responsibilities
create escalation record,
preserve relevant context,
attach evidence references,
stop prohibited autonomous actions,
expose the case to the appropriate operator.
Must not

The escalation service must not silently discard or reset case history.

18. Audit Service
Responsibility

Record material workflow events.

Inputs

Events from:

orchestrator,
agents,
policy engine,
state machine,
Razorpay integration,
webhook handler,
human approval,
escalation.
Output

Append-only audit events.

Example
{
  "event_type": "POLICY_CHECKED",
  "case_id": "CASE-1042",
  "actor_type": "POLICY_ENGINE",
  "state_before": "RESOLUTION_READY",
  "state_after": "POLICY_REVIEW",
  "policy_version": "v1.0"
}
Must not

The audit system must not expose or depend on private LLM chain-of-thought.

It records decision facts, inputs/references, policy outcomes, state transitions, and provenance.

19. Evaluation Runner
Responsibility

Execute the synthetic benchmark.

Inputs
benchmark dataset,
system configuration,
selected model/configuration.
Workflow
Case
 ↓
Triage
 ↓
Evidence
 ↓
Resolution
 ↓
Policy
 ↓
Recovery Simulation
 ↓
Expected Outcome Comparison
Outputs
per-case results,
aggregate metrics,
safety violations,
recovery results,
error categories.
Must not

The evaluation runner must not expose ground truth to the inference path.

20. Evaluation Metrics Service
Responsibility

Calculate benchmark metrics.

Initial metrics:

Recovery Rate
Resolution Accuracy
Collectible Amount Accuracy
Unsupported Recovery Rate
Policy Violation Rate
Human Escalation Rate
Cycle-Time Reduction

The metrics service must distinguish:

system correctness,
financial outcome,
safety behavior,
human escalation.
21. Database Layer
Responsibility

Persist domain and operational state.

Technology

PostgreSQL + SQLAlchemy.

Main entities
Merchant
Customer
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
Principle

Database writes involving financial state should occur through domain/application services rather than arbitrary direct writes from AI components.

22. Configuration Layer
Responsibility

Provide validated runtime configuration.

Examples:

DATABASE_URL
LLM_API_KEY
RAZORPAY_KEY_ID
RAZORPAY_KEY_SECRET
RAZORPAY_WEBHOOK_SECRET

Configuration must be validated at startup.

Secrets must never be committed to Git.

23. Error Handling Layer

Errors should be classified rather than silently swallowed.

Important categories:

VALIDATION_ERROR
AI_OUTPUT_INVALID
EVIDENCE_UNAVAILABLE
EVIDENCE_CONFLICT
POLICY_BLOCKED
HUMAN_APPROVAL_REQUIRED
LEGAL_LOCK
INVALID_STATE_TRANSITION
RAZORPAY_API_ERROR
WEBHOOK_SIGNATURE_INVALID
DUPLICATE_WEBHOOK
PAYMENT_NOT_CONFIRMED

Errors that could cause unsafe financial behavior must fail closed.

24. Component Trust Model
Untrusted / probabilistic
Customer content
External documents
LLM output
Deterministic / controlled
Financial calculation
Policy Engine
State Machine
Approval validation
Webhook validation
External financial execution
Razorpay

The architecture must preserve these boundaries.

25. Component Interaction Rules
Rule 1

AI components produce structured recommendations, not financial execution.

Rule 2

Financial calculations happen in deterministic application code.

Rule 3

Policy validation occurs before executable recovery actions.

Rule 4

State transitions are controlled by the State Machine.

Rule 5

Razorpay calls are made only by the dedicated integration layer.

Rule 6

Payment success is established only through verified payment events.

Rule 7

Legal locks cannot be overridden by AI.

Rule 8

Insufficient or conflicting evidence prevents unsupported automatic recovery.

Rule 9

Material decisions generate audit events.

Rule 10

A component must not modify another component's state through undocumented side effects.

26. Component Dependency Direction

The intended dependency direction is:

API
 ↓
Application Services / Orchestrator
 ↓
Domain Components
 ↓
Integration Adapters

More specifically:

Frontend
   ↓
API
   ↓
Orchestrator
   ├── AI Components
   ├── Evidence
   ├── Financial Calculation
   ├── Policy
   ├── State
   ├── Approval / Escalation
   └── Recovery Executor
             ↓
       Razorpay Adapter

The AI components must not become a lower-level dependency of the financial domain.

27. Component Communication Principle

Components should communicate through typed data contracts.

Examples:

TriageResult
EvidenceAssessment
ResolutionProposal
PolicyDecision
PaymentResult
StateTransitionResult
AuditEvent

Free-form strings should not be used as the primary contract between components.

28. Golden Component Flow

For the canonical ₹10,00,000 invoice:

Invoice
   ↓
Triage Agent
   ↓
QUANTITY_DISPUTE
   ↓
Evidence Service
   ↓
Evidence Agent
   ↓
90/100 licenses verified
   ↓
Financial Calculation
   ↓
₹1,00,000 disputed
₹9,00,000 collectible
   ↓
Resolution Agent
   ↓
CREATE_PARTIAL_RECOVERY ₹9,00,000
   ↓
Policy Engine
   ↓
₹9,00,000 exceeds ₹5,00,000 autonomous authority
   ↓
HUMAN_APPROVAL_REQUIRED
   ↓
State Machine
   ↓
HUMAN_REVIEW
   ↓
Valid human approval for the exact action fingerprint
   ↓
RECOVERY_INITIATED
   ↓
Recovery Executor
   ↓
Razorpay
   ↓
Payment Link
   ↓
PAYMENT_PENDING
   ↓
Verified Webhook
   ↓
PAYMENT_CONFIRMED domain event
   ↓
Financial Reconciliation
   ↓
PARTIALLY_RECOVERED
   ↓
Audit Event
29. Golden Safety Flow

For a case with legal-risk content:

Customer Communication
        ↓
Triage / Safety Detection
        ↓
LEGAL_RISK
        ↓
Policy Engine
        ↓
STOPPED
        ↓
Automation Lock
        ↓
No automated recovery
        ↓
No automated outreach
        ↓
Legal / Human Escalation
        ↓
Audit Event
30. Design Principle

Every component should have one primary responsibility.

The architecture deliberately avoids creating an autonomous AI component that owns the entire financial workflow.

The desired system behavior is:

AI understands the case. Deterministic systems decide what is allowed. Razorpay executes approved payment operations. Verified external events establish payment truth. Humans handle uncertainty and exceptions.
