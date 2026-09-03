# Recovery Case State Machine

## 1. Purpose

This document defines the deterministic state machine governing the lifecycle of a Receivables Resolution Agent Recovery Case.

The State Machine controls:

- valid Recovery Case states,
- allowed transitions,
- transition triggers,
- transition conditions,
- exceptional paths,
- terminal states,
- safety interrupts, and
- recovery/payment state changes.

The State Machine is deterministic.

An LLM cannot directly change Recovery Case state.

---

# 2. Core Principle

The State Machine enforces:

> **A Recovery Case can only move from one valid state to another through an explicitly defined domain event satisfying the required transition conditions.**

The system must reject invalid transitions.

Example:

```text
INVALID

OVERDUE
   ↓
FULLY_RECOVERED

A case cannot become fully recovered without the required recovery and payment events.

3. State Categories

The states are grouped into five categories.

3.1 Active Investigation
OVERDUE
TRIAGING
ISSUE_IDENTIFIED
EVIDENCE_ANALYSIS
RESOLUTION_READY
3.2 Controlled Execution
POLICY_REVIEW
RECOVERY_INITIATED
PAYMENT_PENDING
3.3 Recovery Outcomes
PARTIALLY_RECOVERED
FULLY_RECOVERED
3.4 Human / Safety Handling
HUMAN_REVIEW
LEGAL_ESCALATION
AUTOMATION_LOCKED
3.5 Failure / Closure
EXECUTION_FAILED
CLOSED
4. State Definitions
4.1 OVERDUE
Meaning

The invoice has reached a configured recovery trigger and remains unpaid or insufficiently paid.

Entry

A valid recovery trigger is detected.

Allowed exits
TRIAGING
LEGAL_ESCALATION
AUTOMATION_LOCKED
5. TRIAGING
Meaning

The system is determining why the receivable is at risk.

Entry event
START_TRIAGE
Requirements
case exists,
case is not locked,
invoice is eligible for recovery processing.
Allowed exits
ISSUE_IDENTIFIED
HUMAN_REVIEW
LEGAL_ESCALATION
Notes

The Triage Agent may classify the issue.

The Triage Agent cannot directly authorize recovery.

6. ISSUE_IDENTIFIED
Meaning

A likely cause of non-payment has been identified.

Examples
PAYMENT_FAILURE
QUANTITY_DISPUTE
PRICE_DISPUTE
PO_MISMATCH
GST_DOCUMENTATION
MILESTONE_PENDING
SERVICE_DELIVERY_DISPUTE
CREDIT_NOTE_REQUEST
PROMISE_TO_PAY
UNKNOWN
Entry event
TRIAGE_COMPLETED
Allowed exits
EVIDENCE_ANALYSIS
LEGAL_ESCALATION
HUMAN_REVIEW
7. EVIDENCE_ANALYSIS
Meaning

The system is examining relevant evidence to determine whether the identified issue is supported.

Entry event
START_EVIDENCE_ANALYSIS
Allowed exits
RESOLUTION_READY
HUMAN_REVIEW
LEGAL_ESCALATION
AUTOMATION_LOCKED
Evidence outcomes
SUPPORTED
PARTIALLY_SUPPORTED
UNSUPPORTED
CONFLICTING
INSUFFICIENT_EVIDENCE
Transition rules

If evidence is sufficient and supports a valid resolution:

EVIDENCE_SUFFICIENT
        ↓
RESOLUTION_READY

If material evidence conflicts:

EVIDENCE_CONFLICT
        ↓
HUMAN_REVIEW

If evidence is insufficient to determine a safe recovery decision:

EVIDENCE_INSUFFICIENT
        ↓
HUMAN_REVIEW

If a legal/high-risk condition is detected:

LEGAL_RISK_DETECTED
        ↓
AUTOMATION_LOCKED
        ↓
LEGAL_ESCALATION
8. RESOLUTION_READY
Meaning

The system has enough information to produce a structured resolution proposal.

Requirements

At minimum:

issue identified,
relevant evidence assessed,
financial facts established where needed,
collectible amount calculated where applicable,
unresolved ambiguity below the threshold for human escalation.
Allowed exits
POLICY_REVIEW
HUMAN_REVIEW
LEGAL_ESCALATION
9. POLICY_REVIEW
Meaning

A Resolution Proposal is being evaluated against merchant policy and current case conditions.

Entry event
SUBMIT_RESOLUTION_FOR_POLICY
Inputs
Resolution Proposal,
Recovery Case,
merchant policy,
verified evidence,
current time,
recovery history.
Possible policy outcomes
APPROVED
DEFERRED
HUMAN_APPROVAL_REQUIRED
BLOCKED
STOPPED

These are Policy Decision outcomes, not Recovery Case states.

Transitions
Approved without additional human authorization
POLICY_APPROVED
      ↓
RECOVERY_INITIATED

This is allowed only when all applicable autonomous execution limits and safety conditions are satisfied.

Human approval required
HUMAN_APPROVAL_REQUIRED
      ↓
HUMAN_REVIEW
      ↓
HUMAN_APPROVAL_GRANTED
      ↓
RECOVERY_INITIATED

The case remains under controlled workflow until the required human approval is granted.

Human approval must authorize the exact recovery action and amount.

Deferred
POLICY_DEFERRED
      ↓
RESOLUTION_READY
Blocked
POLICY_BLOCKED
      ↓
HUMAN_REVIEW
Stopped
POLICY_STOPPED
      ↓
AUTOMATION_LOCKED
Important distinction

The Policy Engine determines whether a financially supported amount may be executed automatically.

For example:

Verified collectible amount:
₹9,00,000

Merchant autonomous recovery authority:
₹5,00,000

Policy result:
HUMAN_APPROVAL_REQUIRED

The Policy Engine does not reduce the underlying collectible amount merely because autonomous authority is lower.

Human approval authorizes the exact recovery action; it does not modify the underlying collectible amount.

10. RECOVERY_INITIATED
Meaning

A valid recovery action has been authorized and is being executed.

Requirements

All applicable conditions must be true:

Policy decision is APPROVED, or
required human approval has been granted,
State Machine transition is valid,
financial amount is valid,
legal lock is false,
required human approval is satisfied,
action authorization is valid and current.
Typical action

Creation of a Razorpay payment request.

Allowed exits
PAYMENT_PENDING
EXECUTION_FAILED
11. PAYMENT_PENDING
Meaning

A payment request has been created, but successful payment has not yet been verified.

Entry event
PAYMENT_REQUEST_CREATED
Critical rule

The system must not treat this state as recovered.

Creating a payment link or payment request is not equivalent to receiving payment.

Allowed exits
PARTIALLY_RECOVERED
FULLY_RECOVERED
EXECUTION_FAILED
LEGAL_ESCALATION
Payment success condition

A verified external payment event must establish the actual payment amount.

The State Machine must consume payment truth from the verified payment/webhook layer.

12. PARTIALLY_RECOVERED
Meaning

At least one verified payment has been received, but the original receivable still contains an unresolved balance.

Example
Invoice:
₹10,00,000

Recovered:
₹9,00,000

Remaining disputed:
₹1,00,000
Entry condition
verified_recovered_amount > 0

and:

verified_recovered_amount < applicable_recoverable_balance

The unresolved balance may be a disputed amount, remaining collectible amount, or another valid financial balance according to the application's financial model.

Allowed exits
RESOLUTION_READY
RECOVERY_INITIATED
FULLY_RECOVERED
HUMAN_REVIEW
CLOSED

The exact next state depends on what remains unresolved.

Important distinction

PARTIALLY_RECOVERED is a Recovery Case business state.

It must not be confused with a provider-level partial-payment event.

A provider may report a partial payment, but the application determines the Recovery Case state after reconciling the verified payment against the current financial assessment.

13. FULLY_RECOVERED
Meaning

The receivable has been fully recovered according to the application's financial model.

Entry condition

The verified recovered amount satisfies the receivable's applicable recoverable balance.

Critical requirement

The transition must be based on verified payment data rather than:

AI output,
payment-link creation,
customer intention, or
an unverified callback.
Allowed exits
CLOSED
14. HUMAN_REVIEW
Meaning

Autonomous processing cannot safely continue and a human decision is required.

Entry causes

Examples:

INSUFFICIENT_EVIDENCE
EVIDENCE_CONFLICT
POLICY_BLOCK
HIGH_VALUE_ACTION
CONCESSION_EXCEPTION
UNSUPPORTED_AUTOMATION
EXECUTION_RETRY_EXHAUSTED
HUMAN_APPROVAL_REQUIRED
OTHER_REVIEW_REQUIRED
Possible exits
RESOLUTION_READY
POLICY_REVIEW
RECOVERY_INITIATED
CLOSED
LEGAL_ESCALATION
Human approval rule

When HUMAN_APPROVAL_REQUIRED caused entry into HUMAN_REVIEW, the case may proceed to RECOVERY_INITIATED only after a valid approval exists for the exact recovery action.

Approval must bind to:

Recovery Case,
Recovery Action,
action amount,
relevant proposal/material parameters,
action fingerprint.

Any material change to the action or amount invalidates the previous approval and requires re-authorization.

The exact transition depends on the human decision and the new case conditions.

15. LEGAL_ESCALATION
Meaning

The case contains a condition that requires specialized legal/human handling.

Entry causes

Examples:

LEGAL_RISK_DETECTED
CUSTOMER_REQUESTS_LEGAL_CHANNEL
FRAUD_ALLEGATION
COURT_OR_LEGAL_NOTICE
POLICY_DEFINED_LEGAL_TRIGGER
Required behavior

When a case enters legal escalation:

AUTOMATED_RECOVERY = DISABLED
AUTOMATED_OUTREACH = DISABLED
Allowed exit
CLOSED

or another explicitly authorized human-controlled transition.

The AI cannot independently remove the legal escalation.

16. AUTOMATION_LOCKED
Meaning

Autonomous execution is disabled for the case.

Typical causes
LEGAL_RISK
SAFETY_VIOLATION
SYSTEM_INTEGRITY_FAILURE
MANUAL_LOCK
Behavior

The system may:

retain data,
record audit events,
prepare information for human review.

It may not:

execute recovery,
send prohibited outreach,
grant concessions,
bypass policy.
Exit

Only a controlled system or human workflow may release a lock.

For legal cases, the lock normally remains until explicit human/legal handling.

17. EXECUTION_FAILED
Meaning

An approved recovery action could not be executed successfully.

Examples
Razorpay API unavailable
provider timeout
temporary network failure
execution dependency unavailable
Entry
EXECUTION_ERROR
Possible exits
RECOVERY_INITIATED
HUMAN_REVIEW
CLOSED
Retry rule

A retry is allowed only if merchant/system retry policy permits it.

Retries must be bounded.

A retry must revalidate current financial state, policy authorization, approval validity, and state eligibility before execution.

18. CLOSED
Meaning

No further autonomous workflow is required for the case.

Possible reasons
FULLY_RECOVERED
HUMAN_RESOLUTION_COMPLETED
LEGAL_PROCESS_COMPLETED
RECOVERY_ABANDONED_BY_AUTHORIZED_USER
Principle

Closed is a terminal operational state for the current Recovery Case.

Historical audit data remains available.

19. Canonical Happy Path

The standard autonomous full-recovery path is:

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
RECOVERY_INITIATED
   ↓
PAYMENT_PENDING
   ↓
FULLY_RECOVERED
   ↓
CLOSED

FULLY_RECOVERED requires verified payment evidence.

20. Canonical Partial-Recovery Path

For a ₹10,00,000 invoice with ₹1,00,000 verified dispute:

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
HUMAN_REVIEW
   ↓
RECOVERY_INITIATED
   ↓
PAYMENT_PENDING
   ↓
PARTIALLY_RECOVERED
Financial state
Invoice amount:        ₹10,00,000
Verified disputed:     ₹1,00,000
Verified collectible:  ₹9,00,000
Recovered:             ₹9,00,000
Remaining dispute:     ₹1,00,000
Authorization logic

The Financial Calculation Service establishes:

Verified collectible:
₹9,00,000

The Policy Engine evaluates:

Autonomous authority:
₹5,00,000

Therefore:

HUMAN_APPROVAL_REQUIRED

The human approval authorizes the exact ₹9,00,000 recovery action.

The collectible amount remains ₹9,00,000.

The remaining ₹1,00,000 remains associated with the unresolved disputed portion.

The remaining balance may subsequently be resolved or escalated.

21. Insufficient-Evidence Path
OVERDUE
   ↓
TRIAGING
   ↓
ISSUE_IDENTIFIED
   ↓
EVIDENCE_ANALYSIS
   ↓
EVIDENCE_INSUFFICIENT
   ↓
HUMAN_REVIEW

No automatic financial execution may occur from the insufficient-evidence condition.

22. Conflicting-Evidence Path
OVERDUE
   ↓
TRIAGING
   ↓
ISSUE_IDENTIFIED
   ↓
EVIDENCE_ANALYSIS
   ↓
EVIDENCE_CONFLICT
   ↓
HUMAN_REVIEW

The system must preserve the conflicting evidence sources.

It must not silently select one conflicting source merely to continue automation.

23. Legal-Safety Path
ACTIVE CASE
     ↓
LEGAL_RISK_DETECTED
     ↓
AUTOMATION_LOCKED
     ↓
LEGAL_ESCALATION
     ↓
HUMAN / LEGAL HANDLING
     ↓
CLOSED

Legal/safety transitions have priority over ordinary recovery transitions.

24. Policy-Approval Path
Autonomous approval
RESOLUTION_READY
      ↓
POLICY_REVIEW
      ↓
POLICY_APPROVED
      ↓
RECOVERY_INITIATED
Human approval
RESOLUTION_READY
      ↓
POLICY_REVIEW
      ↓
HUMAN_APPROVAL_REQUIRED
      ↓
HUMAN_REVIEW
      ↓
HUMAN_APPROVAL_GRANTED
      ↓
RECOVERY_INITIATED

Approval must apply to the exact proposal and recovery action amount.

HUMAN_APPROVAL_REQUIRED is a policy outcome/event, not a Recovery Case state.

HUMAN_APPROVAL_GRANTED is a domain event indicating that the required authorization has been satisfied.

25. Execution-Failure Path
RECOVERY_INITIATED
      ↓
EXECUTION_FAILED
      │
      ├── RETRY_ALLOWED
      │       ↓
      │  RECOVERY_INITIATED
      │
      └── RETRY_EXHAUSTED
              ↓
          HUMAN_REVIEW

No execution failure may create a successful recovery state.

26. Global Safety Interrupts

The following events may interrupt the normal workflow.

Legal Risk
ANY_ACTIVE_STATE
      ↓
LEGAL_RISK_DETECTED
      ↓
AUTOMATION_LOCKED
Manual Lock
ANY_ACTIVE_STATE
      ↓
MANUAL_LOCK
      ↓
AUTOMATION_LOCKED
System Integrity Failure
ANY_FINANCIAL_EXECUTION_STATE
      ↓
SYSTEM_INTEGRITY_FAILURE
      ↓
AUTOMATION_LOCKED

These interrupts must be implemented independently of LLM recommendations.

Safety interrupts take precedence over ordinary workflow progression.

27. Invalid Transitions

Examples of prohibited transitions:

OVERDUE → FULLY_RECOVERED

TRIAGING → PAYMENT_PENDING

EVIDENCE_ANALYSIS → PAYMENT_CONFIRMED

LEGAL_ESCALATION → RECOVERY_INITIATED

AUTOMATION_LOCKED → PAYMENT_PENDING

The following is also prohibited:

PAYMENT_PENDING → FULLY_RECOVERED

without verified payment evidence.

The system must reject these transitions.

28. State Transition Event Model

Each transition should be caused by a domain event.

Examples:

INVOICE_OVERDUE
START_TRIAGE
TRIAGE_COMPLETED
START_EVIDENCE_ANALYSIS
EVIDENCE_SUFFICIENT
EVIDENCE_INSUFFICIENT
EVIDENCE_CONFLICT
RESOLUTION_PROPOSED
POLICY_APPROVED
POLICY_DEFERRED
POLICY_BLOCKED
HUMAN_APPROVAL_GRANTED
PAYMENT_REQUEST_CREATED
PAYMENT_CONFIRMED
PAYMENT_FAILED
EXECUTION_ERROR
LEGAL_RISK_DETECTED
MANUAL_LOCK
REVIEW_COMPLETED
CASE_CLOSED

The event determines which state transition is requested.

The State Machine validates whether that transition is allowed.

29. Transition Guard Model

A transition should conceptually follow:

Current State
      +
Domain Event
      +
Transition Guards
      ↓
Next State

Example:

Current:
POLICY_REVIEW

Event:
POLICY_APPROVED

Guards:

- proposal valid
- amount valid
- evidence sufficient
- no legal lock
- required approval satisfied
- financial assessment current
- recovery action authorized

Result:

RECOVERY_INITIATED

If any mandatory guard fails, the transition must be rejected.

30. State Machine Must Be Deterministic

For identical:

current state
+
event
+
case snapshot
+
policy snapshot

the State Machine must produce the same result.

It must not call the LLM to decide which state comes next.

31. State and Financial Data Separation

The State Machine controls operational state.

Financial calculations come from deterministic financial services.

The State Machine should not independently calculate:

disputed amount
collectible amount
payment amount
recovered amount

It consumes validated financial facts.

Financial truth is established by the Financial Calculation Service.

32. State and Payment Separation

Payment state is external-provider-derived.

The State Machine may receive:

PAYMENT_CONFIRMED

only after the webhook/payment layer has verified the underlying event.

Therefore:

Razorpay event
      ↓
Webhook verification
      ↓
Payment state update
      ↓
Domain event
      ↓
State transition

A payment-link creation event must never be treated as payment confirmation.

33. Idempotent Events

External events may be delivered more than once.

An event must have a unique identifier where available.

Processing:

Event ID
   ↓
Already processed?
   │
   ├── YES → no state change
   │
   └── NO  → process once

Repeated events must not produce duplicate state transitions or duplicate financial effects.

34. Concurrency Protection

Two simultaneous operations must not produce an invalid financial state.

Examples:

Two recovery actions
Two webhook deliveries
Human approval + automated action
Two simultaneous state transitions

The implementation must use appropriate transaction/locking mechanisms.

At minimum:

current state must be checked before transition,
updates must be atomic,
stale state must not silently overwrite newer state,
execution authorization must be revalidated immediately before external execution.
35. State Transition Audit

Every successful state transition must generate an AuditEvent containing:

case_id
event_type
state_before
state_after
actor
timestamp
policy_version when applicable
relevant references

Rejected transitions should also be observable through appropriate audit/error events.

Audit events are append-only and historical audit data must remain immutable.

36. State Machine Invariants

The following must always hold.

Invariant 1

A case cannot enter a successful recovery state without verified payment evidence.

Invariant 2

A legal-locked case cannot enter an autonomous recovery state.

Invariant 3

An invalid, expired, rejected, or invalidated human approval cannot authorize execution.

Invariant 4

A recovery action cannot execute from an invalid state.

Invariant 5

A blocked policy decision cannot directly create an executable recovery action.

Invariant 6

A failed payment cannot cause a successful recovery transition.

Invariant 7

A case cannot skip mandatory evidence/policy states for an action that requires them.

Invariant 8

Duplicate external events cannot create duplicate state effects.

Invariant 9

State transitions must not alter financial amounts without going through the appropriate deterministic financial service.

Invariant 10

Historical audit events remain immutable.

Invariant 11

A recovery action cannot execute using a stale financial assessment.

Invariant 12

A recovery action cannot execute unless its required authorization remains valid for the exact action being executed.

37. Transition Priority

When multiple events are available, safety takes precedence over ordinary recovery actions.

Priority should generally be:

1. Legal / safety lock
2. System integrity failure
3. Payment truth
4. Human approval / rejection
5. Policy decision
6. Evidence result
7. AI recommendation
8. Ordinary workflow progression

The exact event-priority implementation may be refined during development.

The AI recommendation is always lower priority than deterministic safety, financial, policy, payment, and state controls.

38. State Machine API Contract

The application should expose an internal operation conceptually equivalent to:

transition(
    case,
    event,
    context
) -> TransitionResult

The result should contain:

allowed
state_before
state_after
reason
event_id

Example:

{
  "allowed": true,
  "state_before": "POLICY_REVIEW",
  "state_after": "RECOVERY_INITIATED",
  "reason": "Policy approved and all execution guards passed",
  "event_id": "EVT-1042-91"
}

Example rejection:

{
  "allowed": false,
  "state_before": "AUTOMATION_LOCKED",
  "state_after": "AUTOMATION_LOCKED",
  "reason": "Case is automation locked by legal-risk policy",
  "event_id": "EVT-1042-92"
}

The transition operation must not perform external payment execution itself.

It only validates and applies the domain state transition.

39. State Machine Testing Requirements

The implementation must include tests for:

valid happy-path transitions,
invalid state transitions,
legal lock,
manual lock,
insufficient evidence,
conflicting evidence,
policy blocking,
autonomous policy approval,
human approval,
invalid human approval,
expired human approval,
payment confirmation,
payment failure,
execution retry,
stale financial assessment,
duplicate events,
concurrent/stale transitions,
terminal states.

Examples:

test_overdue_to_triaging()

test_cannot_skip_evidence()

test_legal_lock_blocks_recovery()

test_payment_requires_verified_event()

test_duplicate_webhook_is_idempotent()

test_blocked_policy_cannot_execute()

test_human_approval_required_for_high_value_recovery()

test_invalid_human_approval_cannot_execute()

test_stale_assessment_blocks_execution()

test_invalid_transition_is_rejected()

test_fully_recovered_is_terminal()
40. State Machine Summary

The normal workflow is:

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
      ├── POLICY_APPROVED
      │       ↓
      │  RECOVERY_INITIATED
      │
      └── HUMAN_APPROVAL_REQUIRED
              ↓
          HUMAN_REVIEW
              ↓
      HUMAN_APPROVAL_GRANTED
              ↓
       RECOVERY_INITIATED
              ↓
       PAYMENT_PENDING
              ↓
       PARTIALLY_RECOVERED
              or
       FULLY_RECOVERED
              ↓
            CLOSED

Exceptional conditions route to:

HUMAN_REVIEW
LEGAL_ESCALATION
AUTOMATION_LOCKED
EXECUTION_FAILED

The State Machine is deterministic and serves as the final authority over Recovery Case state transitions.

It does not calculate financial truth, make AI decisions, or execute external payments.

The responsibility boundaries are:

Financial Calculation Service
    ↓
Financial truth

Policy Engine
    ↓
Execution authority

State Machine
    ↓
Workflow validity

Recovery Executor
    ↓
Authorized external execution
The LLM remains a recommendation component and cannot bypass these deterministic controls.