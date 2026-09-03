# Success Criteria

## 1. Purpose

This document defines the criteria used to determine whether the Receivables Resolution Agent is ready for Razorpay Buildathon Track 03 submission.

The criteria evaluate:

- functional completeness,
- financial correctness,
- AI quality,
- safety,
- policy compliance,
- payment integrity,
- auditability,
- benchmark performance,
- engineering quality, and
- demo readiness.

The system must satisfy all mandatory release gates before submission.

---

# 2. Success Philosophy

The project is successful when it demonstrates:

```text
Revenue at Risk
      ↓
Diagnosis
      ↓
Evidence-Grounded Resolution
      ↓
Bounded Recovery
      ↓
Verified Payment
      ↓
Measured Financial Outcome
      ↓
Safe Escalation
      ↓
Complete Audit Trail

The project is not considered successful merely because an LLM can generate plausible recovery recommendations.

3. Requirement Classes

Criteria are divided into:

MUST PASS

Hard release requirements.

Failure blocks MVP submission.

TARGET

Desired benchmark or quality outcomes.

Missing a target does not automatically invalidate the MVP if all mandatory safety and functional gates pass.

STRETCH

Optional improvements that strengthen the submission after the core system is stable.

4. MUST PASS — Product Functionality

The following capabilities must work end-to-end.

[ ] At-risk receivable detection
[ ] AI triage
[ ] Evidence retrieval
[ ] Evidence assessment
[ ] Deterministic financial calculation
[ ] Collectible amount determination
[ ] Resolution recommendation
[ ] Deterministic policy evaluation
[ ] Deterministic state transitions
[ ] Approved recovery execution
[ ] Razorpay Test Mode integration
[ ] Razorpay webhook verification
[ ] Partial recovery
[ ] Human approval
[ ] Human escalation
[ ] Legal/safety stop
[ ] Audit trail
[ ] Benchmark execution
5. MUST PASS — Golden Workflow

The canonical partial-recovery journey must work end-to-end.

Scenario:

Invoice:
₹10,00,000

Verified disputed amount:
₹1,00,000

Approved recovery:
₹9,00,000

Expected flow:

OVERDUE
   ↓
TRIAGING
   ↓
QUANTITY_DISPUTE
   ↓
EVIDENCE_ANALYSIS
   ↓
COLLECTIBLE_AMOUNT = ₹9,00,000
        ↓
CREATE_PARTIAL_RECOVERY
        ↓
POLICY REVIEW
        ↓
HUMAN_APPROVAL_REQUIRED
        ↓
FINANCE APPROVAL
        ↓
RECOVERY AUTHORIZED
        ↓
Razorpay Payment Link
   ↓
Customer Test Payment
   ↓
Verified Webhook
   ↓
PARTIALLY_RECOVERED

The system must display the complete audit trace.Because the default automated recovery authority is ₹5,00,000, the ₹9,00,000 recovery requires human approval before execution. The ₹9,00,000 remains the evidence-supported collectible amount; only the autonomous execution authority is exceeded.

6. MUST PASS — Safe Failure Workflow

At least one safety-critical failure must be demonstrated.

Recommended:

Customer communicates legal-risk condition
        ↓
LEGAL_RISK_DETECTED
        ↓
AUTOMATION_LOCKED
        ↓
NO AUTOMATED RECOVERY
        ↓
NO PROHIBITED OUTREACH
        ↓
LEGAL_ESCALATION
        ↓
AUDIT TRACE

A second recommended demonstration:

Conflicting Evidence
        ↓
NO VERIFIED COLLECTIBLE AMOUNT
        ↓
NO AUTOMATIC RECOVERY
        ↓
HUMAN_REVIEW
7. MUST PASS — Financial Integrity

The implementation must guarantee:

recovered_amount >= 0
verified_disputed_amount >= 0
collectible_amount >= 0

and:

recovered_amount <= invoice_amount

and, where applicable:

recovery_action_amount <= verified_collectible_amount

No financial calculation may rely on floating-point arithmetic for authoritative monetary state.

8. MUST PASS — Policy Safety

The Policy Engine must be deterministic.

The following must be enforced:

[ ] Recovery cannot exceed verified collectible amount
[ ] Autonomous recovery authority is enforced
[ ] Concession cap is enforced
[ ] Touchpoint limit is enforced
[ ] Quiet hours are enforced where configured
[ ] Legal lock prevents prohibited automation
[ ] Human approval is required when authority is exceeded
[ ] Policy failures fail closed
9. MUST PASS — State Safety

The State Machine must:

[ ] Reject invalid transitions
[ ] Prevent direct recovery-state manipulation
[ ] Prevent recovery from legal-locked cases
[ ] Require verified payment evidence before successful recovery
[ ] Prevent invalid terminal-state mutation
[ ] Handle payment failure safely
[ ] Handle execution failure safely
[ ] Protect against stale state
[ ] Support valid human-review transitions
10. MUST PASS — AI Safety

The system must demonstrate that:

[ ] AI output is schema validated
[ ] AI cannot directly execute Razorpay actions
[ ] AI cannot directly mutate financial state
[ ] AI cannot bypass Policy Engine
[ ] AI cannot bypass State Machine
[ ] AI cannot remove legal locks
[ ] AI cannot invent evidence
[ ] AI cannot convert customer instructions into system authority
11. MUST PASS — Prompt Injection Resistance

The system must pass the prompt-injection safety cases defined in:

docs/03-evaluation/safety-tests.md

At minimum:

[ ] Ignore-instructions attack
[ ] Fake-system-message attack
[ ] Financial-authority manipulation
[ ] Policy manipulation
[ ] Tool-invocation injection
[ ] AI hallucinated evidence

None may produce unauthorized financial execution.

12. MUST PASS — Payment Integrity

The payment workflow must demonstrate:

[ ] Payment request ≠ payment confirmation
[ ] Webhook signature verification
[ ] Event payload validation
[ ] Webhook idempotency
[ ] Correct Payment Link mapping
[ ] Payment amount reconciliation
[ ] Duplicate-event protection
[ ] Unknown-resource protection
[ ] Safe provider failure handling
13. MUST PASS — Human Approval

The system must support human approval for restricted actions.

Approval must be bound to:

case
+
proposal
+
action
+
amount
+
approver

The implementation must reject:

[ ] wrong-case approval
[ ] changed-amount reuse
[ ] changed-action reuse
[ ] unauthorized approver
[ ] rejected approval followed by execution
14. MUST PASS — Auditability

Every material recovery case must have a reconstructable audit trail.

For a successful recovery, the trace must connect:

Evidence
   ↓
AI result
   ↓
Financial assessment
   ↓
Resolution proposal
   ↓
Policy decision
   ↓
Recovery action
   ↓
Payment event
   ↓
Verified payment
   ↓
Recovery outcome

For a blocked case, the trace must show:

Proposal
   ↓
Policy / Safety condition
   ↓
Block / Stop
   ↓
Escalation
15. MUST PASS — Audit Integrity

The implementation must demonstrate:

[ ] Material financial events are recorded
[ ] State transitions are auditable
[ ] Policy decisions are auditable
[ ] Human approvals are auditable
[ ] Payment confirmations are auditable
[ ] Legal locks are auditable
[ ] Historical events are append-oriented
[ ] Audit records do not contain secrets
[ ] Private LLM chain-of-thought is not exposed
16. MUST PASS — Benchmark Infrastructure

The repository must support a reproducible benchmark run.

Required capability:

python run_eval.py

or an equivalent single-command benchmark entry point.

The benchmark must:

[ ] Load the selected benchmark version
[ ] Execute all cases
[ ] Produce per-case results
[ ] Produce aggregate metrics
[ ] Produce safety results
[ ] Produce financial totals
[ ] Produce escalation metrics
[ ] Produce audit metrics
[ ] Record model/prompt/policy versions
17. MUST PASS — Benchmark Size

Minimum:

50 cases

Target:

100 cases

The final submission should use the frozen benchmark-v1 dataset or a later explicitly versioned dataset.

18. MUST PASS — Benchmark Coverage

The benchmark must contain meaningful representation of:

[ ] Payment failures
[ ] Quantity disputes
[ ] Price disputes
[ ] PO mismatches
[ ] Documentation issues
[ ] Milestone/service acceptance
[ ] Credit notes
[ ] Promise-to-pay
[ ] Partial recovery
[ ] Insufficient evidence
[ ] Conflicting evidence
[ ] Legal/high-risk
[ ] Policy boundary
[ ] Outreach stopping
[ ] Prompt injection
[ ] Payment/webhook failure
[ ] Multi-factor cases
19. MUST PASS — Zero-Tolerance Safety Gates

The following must be:

Unsupported Recovery Rate            = 0%
Over-Recovery Rate                   = 0%
Policy Violation Rate                = 0%
Safety Violation Rate                = 0%
Payment Confirmation Without Evidence = 0
Legal Lock Bypass                    = 0
Duplicate Financial Effects          = 0
Approval Replay                      = 0

For legal and evidence-safety cases:

Legal Stop Recall                    = 100%
Evidence Safety Recall               = 100%
20. MUST PASS — Webhook Safety Gates

The following should be:

Webhook Integrity Rate               = 100%
Idempotency Success Rate             = 100%
Payment Confirmation Accuracy        = 100%

These are deterministic integration controls and therefore should not have an acceptable error margin in the MVP.

21. MUST PASS — Audit Gates

The target for the MVP is:

Audit Completeness                   = 100%
Audit Reconstruction Rate             = 100%

Every golden case must have a fully reconstructable trace.

22. TARGET — Intelligence Quality

Desired benchmark performance:

Diagnosis Accuracy                  >= 90%
Evidence Accuracy                   >= 85%
Collectible Amount Accuracy         >= 85%
Resolution Accuracy                 >= 90%

These are targets rather than claims about actual performance.

The final submission must report measured values.

23. TARGET — Financial Recovery

Desired:

Safe Automatic Recovery Rate        >= 70%

The denominator is:

Safely Recoverable Amount

not total revenue at risk.

The final value must be measured from the benchmark.

24. TARGET — Escalation

Desired:

Under-Escalation Rate               <= 2%

and:

Correct Escalation Rate             >= 90%

Over-escalation should be minimized without weakening the safety gates.

25. TARGET — Cycle Time

Desired benchmark result:

Meaningful cycle-time reduction

The exact percentage should be reported only after the manual baseline and automated timing methodology are frozen.

A simulated cycle-time result must be labeled as simulated.

26. TARGET — AI Confidence

The benchmark should show reasonable confidence calibration.

Desired behavior:

High confidence
+
Correct result

for straightforward cases.

And:

Low / uncertain confidence
+
Human review

for genuinely ambiguous cases.

High confidence must never override policy or evidence controls.

27. TARGET — Developer Experience

A new developer should be able to:

clone repository
      ↓
configure environment
      ↓
start dependencies
      ↓
run tests
      ↓
run benchmark
      ↓
start application

with clearly documented commands.

28. MUST PASS — Automated Tests

The backend test suite must cover:

[ ] Financial calculations
[ ] Policy Engine
[ ] State Machine
[ ] AI output schemas
[ ] Recovery execution guards
[ ] Human approvals
[ ] Webhook verification
[ ] Webhook idempotency
[ ] Audit event generation
[ ] Tenant isolation
[ ] Prompt injection

Critical safety tests must fail the test suite when violated.

29. MUST PASS — No Secret Leakage

Before submission:

[ ] No API keys in Git
[ ] No webhook secrets in Git
[ ] No passwords in Git
[ ] No production credentials in benchmark data
[ ] No secrets in frontend bundle
[ ] No secrets in logs
[ ] No secrets in audit payloads

A repository secret scan should pass before submission.

30. MUST PASS — Repository Structure

The repository should contain:

README.md
AGENTS.md
ARCHITECTURE.md
MVP.md
DECISIONS.md

docs/
├── 01-product/
├── 02-engineering/
├── 03-evaluation/
└── 04-demo/

Implementation directories will be added during the build phases.

31. MUST PASS — Documentation Consistency

The documentation must not contain contradictions between:

Product Definition
Engineering Architecture
Domain Model
Database Schema
State Machine
Policy Engine
AI Contracts
API Contracts
Razorpay Integration
Webhook Design
Audit System
Security Model
Evaluation Specification

When a requirement changes, dependent documents must be updated in the same change.

32. MUST PASS — Track Traceability

The final system must be clearly traceable to the Track 03 workflow:

Detect Revenue at Risk
        ↓
Determine Right Intervention
        ↓
Execute Bounded Recovery
        ↓
Measure Money Recovered
        ↓
Compliant Escalation
        ↓
Stopping Rules
        ↓
Audit Trail

The final README and demo should explicitly show this mapping.

33. MUST PASS — Product Differentiation

The project must visibly demonstrate that it is not merely:

overdue invoice
      ↓
send reminder

It must demonstrate one or more of:

Evidence-grounded dispute diagnosis
Collectible amount decomposition
Partial recovery
Evidence conflict handling
Policy-gated recovery
Safe escalation
Revenue friction analysis

The MVP's strongest differentiation is:

Collectible Amount Decomposition
+
Partial Recovery
+
Evidence-Grounded Resolution
34. MUST PASS — Golden Demo

The final five-minute demonstration should contain:

Act 1 — Problem

Show an overdue B2B invoice with a real blocker.

Act 2 — AI Resolution

Show:

customer objection
      ↓
evidence
      ↓
verified dispute
      ↓
collectible amount
Act 3 — Bounded Recovery

Show:

policy
      ↓
approved recovery
      ↓
Razorpay payment request
Act 4 — Verified Outcome

Show:

payment
      ↓
webhook
      ↓
recovery state
Act 5 — Safety

Show one case where:

legal risk / evidence conflict
      ↓
automation stops
      ↓
human escalation
Act 6 — Batch Evidence

Show benchmark metrics:

cases
revenue at risk
safely recoverable
recovered
safety violations
escalations
audit completeness
35. MUST PASS — Demo Integrity

Every number shown in the final demo must be traceable to:

actual application output,
actual benchmark output, or
clearly labeled illustrative/sample data.

The demo must not present simulated numbers as production measurements.

36. MUST PASS — No Fake Integrations

The submission must clearly distinguish:

Real Razorpay Test Mode integration

from:

Mock/simulated benchmark infrastructure

The project must not imply that a mock payment is a real Razorpay transaction.

37. STRETCH — Revenue Friction Analytics

After the MVP is stable, add:

Recovery Cases
      ↓
Aggregate Root Causes
      ↓
Revenue Friction Dashboard

Example:

32% → PO mismatch
21% → payment failure
18% → quantity dispute

This turns recovery data into upstream business intelligence.

38. STRETCH — Root-Cause Prevention

Use historical cases to identify recurring conditions associated with delayed revenue.

Example:

Invoices missing PO references
      ↓
High overdue probability
      ↓
Recommend upstream correction

This moves the product from:

Recover

toward:

Recover + Prevent
39. STRETCH — Promise-to-Pay Intelligence

Add a structured promise lifecycle:

PROMISE_MADE
      ↓
DUE_DATE_REACHED
      ↓
PAYMENT_OBSERVED?
     /       \
   YES        NO
   ↓           ↓
FULFILLED   BREACHED

Use the result to determine the next bounded recovery action.

40. STRETCH — Adaptive Recovery

Use historical benchmark/application outcomes to recommend which bounded intervention has historically performed best for similar cases.

The recommendation must remain subject to deterministic Policy Engine constraints.

The system must never autonomously learn or modify financial policy.

41. Release Gate

The MVP may be considered submission-ready only when:

[ ] All MUST PASS functional requirements pass
[ ] All Critical safety tests pass
[ ] Zero-tolerance safety gates pass
[ ] Golden recovery scenario works
[ ] Golden safety scenario works
[ ] Razorpay Test Mode integration works
[ ] Webhook verification works
[ ] Benchmark runs reproducibly
[ ] At least 50 benchmark cases execute
[ ] Audit trail is complete
[ ] No secrets are committed
[ ] Documentation is consistent
[ ] Demo flow is reproducible
[ ] README explains the system clearly
42. Final Submission Checklist

Before submission:

REPOSITORY
[ ] Public repository
[ ] Clean README
[ ] Architecture documented
[ ] Setup instructions tested
[ ] Environment example included
[ ] No secrets

PRODUCT
[ ] Problem clearly stated
[ ] Track alignment explicit
[ ] Differentiation explicit
[ ] MVP boundary documented

ENGINEERING
[ ] Architecture implemented
[ ] Database migrations work
[ ] State machine tested
[ ] Policy Engine tested
[ ] AI contracts enforced
[ ] Razorpay integration tested
[ ] Webhook verified
[ ] Audit trace complete
[ ] Security checks passed

EVALUATION
[ ] Benchmark frozen
[ ] Dataset version recorded
[ ] 50+ cases
[ ] Per-case outputs
[ ] Aggregate metrics
[ ] Safety metrics
[ ] Recovery metrics
[ ] No ground-truth leakage

DEMO
[ ] Golden recovery works
[ ] Partial recovery shown
[ ] Safety stop shown
[ ] Human review shown
[ ] Benchmark results shown
[ ] No fake production claims
43. Final Success Definition

Receivables Resolution Agent is considered successful when it can demonstrate:

A real B2B receivable is at risk
            ↓
The system identifies why
            ↓
The system gathers and evaluates evidence
            ↓
The system separates disputed from collectible value
            ↓
The system recommends the appropriate intervention
            ↓
Deterministic policy decides whether automation is permitted
            ↓
Razorpay executes an approved recovery action
            ↓
A verified payment event establishes what was actually recovered
            ↓
The system resolves, partially recovers, or escalates the remainder
            ↓
Every material decision is auditable
            ↓
The entire behavior is measurable across a benchmark batch

The project succeeds not by maximizing autonomy, but by demonstrating:

Safe, evidence-supported, measurable revenue recovery.