# Terminology

## 1. Purpose

This document defines the terminology used throughout the Receivables Resolution Agent project.

The purpose is to maintain consistent product, financial, technical, and engineering language across:

- product documentation,
- source code,
- database models,
- API contracts,
- UI,
- evaluation reports,
- presentation material, and
- AI prompts.

The project should use these definitions consistently.

---

# 2. Receivable

A **receivable** is an amount that a business is entitled to receive from a customer for goods or services already provided or invoiced.

Example:

```text
Customer owes:
₹10,00,000

Receivable:
₹10,00,000

In this project, the receivable is represented primarily through an invoice and its associated payment state.

3. B2B Receivable

A B2B receivable is a receivable arising from a transaction between businesses.

Examples include:

SaaS subscriptions,
software licenses,
professional services,
consulting engagements,
enterprise procurement,
managed services, and
other business-to-business transactions.

The MVP focuses on B2B receivables because they frequently involve supporting business records such as purchase orders, delivery records, contracts, milestones, and finance communications.

4. Invoice

An invoice is a financial document issued by a merchant to a customer requesting payment for specified goods or services.

An invoice may contain:

invoice number,
issue date,
due date,
customer information,
line items,
taxes,
total amount, and
payment terms.

An invoice is a financial record.

It is not itself a recovery case.

5. Invoice Line Item

An invoice line item represents an individual good, service, quantity, rate, or charge within an invoice.

Example:

100 Software Licenses
₹9,000 each

Line-level representation is important because many B2B disputes are limited to specific quantities, products, or services rather than the entire invoice.

6. Outstanding Amount

The outstanding amount is the portion of an invoice that has not yet been paid.

Conceptually:

Outstanding Amount
=
Invoice Amount
-
Verified Payments

The exact financial calculation is performed deterministically by the application.

7. Revenue at Risk

Revenue at risk is revenue represented by receivables that are overdue, likely to remain unresolved, or otherwise require recovery intervention.

For this project, an at-risk amount may arise from:

overdue invoices,
failed payment attempts,
missed payment commitments,
unresolved commercial disputes,
operational blockers, or
other configured recovery-risk signals.

Revenue at risk represents an opportunity for recovery.

It does not mean that the entire amount is necessarily immediately collectible.

8. Recovery

Recovery is the process of converting an outstanding receivable into an actual successful customer payment.

Example:

Outstanding:
₹10,00,000

Successful payment:
₹9,00,000

Recovered:
₹9,00,000

Recovery is complete only when the system has verified that the payment actually succeeded.

Creating a payment request is not itself recovery.

9. Recovery Rate

Recovery rate measures how much safely recoverable value was actually recovered.

For the benchmark:

Recovery Rate
=
Automatically Recovered Amount
/
Safely Recoverable Amount
× 100

The exact benchmark methodology is defined in the evaluation specifications.

10. Recovery Case

A Recovery Case is the operational workflow associated with recovering an outstanding receivable.

An invoice represents:

what the customer owes.

A recovery case represents:

what the system is doing about recovering it.

A recovery case may contain:

issue classification,
disputes,
evidence,
AI proposals,
policy decisions,
recovery actions,
payments,
outreach records,
escalation records, and
audit events.
11. Revenue-Recovery Workflow

The revenue-recovery workflow is the controlled sequence used to move an at-risk receivable toward recovery or appropriate escalation.

The canonical workflow is:

At-Risk Receivable
        ↓
Diagnosis
        ↓
Evidence Analysis
        ↓
Resolution Proposal
        ↓
Policy Validation
        ↓
Recovery / Defer / Escalate
        ↓
Payment Confirmation
        ↓
Final Recovery State
12. Payment Failure

A payment failure occurs when a customer attempts to make a payment but the transaction does not successfully complete.

Examples may include:

payment decline,
expired payment method,
insufficient balance,
network failure, or
other provider-level payment failure.

A payment failure is different from a commercial invoice dispute.

13. Commercial Dispute

A commercial dispute occurs when the customer contests some aspect of the underlying invoice or transaction.

Examples:

incorrect quantity,
incorrect price,
missing delivery,
incorrect purchase-order reference,
incomplete service,
milestone not accepted.

A commercial dispute is distinct from a payment-provider dispute or chargeback.

14. Payment Dispute / Chargeback

A payment dispute or chargeback is a payment-related dispute handled through payment-network or payment-provider dispute mechanisms.

This project primarily focuses on commercial invoice disputes.

The project must not use "dispute" ambiguously when referring to these different concepts.

When necessary, documentation should explicitly use:

Commercial Invoice Dispute

or:

Payment Dispute / Chargeback
15. Disputed Amount

The disputed amount is the portion of an invoice that is genuinely contested by the customer and supported by the available evidence as disputed or blocked.

Example:

Invoice:
₹10,00,000

Verified disputed amount:
₹1,00,000

The disputed amount should not be determined solely from an unsupported customer claim.

It should be grounded in relevant evidence whenever automatic recovery is being considered.

16. Claimed Disputed Amount

The claimed disputed amount is the amount the customer says they are disputing.

Example:

Customer claims:
₹2,00,000 disputed

This is not automatically equivalent to the verified disputed amount.

The system must distinguish:

Customer claim
        ↓
Evidence analysis
        ↓
Verified disputed amount
17. Verified Disputed Amount

The verified disputed amount is the disputed amount supported by sufficient evidence for the system to use in its recovery calculations.

Example:

Customer claims:
₹2,00,000

Evidence supports:
₹1,50,000

Verified disputed amount:
₹1,50,000

If the evidence is insufficient or conflicting, the amount may remain unknown and automatic recovery should be blocked or escalated.

18. Collectible Amount

The collectible amount is the amount that the system determines is currently supported as recoverable based on:

the invoice,
verified payments,
verified dispute information,
relevant evidence, and
applicable business rules.

Example:

Invoice:
₹10,00,000

Verified disputed amount:
₹1,00,000

Collectible amount:
₹9,00,000

The authoritative calculation is deterministic.

The LLM may extract facts used by the calculation, but does not have final authority over the monetary result.

19. Safely Recoverable Amount

The safely recoverable amount is the amount that can legitimately be pursued without violating:

evidence requirements,
merchant policy,
recovery authority,
safety rules,
escalation requirements, or
other system invariants.

An amount may be collectible in principle but not automatically recoverable.

Example:

Verified collectible:
₹9,00,000

Merchant auto-recovery limit:
₹5,00,000

Collectible:
₹9,00,000

Automatically recoverable:
₹5,00,000 or less

The exact behavior depends on merchant policy.

20. Automatically Recoverable Amount

The automatically recoverable amount is the portion of the collectible amount that the system is authorized to recover without human approval.

It is constrained by:

merchant limits,
evidence,
policy,
state,
safety conditions, and
approval requirements.
21. Recovered Amount

The recovered amount is money that has been successfully received and verified through the configured payment workflow.

It should be derived from verified payment events.

Example:

Recovery request:
₹9,00,000

Verified payment:
₹9,00,000

Recovered:
₹9,00,000
22. Remaining Amount

The remaining amount is the portion of the original receivable that has not yet been recovered or otherwise resolved.

For the simplified MVP accounting model:

Remaining Amount
=
Invoice Amount
-
Recovered Amount

The system separately tracks amounts that remain disputed or otherwise blocked.

23. Partial Recovery

Partial recovery occurs when only part of the original receivable is successfully recovered.

Example:

Original invoice:
₹10,00,000

Recovered:
₹9,00,000

Remaining disputed:
₹1,00,000

The case is:

PARTIALLY_RECOVERED

Partial recovery is a core capability of the MVP.

24. Resolution

Resolution is the process of determining what should happen next to address the cause of a receivable being blocked.

A resolution may involve:

full recovery,
partial recovery,
documentation correction,
evidence request,
promise-to-pay handling,
human review,
legal escalation, or
stopping automation.

Resolution is broader than payment collection.

25. Resolution Proposal

A Resolution Proposal is a structured recommendation generated by the AI reasoning layer.

Example:

Action:
CREATE_PARTIAL_RECOVERY

Amount:
₹9,00,000

Reason:
Undisputed amount supported by PO and delivery evidence

A proposal is not permission to execute.

It must pass through the Policy Engine and State Machine.

26. Evidence

Evidence is a business record used to support or challenge a recovery decision.

Examples:

invoice,
purchase order,
GRN,
delivery record,
contract,
milestone record,
customer email,
payment history,
credit note.

Each material resolution claim should be traceable to supporting evidence.

27. Evidence Sufficiency

Evidence sufficiency means that enough reliable information exists to support the proposed resolution or financial action.

Evidence is insufficient when the system cannot confidently establish the facts required for a safe automated action.

Example:

Customer claims:
₹2–3L disputed

PO:
missing

GRN:
missing

Result:

Evidence insufficient
→
No automatic recovery
28. Evidence Conflict

Evidence conflict occurs when relevant sources contain materially inconsistent information.

Example:

GRN:
90 units delivered

Customer communication:
80 units delivered

The system must surface the conflict rather than silently choosing one value.

Conflicting evidence should normally prevent automatic financial execution until resolved.

29. Audit Event

An audit event is an immutable record of a material action, decision, or state transition.

Examples:

RECOVERY_CASE_CREATED
TRIAGE_COMPLETED
EVIDENCE_RETRIEVED
DISPUTE_VERIFIED
COLLECTIBLE_AMOUNT_CALCULATED
POLICY_CHECKED
PAYMENT_LINK_CREATED
PAYMENT_CONFIRMED
LEGAL_LOCK_APPLIED
HUMAN_ESCALATION

The audit system records decision facts and provenance.

It does not require storing or exposing private model chain-of-thought.

30. Policy

A policy is a deterministic set of rules defining what the system may or may not do for a merchant.

Policies may govern:

automated recovery authority,
concessions,
outreach frequency,
quiet hours,
escalation thresholds,
legal locks,
approval requirements.

Policies are enforced by code rather than relying on natural-language instructions to the LLM.

31. Policy Decision

A Policy Decision is the deterministic result of evaluating a proposed action against the applicable merchant policy and current case state.

Possible results are:

APPROVED
DEFERRED
HUMAN_APPROVAL_REQUIRED
BLOCKED
STOPPED
32. State Machine

The State Machine is the deterministic component that controls which Recovery Case states and transitions are valid.

Example:

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

An LLM cannot bypass valid state transitions.

33. Escalation

Escalation means transferring a case from autonomous workflow execution to human or specialized handling.

Types include:

HUMAN_REVIEW
LEGAL_ESCALATION
APPROVAL_REQUIRED

Escalation is not necessarily an error.

It is an intentional safety mechanism.

34. Human-in-the-Loop

Human-in-the-loop means that a human must review or approve a case before a restricted action can continue.

Examples:

recovery exceeds autonomous authority,
evidence is insufficient,
evidence conflicts,
a policy exception is requested,
a legal/high-risk condition occurs.

The human should receive the relevant evidence and reasoning summary required to make an informed decision.

35. Stopping Rule

A stopping rule is a deterministic condition that prevents further automated action.

Examples:

Legal-risk condition
Maximum outreach attempts reached
Insufficient evidence
Policy authority exceeded
Retry limit reached

Stopping rules exist to prevent the recovery system from continuing blindly.

36. Automation Lock

An automation lock is a system state that prevents specified autonomous actions from executing.

Example:

LEGAL_RISK_DETECTED
        ↓
AUTOMATION_LOCKED

When locked, the system may continue to preserve information and support human review, but prohibited autonomous actions must not execute.

37. Recovery Action

A Recovery Action is an operational action intended to move a receivable toward recovery.

Examples:

CREATE_FULL_RECOVERY
CREATE_PARTIAL_RECOVERY
REQUEST_DOCUMENT
REQUEST_CORRECTION
SEND_PAYMENT_REQUEST
STOP_OUTREACH
ESCALATE_HUMAN
ESCALATE_LEGAL

A Recovery Action may only execute after passing the required policy and state checks.

38. Payment Request

A payment request is a request for the customer to pay a specified amount.

In the MVP, an approved recovery action may result in a Razorpay Payment Link or another supported Razorpay payment mechanism.

Creating a payment request does not mean that payment has been completed.

39. Payment Confirmation

Payment confirmation means the application has received and verified a valid external payment event indicating that a payment was successfully completed.

The application must not infer payment success merely from the creation of a payment request.

40. Webhook

A webhook is an externally delivered event notification used to inform the application that a payment-related event occurred.

The application must:

authenticate or verify the webhook,
validate its structure,
handle it idempotently,
associate it with the relevant recovery action, and
update system state through valid transitions.
41. Idempotency

Idempotency means processing the same external event more than once does not produce duplicate financial effects.

Example:

Webhook event:
evt_123

First delivery:
processed

Second delivery:
recognized as duplicate
→ no duplicate recovery
→ no duplicate state transition
42. Settlement

Settlement refers to the transfer of collected funds from a payment provider to a merchant according to the provider's settlement process.

In this project, settlement is not synonymous with receivables recovery.

The project primarily concerns:

Customer receivable
        ↓
Recovery
        ↓
Payment

rather than the provider's downstream merchant settlement process.

The term "settlement" should therefore be used carefully and only when referring to an actual settlement concept.

43. Recovery vs. Settlement

These terms must remain distinct.

Recovery

Collecting money owed by the customer.

Settlement

Provider-side transfer of collected funds to the merchant.

For this project:

We recover receivables; Razorpay handles payment processing and its associated settlement flow.

44. AI Agent

An AI Agent in this project is a bounded reasoning component that interprets information or recommends actions within a larger deterministic workflow.

AI agents may:

classify issues,
extract facts,
identify evidence,
recommend resolutions.

AI agents may not:

directly mutate financial state,
bypass the Policy Engine,
bypass the State Machine,
confirm payments,
override legal locks, or
directly execute financial actions.
45. AI Recommendation

An AI Recommendation is a proposed interpretation or action produced by an AI reasoning component.

It is untrusted until validated.

Conceptually:

AI Recommendation
        ↓
Schema Validation
        ↓
Policy Validation
        ↓
State Validation
        ↓
Execution
46. Human Approval

Human Approval is an explicit authorization from an authorized operator to execute a specific action outside normal autonomous authority.

Approval should be bound to:

recovery case,
proposal,
action,
amount,
approver,
timestamp.

Changing the action or amount requires a new approval.

47. Direct Recovery

Direct recovery means money is successfully recovered through the automated workflow without requiring human intervention for the specific recovery action.

This metric is used to distinguish automatic recovery from cases that require human handling.

48. Cycle Time

Cycle time is the elapsed time required to move a recovery case from its defined starting condition to its defined resolution or recovery outcome.

For evaluation, the system should compare the automated workflow with an explicitly defined simulated manual baseline.

The baseline methodology will be documented separately.

49. Recovery Friction

Recovery friction refers to recurring operational conditions that make a receivable difficult or slow to collect.

Examples include:

repeated PO mismatches,
recurring documentation errors,
repeated quantity disputes,
frequent milestone approval delays.

Recovery friction analytics are a post-MVP capability.

50. Revenue Friction Analytics

Revenue Friction Analytics is the post-MVP capability of aggregating historical recovery cases to identify recurring causes of delayed revenue.

Example:

32% → PO mismatch
21% → payment failure
18% → quantity dispute
14% → documentation issue

This is intended to support upstream process improvement, not merely downstream collection.

51. Canonical Financial Vocabulary

For consistency, the MVP should generally use the following terminology:

Invoice Amount
        ↓
Outstanding Amount
        ↓
Disputed Amount
        ↓
Collectible Amount
        ↓
Recovered Amount
        ↓
Remaining Balance

Where relevant, distinguish:

Claimed Disputed Amount
        ↓
Verified Disputed Amount

and:

Collectible Amount
        ↓
Safely Recoverable Amount
        ↓
Automatically Recoverable Amount

These distinctions prevent the AI system from collapsing different financial concepts into a single number.

52. Canonical Product Principle

Throughout the project, use the following principle:

The LLM interprets and recommends; deterministic systems calculate, authorize, transition, execute, and verify.

This principle is a core architectural and safety constraint of Receivables Resolution Agent.
