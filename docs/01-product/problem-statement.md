# Problem Statement

## 1. Track Context

**Razorpay Buildathon Track:** Track 03 — AI Revenue Recovery

The track asks builders to create an agent that:

1. detects revenue at risk,
2. determines the right intervention,
3. executes a bounded recovery workflow, and
4. demonstrates measured money recovered across a batch.

The track also explicitly requires compliant escalation, stopping rules, and an audit trail.

This project is designed directly around those requirements.

---

## 2. The Real Business Problem

B2B businesses regularly have significant amounts of money tied up in overdue receivables.

An overdue invoice does not necessarily mean that the customer is unwilling or unable to pay.

In many B2B workflows, payment is blocked by an unresolved operational or commercial issue such as:

- quantity or delivery discrepancies,
- purchase-order mismatches,
- incorrect pricing,
- missing milestone approvals,
- incorrect GST or billing information,
- missing documentation,
- partial invoice disputes,
- service-delivery disagreements, or
- unresolved payment/process failures.

When this happens, a conventional collection workflow often treats the situation simply as:

> **Invoice overdue → send reminder → send another reminder → escalate.**

That approach is ineffective when the actual blocker requires investigation and resolution.

---

## 3. Why This Creates a Real Operational Problem

Finance and accounts-receivable teams may have to manually:

1. identify which receivables are genuinely at risk,
2. read customer email conversations,
3. inspect invoices and invoice line items,
4. locate purchase orders,
5. compare delivery or GRN records,
6. review contracts or milestone records,
7. determine what portion of the invoice is actually disputed,
8. determine what amount is still collectible,
9. choose an appropriate intervention,
10. create a payment request,
11. monitor the resulting payment, and
12. escalate cases that cannot be safely resolved.

This process becomes expensive and slow when hundreds or thousands of receivables are outstanding.

The problem is therefore not simply a lack of payment reminders.

The deeper problem is:

> **The reason preventing legitimate payment often remains unresolved, leaving collectible cash unnecessarily blocked.**

---

## 4. Representative Example

Consider a B2B software invoice of ₹10,00,000.

The customer states:

> "We received only 90 of the 100 licenses billed and are disputing the remaining amount."

The available evidence contains:

- invoice: 100 licenses,
- purchase order: 100 licenses,
- delivery/GRN record: 90 licenses,
- customer communication: dispute for 10 licenses.

A conventional collection workflow may continue treating the entire ₹10,00,000 as overdue.

A better recovery workflow should recognize:

```text
Invoice amount       ₹10,00,000
Supported dispute    ₹1,00,000
Potentially collectible amount
                     ₹9,00,000

The ₹9,00,000 that is supported by the available evidence should not necessarily remain blocked while the ₹1,00,000 dispute is being resolved.

At the same time, the system must not make an unsupported assumption that the customer owes ₹9,00,000.

The recovery decision must be grounded in evidence and constrained by explicit financial policies.

5. Core Problem We Are Solving
Primary problem

B2B receivables become unnecessarily delayed because existing recovery workflows often focus on chasing payment rather than resolving the underlying blocker that prevents legitimate payment.

More precise system problem

For an overdue receivable, a finance team needs to determine:

Why is payment stuck?
What evidence supports the customer's objection?
What portion of the amount is genuinely disputed?
What amount is legitimately collectible now?
What intervention is appropriate?
Can that intervention be performed automatically within merchant-defined limits?
When should automation stop and a human take over?

Today, answering these questions can require substantial manual effort across fragmented business information.

6. Why AI Is Relevant

The information required to resolve these cases is often heterogeneous and partially unstructured.

Examples include:

natural-language customer emails,
invoice descriptions,
purchase-order text,
delivery records,
contract clauses,
milestone notes,
payment histories, and
previous communications.

AI is useful for the semantic part of the workflow:

understanding customer objections,
classifying the likely reason for non-payment,
extracting facts from unstructured communications,
identifying relevant evidence, and
proposing a resolution.

However, AI should not have unrestricted authority over financial actions.

Financial calculations, policy enforcement, state transitions, payment confirmation, and execution must remain deterministic.

7. Our Intended Problem Boundary

This project focuses specifically on:

B2B receivables that are delayed because of operational or commercial blockers.

The project is not primarily a:

generic payment reminder system,
generic dunning bot,
customer-support chatbot,
fraud detector,
accounting replacement, or
general-purpose autonomous finance agent.

The differentiating problem is:

Resolving the blocker behind an overdue receivable so that the legitimately collectible portion of the money can be recovered safely.

8. Track 03 Alignment

The project maps directly to the Track 03 requirements:

Track 03 requirement	Problem addressed by this project
Detect revenue at risk	Identify overdue/stuck B2B receivables
Determine the right intervention	Diagnose the blocker and determine the appropriate recovery path
Execute a bounded recovery workflow	Execute only policy-approved recovery actions
Demonstrate measured money recovered	Evaluate recovery across a synthetic batch
Compliant escalation	Route high-risk, ambiguous, or unauthorized cases to humans
Stopping rules	Stop outreach/recovery when policy or risk thresholds are reached
Audit trail	Record evidence, decisions, policy checks, actions, and outcomes
9. Key Insight

The fundamental insight behind this project is:

An overdue invoice is a symptom. The real recovery opportunity is often the unresolved problem behind it.

Instead of asking only:

"How do we remind the customer to pay?"

the system asks:

"What is blocking payment, what amount is actually collectible, and what is the safest action we can take now?"

10. Desired Outcome

The system should reduce the amount of legitimately collectible revenue that remains unnecessarily stuck while avoiding unsafe or unsupported automated financial actions.

Success therefore means:

more legitimate cash recovered,
less manual investigation,
faster resolution of receivable blockers,
fewer unnecessary collection attempts,
appropriate human escalation for uncertain cases, and
complete traceability of every financial decision.