# User Journey

## 1. Primary User

### Finance / Accounts Receivable Operations

The primary user is a finance or accounts-receivable team responsible for collecting outstanding B2B receivables.

Their objectives are to:

- identify revenue at risk,
- understand why receivables are overdue,
- recover legitimate amounts as quickly as possible,
- avoid inappropriate customer follow-up,
- escalate complex cases efficiently, and
- maintain a defensible record of financial decisions.

The system is designed to reduce manual investigation rather than replace finance decision-making entirely.

---

# 2. Current-State Journey

A typical B2B receivable begins as an invoice issued to a customer.

If payment does not arrive by the due date, the finance team generally starts a collection workflow.

A simplified current workflow is:

```text
Invoice becomes overdue
        ↓
Finance identifies overdue invoice
        ↓
Customer is contacted
        ↓
Customer explains issue
        ↓
Finance investigates manually
        ↓
Finds invoice / PO / GRN / contract / emails
        ↓
Determines whether objection is valid
        ↓
Calculates amount that can be collected
        ↓
Contacts customer again
        ↓
Creates payment request
        ↓
Waits for payment
        ↓
Follows up or escalates

The expensive portion of this workflow is often the investigation between:

"Customer has not paid"

and:

"We know what is preventing payment and what can safely be recovered."

3. Future-State Journey

Receivables Resolution Agent inserts an intelligence and control layer into the recovery workflow.

Invoice becomes overdue
        ↓
Revenue-at-risk detection
        ↓
Recovery case created
        ↓
Triage
        ↓
Evidence analysis
        ↓
Resolution proposal
        ↓
Deterministic policy evaluation
        ↓
┌───────────────────────────────┐
│                               │
▼                               ▼
Approved                     Blocked /
│                            Deferred /
│                            Escalated
▼                               │
Razorpay recovery                 │
│                                 │
▼                                 ▼
Payment event                 Human / Legal
│                              review
▼
Verified recovery
│
▼
Audit trail + updated case state
4. Journey A — Full Recovery

This is the simplest case.

Scenario

An invoice of ₹2,00,000 becomes overdue.

The customer has no commercial dispute.

Payment previously failed.

Step 1 — Detection

The system identifies the overdue receivable.

Invoice:
₹2,00,000

Status:
OVERDUE

Reason:
Payment failure

A recovery case is created.

Step 2 — Triage

The Triage Agent identifies:

Issue:
PAYMENT_FAILURE

No commercial dispute is detected.

Step 3 — Evidence

The system verifies:

invoice exists,
customer is valid,
amount remains outstanding,
previous payment attempt failed.

No conflicting evidence exists.

Step 4 — Resolution

The Resolution Agent proposes:

Action:
CREATE_FULL_RECOVERY

Amount:
₹2,00,000
Step 5 — Policy

The Policy Engine checks:

amount within automated authority,
no legal lock,
contact limits not exceeded,
recovery allowed for this case.

Result:

APPROVED
Step 6 — Razorpay

The system creates the appropriate Razorpay payment request.

The case moves to:

PAYMENT_PENDING
Step 7 — Payment

Customer completes payment.

A verified Razorpay PAYMENT_CONFIRMED domain event is received.

The State Machine applies the verified event after financial reconciliation.
It determines whether the case moves to:

PARTIALLY_RECOVERED

or:

FULLY_RECOVERED
Step 8 — Audit

The system records:

Invoice overdue
→
Payment failure detected
→
Recovery proposed
→
Policy approved
→
Payment request created
→
Payment confirmed
→
Fully recovered
5. Journey B — Partial Recovery from a Commercial Dispute

This is the primary product journey.

Scenario

A B2B software company issues:

Invoice:
₹10,00,000

The customer responds:

"We received only 90 of the 100 licenses billed. We are disputing the remaining 10."

Step 1 — Detection

The invoice becomes overdue.

The system creates:

Recovery Case:
CASE-1042

Invoice:
INV-1042

Amount:
₹10,00,000
Step 2 — Triage

The Triage Agent analyzes the customer communication and identifies:

Issue:
QUANTITY_DISPUTE

It also identifies that evidence analysis is required.

The agent does not make a payment decision.

Step 3 — Evidence Collection

The system retrieves relevant evidence:

Invoice
Purchase Order
Delivery / GRN
Customer Email

The evidence contains:

PO:
100 licenses

Invoice:
100 licenses

GRN:
90 licenses

Customer:
10 licenses disputed
Step 4 — Evidence Analysis

The Evidence Agent extracts structured facts.

Quantity invoiced:
100

Quantity delivered:
90

Quantity disputed:
10

Deterministic business logic then calculates the associated amount.

Invoice:
₹10,00,000

Disputed:
₹1,00,000

Collectible:
₹9,00,000

The system stores the evidence supporting the conclusion.

Step 5 — Resolution

The Resolution Agent proposes:

Action:
CREATE_PARTIAL_RECOVERY

Amount:
₹9,00,000

Remaining disputed amount:
₹1,00,000

The proposal contains the relevant evidence references.

Step 6 — Policy Evaluation

The Policy Engine checks:

✓ Collectible amount supports recovery amount
✓ No legal lock
✓ Recovery amount exceeds the ₹5,00,000 autonomous authority
✓ No touchpoint violation
✓ No prohibited concession
✓ Current case state permits recovery

Result:

HUMAN_APPROVAL_REQUIRED

The case enters:

HUMAN_REVIEW

The human must approve the exact ₹9,00,000 recovery action. The approval is
bound to the recovery case, proposal, action, amount, and action fingerprint.

Any material action change invalidates the approval.
Step 7 — Recovery

Only after valid human approval authorizes the exact recovery action does the
system create a Razorpay payment request for ₹9,00,000.

Application-level metadata links the recovery action to:

Parent invoice:
INV-1042

Recovery case:
CASE-1042

Recovery type:
UNDISPUTED_AMOUNT

The case becomes:

PAYMENT_PENDING
Step 8 — Payment Confirmation

The customer pays ₹9,00,000.

The system receives a Razorpay payment event.

The event is:

signature-verified,
checked for duplicate processing, and
matched to the recovery action.

The case becomes:

PARTIALLY_RECOVERED

Financial position:

Original invoice        ₹10,00,000
Recovered               ₹9,00,000
Remaining disputed      ₹1,00,000
Outstanding collectible ₹0
Step 9 — Remaining Dispute

The ₹1,00,000 disputed portion remains outside automatic recovery.

It enters the appropriate resolution or escalation workflow.

The system provides the human operator with:

customer objection,
invoice,
PO,
delivery evidence,
extracted facts,
disputed amount,
recovery already achieved, and
complete decision history.

The finance team does not need to reconstruct the case from scratch.

6. Journey C — Insufficient or Conflicting Evidence
Scenario

The invoice is ₹10,00,000.

Customer claims:

"We only received around 80 units."

Available evidence says:

PO:
100 units

GRN:
90 units

Customer message:
80 units

The exact disputed amount cannot be established reliably.

Agent behavior

The Evidence Agent marks:

EVIDENCE_CONFLICT

and:

COLLECTIBLE_AMOUNT:
UNKNOWN

The Resolution Agent cannot safely produce an executable recovery amount.

The Policy Engine therefore prevents automatic financial execution.

The case becomes:

HUMAN_REVIEW
What the finance user sees
Automatic recovery unavailable

Reason:
Conflicting evidence

Conflict:
GRN = 90
Customer claim = 80

Required:
Human verification

The user receives the evidence package rather than a guessed recovery decision.

7. Journey D — Legal / High-Risk Escalation
Scenario

The customer responds:

"Do not contact us again. Our lawyer will issue a legal notice regarding this invoice."

System behavior

The communication is analyzed for risk.

A deterministic safety layer independently checks for high-risk legal signals.

The recovery case is locked:

AUTOMATION_LOCKED

Automated actions stop.

Automated outreach:
STOPPED

Automated recovery:
STOPPED

The case becomes:

LEGAL_ESCALATION
Human handoff

The finance/legal operator receives:

Invoice
Customer communication
Relevant evidence
Previous actions
Recovery history
Policy state
Audit trail

The system does not attempt to resolve the legal matter autonomously.

8. Journey E — Human Approval
Scenario

An overdue invoice has a verified collectible amount of:

₹9,00,000

The merchant policy permits automated recovery only up to:

₹5,00,000
System behavior

The AI proposes:

CREATE_RECOVERY
₹9,00,000

The Policy Engine determines:

Evidence:
PASS

Legal:
PASS

Recovery authority:
EXCEEDED

Result:

HUMAN_APPROVAL_REQUIRED

The user sees:

Recovery request
₹9,00,000

Reason:
Verified collectible amount

Approval required because:
Amount exceeds automated authority
₹5,00,000

The user can approve or reject the exact proposal.

An approval is bound to the specific proposal and amount.

A modified proposal requires a new policy evaluation and approval.

9. User Experience Across All Journeys

The finance user should always be able to answer four questions quickly:

What is happening?

Current case state.

Why is it happening?

Issue classification and supporting evidence.

What can we recover?

Verified collectible and disputed amounts.

What happens next?

Recommended action, policy status, and required human intervention.

10. Primary Dashboard Journey

When the user enters the dashboard, the system prioritizes:

Revenue at risk
        ↓
Recoverable amount
        ↓
Recently recovered
        ↓
Cases requiring attention
        ↓
Blocked / escalated cases

The user can then drill into an individual case.

11. Case Detail Journey

The case detail view presents information in this order:

Financial summary
        ↓
Reason for non-payment
        ↓
Evidence
        ↓
AI resolution proposal
        ↓
Policy decision
        ↓
Recovery action
        ↓
Payment status
        ↓
Remaining balance
        ↓
Audit timeline

This order keeps financial impact visible before technical details.

12. Human-in-the-Loop Journey

The human is not brought into every case.

The system attempts autonomous resolution only where policy permits.

Human involvement occurs when:

evidence is insufficient,
evidence conflicts,
financial authority is exceeded,
a policy exception is requested,
legal/high-risk conditions are detected,
automated attempts are exhausted, or
the system encounters a condition it cannot safely resolve.

The goal is therefore not:

100% autonomous recovery

but:

maximum safe automation with efficient human escalation.

13. Recovery State Lifecycle

A simplified case lifecycle is:

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
Verified PAYMENT_CONFIRMED domain event
        ↓
FULLY_RECOVERED
or
PARTIALLY_RECOVERED

PAYMENT_CONFIRMED is a verified domain event, not a Recovery Case state.

Exceptional paths include:

EVIDENCE_INSUFFICIENT
        ↓
HUMAN_REVIEW
EVIDENCE_CONFLICT
        ↓
HUMAN_REVIEW
LEGAL_RISK
        ↓
AUTOMATION_LOCKED
        ↓
LEGAL_ESCALATION

HUMAN_APPROVAL_REQUIRED
        ↓
HUMAN_REVIEW

BLOCKED
        ↓
No execution
        ↓
HUMAN_REVIEW

STOPPED
        ↓
AUTOMATION_LOCKED

HUMAN_APPROVAL_REQUIRED, BLOCKED, and STOPPED are Policy Engine outcomes,
not Recovery Case states.
14. End-to-End Product Principle

The user journey can be summarized as:

Find the money at risk
        ↓
Understand why it is stuck
        ↓
Verify what is true
        ↓
Determine what is collectible
        ↓
Act only within authority
        ↓
Confirm actual payment
        ↓
Resolve or escalate what remains

The system should never optimize recovery by ignoring evidence or bypassing merchant controls.

15. Desired User Outcome

After using the system, a finance operator should spend less time asking:

"Why hasn't this invoice been paid?"

and more time making decisions on the relatively small number of cases that genuinely require human judgment.

For straightforward and evidence-supported cases, the system should move the receivable toward recovery automatically.

For ambiguous or high-risk cases, it should make the problem easier to understand and safer to hand off.

16. Product Success From the User's Perspective

The user should experience:

Less investigation

The system gathers and summarizes relevant evidence.

Faster recovery

Legitimately collectible amounts can be pursued without waiting for unrelated disputes to close.

Safer automation

The system cannot bypass configured financial or safety controls.

Better escalation

Human operators receive a prepared evidence package instead of a blank case.

Better visibility

The finance team can see where receivables are blocked and how much money has been recovered.


---

## Why this document is important

Notice that the journey contains **both success and failure paths**.

That matters for Track 03.

A weak project will show:

```text
invoice overdue
→ AI
→ payment
→ yay

Our project must demonstrate:

                    OVERDUE
                       │
            ┌──────────┼──────────┐
            │          │          │
         Clear      Ambiguous    Legal
        evidence     evidence     risk
            │          │          │
            ▼          ▼          ▼
         Recover     Human       Stop
                     review      + escalate

That's much closer to a real financial operations system.
