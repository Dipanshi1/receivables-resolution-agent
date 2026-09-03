# Architecture & Product Decisions

## 1. Purpose

This document records important product and engineering decisions made for the Receivables Resolution Agent.

The purpose is to:

- preserve architectural intent,
- prevent accidental reversal of important decisions,
- explain trade-offs,
- provide context for future contributors,
- provide traceability for changes made during implementation.

These decisions represent the current project direction.

When a decision is intentionally changed, the change should be recorded rather than silently overwritten.

---

# 2. Decision Format

Each decision contains:

- decision,
- rationale,
- alternatives considered,
- consequences.

Decisions may be revised when new technical or product evidence justifies a change.

---

# ADR-001 — Use a Modular Monolith for the MVP

## Decision

Use a modular-monolith architecture for the initial implementation.

Primary deployable layers:

```text
Next.js Frontend
       +
FastAPI Backend
       +
PostgreSQL

The backend is internally divided into modules.

Rationale

The MVP requires many logical components but does not require independent service deployment.

A modular monolith provides:

faster implementation,
simpler local development,
lower infrastructure overhead,
simpler debugging,
easier transactional consistency,
easier repository review.
Alternatives considered
Microservices

Rejected for MVP because they would introduce unnecessary:

networking,
deployment,
service discovery,
observability,
failure modes,
infrastructure overhead.
Serverless-first architecture

Not selected because the core workflow benefits from a persistent relational domain model and explicit application services.

Consequence

The codebase must maintain clear internal boundaries even though modules are deployed together.

ADR-002 — AI Does Not Own Financial Authority
Decision

LLMs may interpret information and recommend actions, but deterministic application components own financial authorization.

Rationale

LLMs can:

hallucinate,
misunderstand evidence,
follow prompt injections,
produce malformed outputs,
make arithmetic mistakes.

Financial actions therefore require deterministic controls.

The architecture is:

LLM
 ↓
Structured Recommendation
 ↓
Financial Validation
 ↓
Policy Engine
 ↓
State Machine
 ↓
Recovery Executor
Alternatives considered
Fully autonomous LLM agent

Rejected because it creates an unsafe and difficult-to-audit financial execution boundary.

LLM + human approval for every action

Rejected for the MVP because it would eliminate the value of bounded automation.

Consequence

The interesting AI work remains in:

semantic diagnosis,
evidence interpretation,
resolution recommendation.

Financial execution remains deterministic.

ADR-003 — Use Deterministic Financial Calculations
Decision

Authoritative financial calculations are performed by application code rather than the LLM.

Rationale

Financial arithmetic must be:

reproducible,
precise,
testable,
auditable.

The LLM may extract values such as:

quantity_invoiced
quantity_delivered
unit_price

The application computes:

disputed amount
collectible amount
remaining amount
recovered amount
Consequence

Financial calculation logic must have independent automated tests.

ADR-004 — Represent INR Amounts in Minor Units
Decision

Represent INR monetary values internally as integer paise.

Example:

₹9,00,000
=
90,000,000 paise
Rationale

Floating-point arithmetic can introduce precision problems.

Integer minor units provide an exact representation for INR monetary calculations.

Alternatives considered
Floating-point numbers

Rejected.

Approximate decimal calculations

Rejected for authoritative financial state.

Database decimal everywhere

Potentially valid for some financial domains, but integer minor units simplify the MVP's INR-focused payment/recovery calculations.

Consequence

API fields use explicit names such as:

amount_minor
total_amount_minor
recovered_amount_minor
ADR-005 — Separate Invoice from Recovery Case
Decision

An Invoice and a Recovery Case are separate domain entities.

Rationale

An invoice represents:

what the customer owes.

A recovery case represents:

what the system is doing about recovering it.

The operational workflow should not mutate the meaning of the underlying invoice.

Consequence

The application can preserve financial records independently of workflow state.

ADR-006 — Separate Customer Claim from Verified Dispute
Decision

The system must distinguish:

claimed_disputed_amount

from:

verified_disputed_amount
Rationale

A customer assertion is not automatically a verified financial fact.

The system should follow:

Customer Claim
    ↓
Evidence
    ↓
Verification
    ↓
Verified Dispute
Consequence

Insufficient or conflicting evidence can prevent automatic recovery.

ADR-007 — Partial Recovery Is a Core MVP Capability
Decision

Partial recovery is part of the MVP rather than a post-MVP feature.

Rationale

The central product differentiation is:

Recover the evidence-supported undisputed amount without waiting for an unrelated disputed portion to be resolved.

Example:

Invoice:
₹10,00,000

Verified dispute:
₹1,00,000

Recoverable:
₹9,00,000

This directly addresses the operational bottleneck the project is designed to solve.

Consequence

The domain model, Policy Engine, Razorpay integration, UI, benchmark, and audit system must support partial recovery.

ADR-008 — Distinguish Application Partial Recovery from Razorpay Partial Payments
Decision

The application's concept of partial recovery must remain separate from Razorpay's provider-level partial-payment capability.

Rationale

Application-level partial recovery answers:

What portion of the commercial receivable is currently eligible for recovery?

Razorpay partial payment answers:

Can the customer pay part of the amount associated with a Payment Link?

They solve different problems.

Consequence

The application owns the commercial dispute/recovery decomposition.

Razorpay remains the payment execution/provider layer.

ADR-009 — Use a Payment Provider Abstraction
Decision

The core recovery domain depends on an application-level payment-provider interface.

PaymentProvider
      │
      ├── RazorpayProvider
      └── MockPaymentProvider
Rationale

This provides:

real Razorpay Test Mode integration,
deterministic benchmark execution,
easier testing,
provider-independent domain logic.
Alternatives considered
Direct Razorpay SDK calls throughout the codebase

Rejected because it would couple the domain directly to provider implementation details.

Multiple production payment providers in MVP

Rejected as unnecessary scope.

Consequence

Razorpay-specific logic is isolated in the provider adapter.

ADR-010 — Use Real Razorpay Test Mode for Selected Flows
Decision

Use real Razorpay Test Mode for the primary end-to-end demonstration.

Rationale

The project should demonstrate genuine Razorpay integration rather than a simulated provider-only implementation.

Scope

At minimum:

Create Payment Link
Test payment
Webhook delivery
Webhook verification
Payment-state update
Recovery-state update
Consequence

The demonstration requires valid Test Mode configuration.

Production credentials are not required.

ADR-011 — Use Mock Payment Provider for Batch Evaluation
Decision

Use MockPaymentProvider for the 50–100 case benchmark.

Rationale

Large benchmark runs should not depend on:

provider availability,
network behavior,
test-mode resource limits,
external rate limits,
repeated live payment operations.

The benchmark measures recovery reasoning and deterministic system behavior rather than the availability of an external payment provider.

Consequence

The final demo must distinguish:

Real Razorpay Test Mode

from:

Mock Benchmark Simulation
ADR-012 — Webhook Events Are Required for Payment Truth
Decision

The application does not consider a payment successful merely because a Payment Link was created.

Payment confirmation requires verified external payment evidence.

Rationale

Payment-link creation proves only that a payment request exists.

It does not prove that the customer paid.

Consequence

The workflow is:

Payment Link Created
       ↓
PAYMENT_PENDING
       ↓
Verified Razorpay Event
       ↓
Payment Reconciliation
       ↓
Recovery State Update
ADR-013 — Webhook Idempotency Is Mandatory
Decision

Razorpay webhook processing must be idempotent.

Rationale

External webhooks may be delivered more than once.

Duplicate events must not produce duplicate financial effects.

Mechanism

Use the provider's webhook event identifier where available.

The application must preserve processed-event state.

Consequence

Tests must verify duplicate webhook delivery.

ADR-014 — Webhook Event Ordering Cannot Be Assumed
Decision

The system must not assume that external webhook events arrive in perfect chronological order.

Rationale

Provider documentation indicates that webhook delivery order is not guaranteed.

Consequence

The application relies on:

current state,
payment records,
event validation,
domain transition guards,

rather than blindly applying events in arrival order.

ADR-015 — Legal and Safety Conditions Override Recovery Optimization
Decision

Legal/high-risk conditions take precedence over normal recovery optimization.

Rationale

A system that continues autonomous customer contact or financial recovery after a legal-risk signal creates unacceptable operational and reputational risk.

Behavior
Legal Risk
    ↓
Automation Lock
    ↓
Stop Prohibited Automation
    ↓
Legal / Human Escalation
Consequence

The legal lock is enforced deterministically and cannot be removed by the LLM.

ADR-016 — Evidence Conflict Prevents Unsupported Automatic Recovery
Decision

Material unresolved evidence conflicts block autonomous financial recovery.

Rationale

The system should not silently choose a convenient interpretation of contradictory business records.

Example
GRN:
90 units

Customer:
80 units

The system should surface the conflict and route the case to review.

Consequence

The benchmark explicitly tests evidence conflicts.

ADR-017 — Fail Closed on Critical Control Failure
Decision

If a critical control layer cannot reliably evaluate an action, the system must not execute the financial action.

Applies to:

Policy Engine failure,
State Machine failure,
financial validation failure,
missing required evidence,
invalid AI output,
webhook verification failure.
Rationale

The safer failure mode for a financial system is:

Do not execute

rather than:

Assume approval
Consequence

Operational escalation and retry paths must be explicit.

ADR-018 — Human Approval Is Bound to the Exact Proposal
Decision

Human approval is valid only for the exact recovery action and amount approved.

Rationale

A generic approval token could be replayed against a modified financial action.

Example

Approved:

₹9,00,000

Modified:

₹9,50,000

The second action requires new validation and approval.

Consequence

Approval records must include:

case
proposal
action
amount
approver
timestamp
ADR-019 — Use Explicit State Machine Rather Than Arbitrary Status Updates
Decision

Recovery Case state transitions are controlled by a deterministic state machine.

Rationale

Financial workflows need:

explicit valid transitions,
invalid-transition protection,
auditable state changes,
predictable behavior.
Consequence

Generic APIs that allow arbitrary status mutation are prohibited.

ADR-020 — Audit Financial Decisions Without Storing Private Chain-of-Thought
Decision

Store structured decision facts and provenance, not private model chain-of-thought.

Rationale

Operational explainability does not require exposing private model deliberation.

The audit trail should show:

Evidence
 ↓
Structured AI result
 ↓
Financial assessment
 ↓
Resolution proposal
 ↓
Policy decision
 ↓
Recovery action
 ↓
Payment confirmation
Consequence

AI runs store:

model,
prompt version,
input fingerprint,
structured output,
confidence,
evidence references,

rather than private chain-of-thought.

ADR-021 — Use PostgreSQL as the Primary Database
Decision

Use PostgreSQL for the MVP.

Rationale

The domain requires:

relational integrity,
foreign keys,
transactions,
precise financial state,
aggregations,
JSONB support.

PostgreSQL provides all required capabilities without introducing multiple databases.

ADR-022 — Use PostgreSQL JSONB Selectively
Decision

Use JSONB for naturally semi-structured data, not core financial fields.

Suitable examples
AI output
Evidence facts
Policy check results
Audit payloads
Provider metadata
Do not use JSONB as the primary representation of:
invoice amount
payment amount
case status
recovered amount
customer identity
Consequence

Frequently queried financial/domain attributes remain relational columns.

ADR-023 — No Vector Database in MVP
Decision

Do not introduce a dedicated vector database unless the evidence workflow demonstrates a real retrieval requirement.

Rationale

The MVP primarily uses:

structured business records,
small evidence documents,
synthetic benchmark data.

A dedicated vector system would add infrastructure complexity without a demonstrated need.

Future option

Use PostgreSQL + pgvector if semantic retrieval becomes necessary.

ADR-024 — No Kubernetes, Kafka, or Microservices in MVP
Decision

Do not introduce distributed infrastructure unless an explicit requirement emerges.

Rationale

These technologies solve scale/operational problems that the MVP does not yet have.

Their introduction would increase:

development time,
infrastructure complexity,
debugging complexity,
deployment risk.
Consequence

Engineering effort is concentrated on:

domain correctness,
AI quality,
deterministic controls,
Razorpay integration,
evaluation.
ADR-025 — Benchmark Ground Truth Is Isolated
Decision

Ground truth must remain inaccessible to the inference path.

Rationale

A benchmark is meaningless if the system can inspect its answers.

Consequence

The dataset architecture separates:

Inference Data

from:

Ground Truth

The evaluator combines them only after inference.

ADR-026 — Safety Metrics Are Release Gates
Decision

Critical safety metrics are hard release gates rather than weighted trade-offs.

Required targets
Unsupported Recovery Rate = 0%
Over-Recovery Rate = 0%
Policy Violation Rate = 0%
Safety Violation Rate = 0%
Legal Stop Recall = 100%
Evidence Safety Recall = 100%
Payment Confirmation Accuracy = 100%
Webhook Integrity = 100%
Idempotency = 100%
Audit Completeness = 100%
Rationale

Improving recovery rate is not an acceptable trade for unsafe financial behavior.

ADR-027 — Optimize for Safe Recovery, Not Maximum Automation
Decision

The system should maximize safe, evidence-supported recovery rather than maximize the percentage of cases handled without humans.

Rationale

Some cases should intentionally escalate.

Examples:

conflicting evidence
legal risk
authority exceeded
ambiguous financial facts

Correct escalation is a successful outcome.

Consequence

The benchmark reports:

recovery,
escalation,
safety,
financial integrity,

separately.

ADR-028 — Partial Recovery Is the Primary Differentiator
Decision

The main product story should center on:

Evidence-Grounded Dispute Diagnosis
+
Collectible Amount Decomposition
+
Partial Recovery
Rationale

A generic dunning system primarily asks:

"How do we contact the customer again?"

This project instead asks:

"What portion of the receivable is genuinely blocked, and what can safely be recovered now?"

That distinction is central to the product.

ADR-029 — Benchmark Uses Synthetic Data
Decision

Use synthetic B2B receivables for evaluation.

Rationale

Synthetic data provides:

reproducibility,
controlled edge cases,
safe testing,
ground-truth access for evaluators,
no exposure of real customer financial data.
Consequence

Benchmark results must be described as benchmark results, not as measured production impact.

ADR-030 — Repository Is Designed for Direct Code Review
Decision

The repository must be structured so that an engineer can quickly understand:

Problem
↓
Architecture
↓
Implementation
↓
Tests
↓
Evaluation
↓
Demo
Required properties
clear documentation,
readable module boundaries,
deterministic tests,
reproducible benchmark,
real Test Mode integration,
no unnecessary infrastructure.
Rationale

The repository is part of the buildathon deliverable and should function as an engineering artifact, not merely as a code dump.

3. Decision Change Process

When a major architectural/product decision changes:

identify the existing decision,
document why it is no longer valid,
record the new decision,
update affected documents,
update implementation and tests.

Do not silently contradict the existing decision record.

4. Decision Principle

The project's decision-making hierarchy is:

Financial Integrity
      ↓
Safety
      ↓
Correctness
      ↓
Auditability
      ↓
Maintainability
      ↓
Developer Velocity
      ↓
Feature Count