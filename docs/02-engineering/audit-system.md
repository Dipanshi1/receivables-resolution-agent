# Audit System

## 1. Purpose

The Audit System provides a traceable, append-oriented history of material decisions, actions, financial events, state transitions, and escalations associated with a Recovery Case.

The audit trail exists to provide:

- financial accountability,
- operational traceability,
- debugging capability,
- policy explainability,
- human-review context,
- benchmark analysis, and
- confidence that autonomous actions were bounded.

The audit trail must allow an operator to reconstruct the lifecycle of a recovery case without relying on private LLM reasoning.

---

# 2. Core Audit Principle

> **Every material financial decision must be traceable from evidence to recommendation to policy decision to execution to verified outcome.**

The canonical chain is:

```text
Business Evidence
      ↓
AI Interpretation
      ↓
Financial Assessment
      ↓
Resolution Proposal
      ↓
Policy Decision
      ↓
State Transition
      ↓
Recovery Action
      ↓
External Payment Event
      ↓
Verified Payment
      ↓
Recovery Outcome
3. What the Audit System Records

The system records material events involving:

Recovery Cases,
AI reasoning,
evidence,
financial calculations,
policy decisions,
state transitions,
human approvals,
recovery actions,
Razorpay interactions,
webhook events,
payment confirmation,
escalations,
stopping rules,
execution failures,
case closure.

Not every technical log entry is an audit event.

Audit events represent meaningful business or financial events.

4. Audit Event Structure

Each Audit Event should contain at minimum:

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

Where applicable, the event may additionally contain:

invoice_id
recovery_action_id
payment_id
proposal_id
evidence_ids
request_id
5. Audit Event Categories

Events are grouped into:

CASE
AI
EVIDENCE
FINANCIAL
POLICY
STATE
RECOVERY
PAYMENT
ESCALATION
SAFETY
HUMAN
SYSTEM

This categorization supports filtering and analysis.

6. Case Events

Initial case events include:

RECOVERY_CASE_CREATED
RECOVERY_CASE_UPDATED
CASE_CLOSED

Example:

{
  "event_type": "RECOVERY_CASE_CREATED",
  "actor_type": "SYSTEM",
  "case_id": "CASE-1042",
  "state_after": "OVERDUE"
}
7. AI Events

AI-related events may include:

TRIAGE_STARTED
TRIAGE_COMPLETED
EVIDENCE_ANALYSIS_STARTED
EVIDENCE_ANALYSIS_COMPLETED
RESOLUTION_ANALYSIS_STARTED
RESOLUTION_PROPOSED
AI_OUTPUT_REJECTED
AI_RETRY
AI_FAILURE

AI events should record structured execution metadata, not private chain-of-thought.

8. AI Audit Information

A useful AI event may contain:

agent_type
model_name
prompt_version
agent_run_id
input_hash
confidence
output_summary
evidence_ids

Example:

{
  "event_type": "TRIAGE_COMPLETED",
  "actor_type": "AI_AGENT",
  "actor_id": "TRIAGE",
  "payload": {
    "agent_run_id": "RUN-001",
    "issue_type": "QUANTITY_DISPUTE",
    "confidence": 0.96,
    "risk_flags": [],
    "evidence_ids": ["E-001"]
  }
}

The system should expose enough information to explain the result without exposing private model deliberation.

9. Evidence Events

Evidence events include:

EVIDENCE_RETRIEVED
EVIDENCE_NORMALIZED
EVIDENCE_RELEVANT
EVIDENCE_CONFLICT_DETECTED
EVIDENCE_INSUFFICIENT
EVIDENCE_VERIFIED

Example:

{
  "event_type": "EVIDENCE_CONFLICT_DETECTED",
  "actor_type": "EVIDENCE_SERVICE",
  "payload": {
    "field": "quantity_delivered",
    "values": [
      {
        "value": 90,
        "evidence_id": "E-001"
      },
      {
        "value": 80,
        "evidence_id": "E-002"
      }
    ]
  }
}
10. Evidence Provenance

Material conclusions should contain evidence references.

For example:

Finding:
quantity_delivered = 90

Supported by:
GRN-1194

The audit trail should allow the operator to navigate from:

Financial conclusion
        ↓
Evidence IDs
        ↓
Source records

The system should not require an operator to trust an unsupported AI statement.

11. Financial Calculation Events

Financial calculation events may include:

CLAIMED_AMOUNT_RECORDED
DISPUTED_AMOUNT_VERIFIED
COLLECTIBLE_AMOUNT_CALCULATED
RECOVERABLE_AMOUNT_CALCULATED
BALANCE_UPDATED

Example:

{
  "event_type": "COLLECTIBLE_AMOUNT_CALCULATED",
  "actor_type": "FINANCIAL_CALCULATION_SERVICE",
  "payload": {
    "invoice_amount_minor": 100000000,
    "verified_disputed_amount_minor": 10000000,
    "collectible_amount_minor": 90000000,
    "calculation_version": "v1.0",
    "evidence_ids": ["E-001", "E-002"]
  }
}

The calculation version should be stored so that calculation behavior can be reconstructed if business logic changes.

12. Financial Audit Principle

The audit system must distinguish:

Customer Claim
        ↓
Verified Dispute
        ↓
Collectible Assessment
        ↓
Approved Recovery
        ↓
Actual Payment

These must not be represented as one ambiguous "amount" field.

13. Policy Events

Policy events include:

POLICY_EVALUATION_STARTED
POLICY_CHECKED
POLICY_APPROVED
POLICY_DEFERRED
POLICY_BLOCKED
HUMAN_APPROVAL_REQUIRED
POLICY_STOPPED

Example:

{
  "event_type": "POLICY_CHECKED",
  "actor_type": "POLICY_ENGINE",
  "payload": {
    "decision": "APPROVED",
    "policy_version": "v1.0",
    "checks": {
      "evidence_sufficient": true,
      "amount_supported": true,
      "auto_recovery_limit_ok": true,
      "legal_lock": false,
      "touchpoint_limit_ok": true
    }
  }
}
14. Policy Explainability

A policy audit record must make it possible to answer:

Why was this action allowed?

or:

Why was this action blocked?

The record should therefore retain:

policy_version
decision
individual checks
blocking/defer reason
proposal reference
timestamp
15. State Transition Events

Every successful state transition should generate an audit event containing:

state_before
state_after
event_type
actor
timestamp

Example:

{
  "event_type": "STATE_TRANSITION",
  "state_before": "POLICY_REVIEW",
  "state_after": "RECOVERY_INITIATED",
  "actor_type": "STATE_MACHINE",
  "payload": {
    "trigger": "POLICY_APPROVED"
  }
}
16. Recovery Events

Recovery-related events include:

RECOVERY_ACTION_CREATED
RECOVERY_INITIATED
PAYMENT_LINK_CREATE_REQUESTED
PAYMENT_LINK_CREATED
PAYMENT_LINK_CREATION_FAILED
RECOVERY_RETRY

A recovery event should reference:

case_id
recovery_action_id
proposal_id
policy_decision_id
external_reference where applicable
17. Payment Events

Payment events include:

PAYMENT_REQUEST_CREATED
PAYMENT_EVENT_RECEIVED
PAYMENT_PARTIALLY_CONFIRMED
PAYMENT_CONFIRMED
PAYMENT_FAILED
PAYMENT_RECONCILIATION_FAILED

Where Razorpay events are involved, the audit event should retain the relevant provider references.

18. Webhook Events

Webhook-specific events include:

WEBHOOK_RECEIVED
WEBHOOK_SIGNATURE_VERIFIED
WEBHOOK_SIGNATURE_REJECTED
WEBHOOK_DUPLICATE_DETECTED
WEBHOOK_RESOURCE_UNMAPPED

These events are useful for operational debugging and payment tracing.

19. Safety Events

Safety-related events include:

LEGAL_RISK_DETECTED
LEGAL_LOCK_APPLIED
AUTOMATION_LOCKED
OUTREACH_STOPPED
TOUCHPOINT_LIMIT_REACHED
FINANCIAL_LIMIT_REACHED
EVIDENCE_SAFETY_BLOCK

These events must clearly state:

what safety condition occurred,
which action was prevented,
what state the case entered,
what escalation was initiated.
20. Human Events

Human workflow events include:

HUMAN_APPROVAL_REQUESTED
HUMAN_APPROVAL_GRANTED
HUMAN_APPROVAL_REJECTED
HUMAN_REVIEW_STARTED
HUMAN_REVIEW_COMPLETED
HUMAN_ESCALATION_CREATED

Example:

{
  "event_type": "HUMAN_APPROVAL_GRANTED",
  "actor_type": "HUMAN",
  "actor_id": "USER-12",
  "payload": {
    "proposal_id": "PROP-001",
    "approved_amount_minor": 90000000
  }
}
21. Execution Failure Events

Execution failures should be visible in the audit trail.

Examples:

EXECUTION_FAILED
RAZORPAY_API_ERROR
PAYMENT_REQUEST_TIMEOUT
RETRY_STARTED
RETRY_EXHAUSTED

The event should retain:

error category
retryable/non-retryable status
external reference where available
request/correlation ID
timestamp

Secrets must never be recorded.

22. Immutability

Audit Events are append-oriented.

Once a material audit event has been recorded, the event itself should not be modified as part of normal business operations.

If a correction is necessary, create a new corrective event rather than silently editing the original history.

Example:

ORIGINAL_EVENT
      ↓
CORRECTION_EVENT
      ↓
AUDIT_TRAIL

This preserves historical integrity.

23. Audit Ordering

Each event contains a timestamp.

Where multiple events occur closely together, the system should also use a monotonically increasing identifier or another deterministic ordering mechanism where necessary.

Ordering should not depend solely on timestamps with coarse precision.

24. Correlation and Trace IDs

Material operations should be traceable across the system using identifiers such as:

request_id
case_id
agent_run_id
proposal_id
recovery_action_id
payment_id
external_event_id

This allows an operator or engineer to move from an API request to the exact recovery outcome.

25. Audit Access

The frontend exposes a case-level audit view.

Endpoint:

GET /v1/recovery-cases/{case_id}/audit

The UI should display events chronologically.

The user should be able to filter by:

All
AI
Evidence
Policy
Recovery
Payment
Safety
Human
System
26. Audit Timeline UI

Example:

10:32:01
Invoice became overdue
SYSTEM

10:32:04
Quantity dispute detected
AI AGENT

10:32:11
GRN verified: 90 units delivered
EVIDENCE

10:32:14
Collectible amount: ₹9,00,000
CALCULATION

10:32:16
Policy approved recovery
POLICY ENGINE

10:32:17
Razorpay Payment Link created
RECOVERY EXECUTOR

10:41:32
Payment confirmed
RAZORPAY WEBHOOK

10:41:33
₹9,00,000 recovered
SYSTEM

This timeline should be understandable to a finance user without requiring technical knowledge.

27. Audit Drill-Down

Selecting an audit event may expose structured details.

Example:

COLLECTIBLE_AMOUNT_CALCULATED

Invoice:
₹10,00,000

Verified disputed amount:
₹1,00,000

Collectible amount:
₹9,00,000

Supporting evidence:
PO-7721
GRN-1194

Calculation version:
v1.0

This is more useful than displaying an opaque model-generated explanation.

28. "Why Was This Recovered?" View

For an executed recovery, the UI should allow the user to reconstruct:

1. Original invoice amount
2. Customer claim
3. Verified dispute
4. Evidence supporting the dispute
5. Collectible amount
6. AI resolution proposal
7. Policy decision
8. Human approval if applicable
9. Recovery action
10. Payment confirmation
11. Remaining balance

This is the primary auditability experience.

29. "Why Was This Blocked?" View

For a blocked action, show:

Proposed action:
CREATE_PARTIAL_RECOVERY

Proposed amount:
₹9,00,000

Decision:
BLOCKED

Reason:
EVIDENCE_CONFLICT

Conflicting evidence:
GRN → 90 units
Customer email → 80 units

Next step:
Human review

This helps demonstrate safe failure rather than hiding it.

30. No Private Chain-of-Thought

The audit trail must not attempt to expose private model chain-of-thought.

Instead, store:

structured outputs,
confidence,
evidence references,
concise reason summaries,
policy results,
execution results,
state transitions.

This provides operational explainability without depending on private model reasoning.

31. Sensitive Data Handling

Audit records should avoid unnecessary storage of:

passwords,
API keys,
webhook secrets,
authentication tokens,
full payment secrets,
unnecessary personal information.

Where customer communications are stored, access should follow the application's authorization model.

32. Audit Retention

The MVP should retain audit history for the lifetime of the Recovery Case.

The exact regulatory/enterprise retention period is outside MVP scope.

Retention policies may be configurable in a future production implementation.

33. Audit Query Performance

The primary query pattern is:

all events for one Recovery Case ordered by time

Therefore the database should maintain an index equivalent to:

(case_id, created_at)

The API should support pagination for large histories.

34. Audit Consistency

Material financial updates and their associated audit events should be committed transactionally where practical.

Example:

Payment confirmed
+
Payment record updated
+
Recovery state updated
+
Audit event created

These operations should not leave the database in a state where the payment is recorded but its corresponding financial transition is silently absent.

35. Audit Event Idempotency

External events such as Razorpay webhooks may generate audit records.

Duplicate webhook deliveries must not generate duplicate financial effects.

Where appropriate, external event identifiers should be associated with audit processing so that replayed events can be recognized.

36. Audit and Benchmarking

The evaluation system should be able to inspect audit events to determine:

whether required policy checks occurred,
whether a legal stop was respected,
whether an unsupported action was attempted,
whether payment confirmation came from a verified event,
whether state transitions were valid.

This enables safety metrics to be derived from actual system behavior.

37. Required Audit Trace for Golden Scenario

For the canonical partial-recovery scenario, the audit trail should contain enough information to reconstruct:

Invoice overdue
      ↓
Quantity dispute detected
      ↓
Relevant evidence retrieved
      ↓
Dispute verified
      ↓
Collectible amount calculated
      ↓
Partial recovery proposed
      ↓
Policy approved
      ↓
Recovery action created
      ↓
Razorpay Payment Link created
      ↓
Payment webhook received
      ↓
Webhook verified
      ↓
Payment confirmed
      ↓
₹9,00,000 recovered
      ↓
₹1,00,000 remains disputed
38. Required Audit Trace for Legal Stop

For a legal-risk case:

Customer legal-risk signal received
      ↓
Legal risk detected
      ↓
Automation lock applied
      ↓
Automated outreach stopped
      ↓
Automated recovery stopped
      ↓
Legal escalation created

The audit trail should demonstrate that no prohibited financial action was executed after the lock.

39. Required Audit Trace for Conflicting Evidence

For an ambiguous case:

Customer claim received
      ↓
Evidence retrieved
      ↓
Conflicting quantities detected
      ↓
Collectible amount not established
      ↓
Automatic recovery blocked
      ↓
Human review requested

The audit trail should preserve both sides of the evidence conflict.

40. Audit Service Interface

Conceptual interface:

record_event(
    case_id,
    event_type,
    actor_type,
    payload,
    state_before=None,
    state_after=None,
    policy_version=None,
    external_event_id=None,
)

The Audit Service should normalize event creation so that important metadata is recorded consistently.

41. Audit Event Taxonomy

The initial event taxonomy is:

CASE
AI
EVIDENCE
FINANCIAL
POLICY
STATE
RECOVERY
PAYMENT
ESCALATION
SAFETY
HUMAN
SYSTEM

The taxonomy may be expanded only when a new event cannot be represented meaningfully by an existing category.

42. Audit Design Principle

The audit trail is not a transcript of everything the application does.

It is a structured record of the decisions and events necessary to reconstruct the financial workflow.

The desired question it should answer is:

What happened, why was it allowed, what money moved, and what evidence proves the outcome?

43. Audit Summary

The complete traceability chain is:

Evidence
   ↓
AI Result
   ↓
Financial Assessment
   ↓
Resolution Proposal
   ↓
Policy Decision
   ↓
State Transition
   ↓
Recovery Action
   ↓
Razorpay Event
   ↓
Verified Payment
   ↓
Recovery Outcome

Every material financial action must be reconstructable from this chain.