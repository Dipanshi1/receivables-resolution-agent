# API Contracts

## 1. Purpose

This document defines the HTTP API contract for the Receivables Resolution Agent backend.

The API provides the interface between:

- the frontend,
- the recovery workflow,
- human operators,
- evaluation tooling, and
- Razorpay webhook delivery.

The API must preserve the system's architectural boundaries.

The backend is the only application component permitted to communicate with Razorpay credentials or execute financial actions.

---

# 2. API Technology

Backend framework:

**FastAPI**

Transport:

**HTTPS**

Data format:

**JSON**

API version:

```text
/v1

Example:

/v1/recovery-cases
3. API Design Principles

The API must follow these principles:

Validate all input.
Return typed, structured responses.
Keep business logic outside HTTP route handlers.
Never expose secrets.
Never allow the frontend to bypass policy or state validation.
Never allow the frontend or AI layer to directly call Razorpay.
Use idempotency for financial operations where appropriate.
Return deterministic domain errors.
Preserve auditability for material actions.
Use explicit state transitions rather than direct status mutation.
Revalidate financial and authorization state immediately before execution.
Treat all client-provided financial and state values as untrusted.

The API is an interface to the controlled domain workflow, not a shortcut around it.

4. Authentication Boundary

The MVP may use a simplified authenticated development environment.

The production-oriented architecture should support:

Bearer token / session
        ↓
Authentication
        ↓
Authorization
        ↓
Merchant / User context

Every protected endpoint must establish the authenticated merchant/user context before accessing merchant data.

The backend must prevent cross-merchant access.

Merchant identity rule

Protected endpoints must derive merchant_id from authenticated context.

The frontend must not be trusted to select an arbitrary merchant by supplying:

{
  "merchant_id": "some-other-merchant"
}

Where a resource is identified by ID, the backend must verify that the resource belongs to the authenticated merchant.

5. Standard API Response Structure

Successful responses may return resource-specific JSON.

Errors should use a common structure:

{
  "error": {
    "code": "POLICY_BLOCKED",
    "message": "Recovery action is not permitted by the current merchant policy.",
    "request_id": "req_123",
    "details": {}
  }
}

The request_id should allow the request to be traced through application logs and audit records where appropriate.

6. Standard HTTP Status Codes

The API should use standard HTTP semantics.

200 OK
201 Created
202 Accepted
400 Bad Request
401 Unauthorized
403 Forbidden
404 Not Found
409 Conflict
422 Unprocessable Entity
429 Too Many Requests
500 Internal Server Error
502 Bad Gateway
503 Service Unavailable

Financial-domain conflicts should normally use:

409 Conflict

rather than a generic server error.

7. Resource: Invoices
POST /v1/invoices

Creates/imports an invoice into the application.

Request
{
  "customer_id": "uuid",
  "invoice_number": "INV-1042",
  "currency": "INR",
  "total_amount_minor": 100000000,
  "issue_date": "2026-08-01",
  "due_date": "2026-08-15",
  "line_items": [
    {
      "line_number": 1,
      "description": "Software Licenses",
      "product_code": "LIC-001",
      "quantity": 100,
      "unit_price_minor": 1000000,
      "tax_amount_minor": 0,
      "line_total_minor": 100000000
    }
  ],
  "external_reference": "ERP-INV-1042"
}

merchant_id is intentionally omitted.

It must come from authenticated merchant context.

Response
{
  "invoice": {
    "id": "uuid",
    "invoice_number": "INV-1042",
    "currency": "INR",
    "total_amount_minor": 100000000,
    "amount_paid_minor": 0,
    "status": "OPEN"
  }
}
Validation

The backend must validate:

authenticated merchant exists,
customer belongs to merchant,
invoice number is unique for the merchant,
currency is valid,
monetary values are non-negative,
due date is valid,
line items are valid,
monetary representation uses minor units.
GET /v1/invoices/{invoice_id}

Returns the invoice and its current financial state.

The response may include:

customer,
line items,
payment amount,
invoice status,
associated recovery case summary.

The endpoint must not expose private credentials or internal secrets.

8. Resource: Recovery Cases
POST /v1/recovery-cases

Creates a Recovery Case for an invoice.

Request
{
  "invoice_id": "uuid",
  "trigger": "INVOICE_OVERDUE"
}
Response
{
  "case": {
    "id": "uuid",
    "invoice_id": "uuid",
    "status": "OVERDUE",
    "trigger": "INVOICE_OVERDUE"
  }
}
Rules
Invoice must exist.
Invoice must belong to the authenticated merchant.
Duplicate active recovery cases for the same workflow must be prevented.
Case creation must generate an audit event.
GET /v1/recovery-cases

Lists recovery cases for the current merchant.

Query parameters
status
issue_type
risk_level
page
page_size
sort

Example:

GET /v1/recovery-cases?status=OVERDUE&page=1&page_size=20
Response
{
  "items": [
    {
      "id": "uuid",
      "invoice_number": "INV-1042",
      "customer_name": "Nova Technologies",
      "invoice_amount_minor": 100000000,
      "recovered_amount_minor": 0,
      "collectible_amount_minor": 90000000,
      "disputed_amount_minor": 10000000,
      "status": "RESOLUTION_READY",
      "issue_type": "QUANTITY_DISPUTE",
      "days_overdue": 18
    }
  ],
  "page": 1,
  "page_size": 20,
  "total": 1
}
GET /v1/recovery-cases/{case_id}

Returns complete operational details for a Recovery Case.

Response
{
  "case": {
    "id": "uuid",
    "status": "RESOLUTION_READY",
    "issue_type": "QUANTITY_DISPUTE",
    "risk_level": "LOW",

    "financials": {
      "invoice_amount_minor": 100000000,
      "claimed_disputed_amount_minor": 10000000,
      "verified_disputed_amount_minor": 10000000,
      "collectible_amount_minor": 90000000,
      "safely_recoverable_amount_minor": 90000000,
      "recovered_amount_minor": 0,
      "remaining_amount_minor": 100000000
    },

    "customer": {
      "id": "uuid",
      "name": "Nova Technologies"
    },

    "invoice": {
      "id": "uuid",
      "invoice_number": "INV-1042"
    },

    "resolution": {
      "proposal_id": "uuid",
      "action": "CREATE_PARTIAL_RECOVERY",
      "amount_minor": 90000000,
      "confidence": 0.93
    }
  }
}

Financial values returned by the API should use explicit _minor naming to make their representation unambiguous.

9. Start Triage
POST /v1/recovery-cases/{case_id}/triage

Starts the triage workflow.

Request
{
  "force": false
}

force must never bypass safety, policy, authorization, or state validation.

Response
{
  "case_id": "uuid",

  "triage": {
    "issue_type": "QUANTITY_DISPUTE",
    "confidence": 0.96,
    "summary": "Customer disputes 10 undelivered licenses.",
    "requires_evidence_analysis": true,
    "risk_flags": []
  },

  "state": {
    "before": "TRIAGING",
    "after": "ISSUE_IDENTIFIED"
  }
}
Rules
Case must be eligible for triage.
Case cannot be legally locked.
AI output must pass schema validation.
Triage must produce an AgentRun.
Material result must generate an audit event.
The AI result cannot directly authorize recovery.
10. Evidence Analysis
POST /v1/recovery-cases/{case_id}/evidence

Runs evidence retrieval and analysis.

Request
{
  "scope": "AUTO"
}
Response
{
  "case_id": "uuid",

  "assessment": {
    "finding": "PARTIALLY_SUPPORTED",

    "claims": [
      {
        "claim": "10 licenses were not delivered",
        "status": "SUPPORTED",
        "evidence_ids": [
          "uuid",
          "uuid"
        ]
      }
    ],

    "facts": [
      {
        "name": "quantity_invoiced",
        "value": 100,
        "evidence_ids": ["uuid"]
      },
      {
        "name": "quantity_delivered",
        "value": 90,
        "evidence_ids": ["uuid"]
      }
    ],

    "conflicts": [],
    "missing_evidence": [],
    "confidence": 0.94,
    "requires_human_review": false
  },

  "state": {
    "before": "ISSUE_IDENTIFIED",
    "after": "EVIDENCE_ANALYSIS"
  }
}
Rules
Evidence must be traceable.
Missing evidence must not be replaced with inferred facts.
Conflicts must be surfaced.
Financial values must not be treated as authoritative solely because the LLM produced them.
Extracted facts must pass the appropriate evidence-verification process before becoming authoritative financial inputs.
11. Generate Resolution Proposal
POST /v1/recovery-cases/{case_id}/resolve

Creates a Resolution Proposal using the completed case context.

Request
{
  "force": false
}
Response
{
  "proposal": {
    "id": "uuid",
    "action": "CREATE_PARTIAL_RECOVERY",
    "amount_minor": 90000000,
    "reason_code": "UNDISPUTED_AMOUNT",
    "reason_summary": "Recover the evidence-supported undisputed amount.",
    "confidence": 0.93,
    "evidence_ids": [
      "uuid",
      "uuid"
    ],
    "status": "PENDING"
  },

  "state": {
    "before": "EVIDENCE_ANALYSIS",
    "after": "RESOLUTION_READY"
  }
}
Rules
Proposal must pass AI schema validation.
Monetary amounts must be represented in minor units.
Proposal is a recommendation, not permission to execute.
Proposal must remain immutable once evaluated, except by creating a new proposal/version.
The proposed amount must be independently checked against authoritative financial assessment.
The AI cannot increase the authoritative collectible or safely recoverable amount.
12. Evaluate Policy
POST /v1/recovery-cases/{case_id}/policy-check

Evaluates the current Resolution Proposal against the applicable merchant policy.

Request
{
  "proposal_id": "uuid"
}
Response
{
  "policy_decision": {
    "id": "uuid",
    "decision": "APPROVED",
    "policy_version": "v1.0",

    "checks": {
      "legal_lock": false,
      "evidence_sufficient": true,
      "financial_assessment_verified": true,
      "amount_supported": true,
      "auto_recovery_limit_ok": true,
      "concession_limit_ok": true,
      "touchpoint_limit_ok": true,
      "quiet_hours_ok": true,
      "state_valid": true
    }
  },

  "state": {
    "before": "RESOLUTION_READY",
    "after": "POLICY_REVIEW"
  }
}
Possible decisions
APPROVED
DEFERRED
HUMAN_APPROVAL_REQUIRED
BLOCKED
STOPPED
Rules

This endpoint may evaluate policy but must not allow the frontend to directly force approval.

The Policy Engine remains deterministic and authoritative.

A Policy Decision is not itself authorization to execute unless its decision is APPROVED and all execution guards pass.

HUMAN_APPROVAL_REQUIRED means that the action cannot proceed autonomously.

13. Create Recovery Action / Execute Recovery
POST /v1/recovery-cases/{case_id}/execute

Attempts execution of an authorized recovery action.

This endpoint is the controlled execution boundary.

Request
{
  "proposal_id": "uuid",
  "human_approval_id": null,
  "idempotency_key": "recover-case-1042-v1"
}

If human approval is required, human_approval_id must identify a valid approval bound to the exact action.

Required checks

Before execution:

proposal exists,
proposal belongs to the case,
proposal has valid status,
current case state is valid,
Policy Decision exists,
Policy Decision permits the action,
human approval exists if required,
approval is valid and not expired/invalidated,
approval matches the exact action fingerprint,
current financial assessment is revalidated,
proposed amount remains within collectible amount,
proposed amount remains within safely recoverable amount,
no legal lock exists,
no automation lock exists,
no conflicting recovery action exists,
idempotency key has not already executed the action,
recovery amount remains within permitted bounds.
Successful payment-request creation response
{
  "recovery_action": {
    "id": "uuid",
    "type": "CREATE_PARTIAL_RECOVERY",
    "amount_minor": 90000000,
    "status": "PAYMENT_PENDING",
    "external_provider": "RAZORPAY",
    "external_reference": "plink_xxxxx"
  },

  "state": {
    "before": "RECOVERY_INITIATED",
    "after": "PAYMENT_PENDING"
  }
}
Critical rule

Creation of a Razorpay payment request must not transition the case directly to a recovered state.

The case becomes:

PAYMENT_PENDING

Payment success is established only by verified external payment evidence.

14. Human Approval
POST /v1/recovery-cases/{case_id}/approvals

Creates a human approval decision.

Request
{
  "proposal_id": "uuid",
  "recovery_action_id": "uuid",
  "decision": "APPROVE",
  "reason": "Verified amount exceeds autonomous recovery limit."
}
Response
{
  "approval": {
    "id": "uuid",
    "proposal_id": "uuid",
    "recovery_action_id": "uuid",
    "decision": "APPROVE",
    "approved_amount_minor": 90000000,
    "action_fingerprint": "sha256:...",
    "approved_by": "user-id"
  }
}
Rules

Approval must be tied to:

Recovery Case
+
Resolution Proposal
+
Recovery Action
+
Amount
+
Action Fingerprint

The approval must represent authorization of the exact action.

Changing any material action detail invalidates the previous approval.

The backend must calculate or verify the action fingerprint.

The client must not be allowed to choose an arbitrary fingerprint and thereby manufacture authorization.

15. Escalation
POST /v1/recovery-cases/{case_id}/escalate

Creates a controlled escalation.

Request
{
  "type": "HUMAN_REVIEW",
  "reason_code": "EVIDENCE_CONFLICT",
  "notes": "GRN and customer communication report different quantities."
}
Response
{
  "escalation": {
    "id": "uuid",
    "type": "HUMAN_REVIEW",
    "status": "OPEN",
    "reason_code": "EVIDENCE_CONFLICT"
  },

  "case": {
    "status": "HUMAN_REVIEW"
  }
}
Legal escalation
{
  "type": "LEGAL_ESCALATION",
  "reason_code": "LEGAL_RISK"
}

The backend must apply the appropriate automation lock where required.

The frontend cannot manually remove a legal or safety lock.

16. Audit Events
GET /v1/recovery-cases/{case_id}/audit

Returns the chronological audit history.

Query parameters
page
page_size
event_type
Response
{
  "case_id": "uuid",

  "events": [
    {
      "id": "uuid",
      "timestamp": "2026-08-30T12:32:01Z",
      "event_type": "TRIAGE_COMPLETED",
      "actor_type": "AI_AGENT",
      "actor_id": "TRIAGE",
      "state_before": "TRIAGING",
      "state_after": "ISSUE_IDENTIFIED",
      "policy_version": null,

      "payload": {
        "issue_type": "QUANTITY_DISPUTE"
      }
    }
  ]
}

The API must not expose private model chain-of-thought.

It should expose structured decision facts, provenance, references, and outcomes.

17. Dashboard Summary
GET /v1/dashboard/summary

Returns merchant-level recovery metrics.

Response
{
  "revenue_at_risk_minor": 28400000,
  "safely_recoverable_minor": 19200000,
  "automatically_recovered_minor": 14600000,
  "awaiting_human_review_minor": 3100000,
  "blocked_minor": 700000,

  "metrics": {
    "recovery_rate_percent": 76.0,
    "resolution_accuracy_percent": 94.0,
    "unsupported_recovery_rate_percent": 0.0,
    "policy_violation_rate_percent": 0.0,
    "human_escalation_rate_percent": 18.0
  }
}

The metrics returned here should come from persisted application/evaluation state rather than frontend calculations over raw records.

18. Evaluation APIs
POST /v1/evaluations

Starts a benchmark run.

Request
{
  "dataset": "benchmark-v1"
}
Response
{
  "run_id": "uuid",
  "status": "QUEUED"
}
GET /v1/evaluations/{run_id}

Returns benchmark results.

Response
{
  "run_id": "uuid",
  "status": "COMPLETED",

  "metrics": {
    "cases": 100,
    "recovery_rate_percent": 76.0,
    "resolution_accuracy_percent": 94.0,
    "collectible_amount_accuracy_percent": 92.0,
    "unsupported_recovery_rate_percent": 0.0,
    "policy_violation_rate_percent": 0.0,
    "human_escalation_rate_percent": 18.0
  }
}
19. Razorpay Webhook
POST /v1/webhooks/razorpay

This endpoint is called by Razorpay.

It is not a frontend API.

The endpoint must:

read the raw request payload,
verify the webhook signature,
validate the event structure,
extract the external event identifier where available,
perform an idempotency check,
identify the associated payment/recovery action,
update payment state,
generate the relevant domain event,
invoke the State Machine,
write an audit event.
Response

For successfully accepted processing:

200 OK

Invalid signatures should be rejected according to the selected Razorpay integration pattern.

The webhook endpoint must never accept a client-provided value that bypasses signature verification.

20. Idempotency

Financial execution endpoints must support idempotency where an operation can create an externally visible effect.

Example:

Idempotency-Key: recover-case-1042-v1

The backend must associate the idempotency key with:

merchant
case
action
result

Repeated identical requests should return the previous result rather than creating a duplicate financial action.

Conflicting reuse of an idempotency key must return:

IDEMPOTENCY_CONFLICT
21. Optimistic / Concurrency Protection

Endpoints that mutate financial state must verify current state immediately before modification.

Example:

Client reads:

collectible = ₹9L

        ↓

Another payment arrives:

₹2L

        ↓

Client executes:

₹9L

The execution endpoint must re-read the current case/payment state.

If the proposal is stale, execution must be re-evaluated.

The client-provided state must never be trusted as the authoritative current state.

Execution must be protected against concurrent duplicate requests and stale authorization.

22. API Error Codes

Initial error codes:

VALIDATION_ERROR
UNAUTHORIZED
FORBIDDEN
RESOURCE_NOT_FOUND
DUPLICATE_RESOURCE
INVALID_STATE_TRANSITION
AI_OUTPUT_INVALID
AI_EXECUTION_FAILED
EVIDENCE_UNAVAILABLE
EVIDENCE_INSUFFICIENT
EVIDENCE_CONFLICT
POLICY_BLOCKED
HUMAN_APPROVAL_REQUIRED
APPROVAL_INVALID
APPROVAL_EXPIRED
APPROVAL_INVALIDATED
LEGAL_LOCK
AUTOMATION_LOCKED
RECOVERY_AMOUNT_INVALID
RECOVERY_AMOUNT_EXCEEDS_COLLECTIBLE
RECOVERY_AMOUNT_EXCEEDS_SAFELY_RECOVERABLE
STALE_PROPOSAL
RAZORPAY_API_ERROR
PAYMENT_NOT_CONFIRMED
WEBHOOK_SIGNATURE_INVALID
DUPLICATE_WEBHOOK
IDEMPOTENCY_CONFLICT
23. API Security Boundaries
Frontend

May:

view data,
request workflow operations,
approve permitted actions,
view audit information.

May not:

directly call Razorpay,
directly call the LLM,
modify financial balances,
directly modify case state,
bypass policy,
bypass human approval,
remove safety/legal locks.
AI Components

May:

analyze,
classify,
extract candidate facts,
recommend.

May not:

execute financial actions,
bypass policy,
bypass state validation,
write arbitrary financial state,
authorize financial execution,
mark payment successful.
Backend

Controls:

domain state,
financial calculations,
policy evaluation,
state transitions,
payment execution,
webhook processing,
authorization,
audit logging.
24. API-to-Component Mapping
API	Primary component
POST /invoices	Invoice Service
GET /invoices/{id}	Invoice Service
POST /recovery-cases	Recovery Case Service
GET /recovery-cases	Recovery Case Service
GET /recovery-cases/{id}	Recovery Case Service
POST /{id}/triage	Triage Agent + Orchestrator
POST /{id}/evidence	Evidence Service + Evidence Agent
POST /{id}/resolve	Resolution Agent + Financial Calculation
POST /{id}/policy-check	Policy Engine
POST /{id}/execute	Recovery Executor
POST /{id}/approvals	Human Approval Service
POST /{id}/escalate	Escalation Service
GET /{id}/audit	Audit Service
GET /dashboard/summary	Analytics/Reporting Service
POST /evaluations	Evaluation Runner
GET /evaluations/{id}	Evaluation Service
POST /webhooks/razorpay	Razorpay Webhook Handler
25. API Execution Boundaries

The following operation is prohibited:

Frontend
   ↓
Razorpay API

The following is required:

Frontend
   ↓
FastAPI
   ↓
Financial Validation
   ↓
Policy Engine
   ↓
State Machine
   ↓
Recovery Executor
   ↓
Razorpay

For human-approved actions:

Frontend
   ↓
Human Approval API
   ↓
Exact Action Authorization
   ↓
Recovery Executor

The frontend never receives or controls Razorpay credentials.

26. Canonical API Flow

For the canonical partial-recovery scenario:

POST /recovery-cases
        ↓
POST /recovery-cases/{id}/triage
        ↓
POST /recovery-cases/{id}/evidence
        ↓
POST /recovery-cases/{id}/resolve
        ↓
POST /recovery-cases/{id}/policy-check
        ↓
HUMAN_APPROVAL_REQUIRED
        ↓
POST /recovery-cases/{id}/approvals
        ↓
HUMAN_APPROVAL_GRANTED
        ↓
POST /recovery-cases/{id}/execute
        ↓
PAYMENT_PENDING
        ↓
Razorpay Webhook
        ↓
Verified PAYMENT_CONFIRMED domain event
        ↓
PARTIALLY_RECOVERED

For an action within autonomous authority:

POST /recovery-cases/{id}/policy-check
        ↓
APPROVED
        ↓
POST /recovery-cases/{id}/execute
        ↓
PAYMENT_PENDING
27. Canonical ₹9L / ₹5L Example

For:

Invoice:
₹10,00,000

Verified disputed amount:
₹1,00,000

Verified collectible amount:
₹9,00,000

Resolution Agent recommendation:
₹9,00,000

Merchant autonomous recovery authority:
₹5,00,000

The API workflow is:

Resolution Agent
      ↓
proposed_amount = ₹9,00,000
      ↓
Financial Validation
      ↓
amount_supported = true
      ↓
Policy Check
      ↓
HUMAN_APPROVAL_REQUIRED
      ↓
Human Approval
      ↓
Exact ₹9,00,000 action authorized
      ↓
Execute API
      ↓
Razorpay payment request
      ↓
PAYMENT_PENDING
      ↓
Verified webhook
      ↓
₹9,00,000 recovered
      ↓
PARTIALLY_RECOVERED

The API must never silently convert:

₹9,00,000 collectible

into:

₹5,00,000 collectible

The ₹5L figure is an autonomous authority limit, not a financial calculation.

28. API-to-State-Machine Boundary

HTTP handlers must not directly mutate:

case.status

Instead:

HTTP Request
    ↓
Application Service
    ↓
Validation
    ↓
Domain Event
    ↓
State Machine
    ↓
State Transition

Example:

POST /execute
      ↓
validate authorization
      ↓
RECOVERY_EXECUTION_REQUESTED
      ↓
State Machine validates transition
      ↓
RECOVERY_INITIATED
      ↓
Recovery Executor

The API layer is therefore not the authority over Recovery Case state.

29. API-to-Financial-Calculation Boundary

The API must never treat client-provided financial values as authoritative.

For example, a client must not be able to submit:

{
  "collectible_amount_minor": 90000000
}

and thereby establish collectible amount.

The authoritative value must come from the Financial Calculation Service.

Before financial execution:

Current Case
      ↓
Financial Calculation Service
      ↓
Verified Financial Assessment
      ↓
Policy Engine
      ↓
Execution
30. API-to-Policy Boundary

The frontend may request policy evaluation.

It may not select:

APPROVED

or:

HUMAN_APPROVAL_REQUIRED

or:

BLOCKED

The Policy Engine determines the decision.

The API only exposes the resulting decision.

31. API-to-Payment Boundary

The API must distinguish:

Payment Request Created

from:

Payment Confirmed

The lifecycle is:

Recovery Action
      ↓
Razorpay Payment Request
      ↓
PAYMENT_PENDING
      ↓
External Payment
      ↓
Webhook
      ↓
Signature Verification
      ↓
Payment Validation
      ↓
Payment Record Update
      ↓
PAYMENT_CONFIRMED
      ↓
State Machine
      ↓
PARTIALLY_RECOVERED / FULLY_RECOVERED

No frontend request may directly mark payment as successful.

32. API Observability

Every material API request should be traceable using:

request_id
merchant_id
user_id where applicable
case_id where applicable
resource_id where applicable
operation
timestamp
result

Sensitive credentials and secrets must never be written to logs.

AI reasoning should be represented through structured outputs, reason codes, evidence references, and decision metadata rather than private chain-of-thought.

33. API Contract Testing

The implementation should include tests covering:

test_cross_merchant_access_is_rejected()

test_invalid_invoice_is_rejected()

test_duplicate_recovery_case_is_rejected()

test_invalid_state_transition_is_rejected()

test_ai_output_schema_is_validated()

test_policy_cannot_be_forced_by_client()

test_human_approval_binds_exact_action()

test_modified_action_invalidates_approval()

test_missing_approval_blocks_execution()

test_amount_is_revalidated_before_execution()

test_amount_cannot_exceed_collectible()

test_amount_cannot_exceed_safely_recoverable()

test_legal_lock_blocks_execution()

test_idempotency_prevents_duplicate_execution()

test_payment_request_does_not_mark_recovered()

test_invalid_webhook_signature_is_rejected()

test_duplicate_webhook_is_idempotent()

test_verified_payment_updates_case()

test_stale_proposal_is_rejected_or_revalidated()
34. API Design Principle

The API is an interface to the controlled recovery workflow, not a mechanism for bypassing it.

The backend must always preserve the sequence:

Interpret
   ↓
Validate
   ↓
Calculate
   ↓
Authorize
   ↓
Transition
   ↓
Execute
   ↓
Verify

The responsibility boundaries are:

AI
    ↓
Interpret / Recommend

Financial Calculation
    ↓
Financial Truth

Policy Engine
    ↓
Permission

State Machine
    ↓
Workflow Validity

Recovery Executor
    ↓
External Execution

Webhook / Payment Layer
    ↓
External Truth

Financial endpoints must fail closed when required information, policy authorization, state validity, human approval, or payment verification is missing.

The API must never provide a shortcut around these controls.
