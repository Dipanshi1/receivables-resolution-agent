import { RecoveryCaseSummary, PaginatedAuditResponse } from './api';

export const DEMO_CASES: RecoveryCaseSummary[] = [
  {
    id: "demo-human-review-123",
    merchant_id: "00000000-0000-0000-0000-000000000001",
    invoice_id: "inv-synthetic-001",
    customer_id: "cust-synthetic-001",
    status: "HUMAN_REVIEW",
    claimed_disputed_amount_minor: 15000000,
    verified_disputed_amount_minor: 15000000,
    collectible_amount_minor: 15000000,
    safely_recoverable_amount_minor: 15000000,
    recovered_amount_minor: 0,
    remaining_amount_minor: 15000000,
    created_at: new Date(Date.now() - 86400000 * 2).toISOString(),
    updated_at: new Date(Date.now() - 3600000).toISOString(),
  },
  {
    id: "demo-payment-pending-456",
    merchant_id: "00000000-0000-0000-0000-000000000001",
    invoice_id: "inv-synthetic-002",
    customer_id: "cust-synthetic-002",
    status: "PAYMENT_PENDING",
    claimed_disputed_amount_minor: 5000000,
    verified_disputed_amount_minor: 5000000,
    collectible_amount_minor: 5000000,
    safely_recoverable_amount_minor: 5000000,
    recovered_amount_minor: 0,
    remaining_amount_minor: 5000000,
    created_at: new Date(Date.now() - 86400000 * 3).toISOString(),
    updated_at: new Date(Date.now() - 7200000).toISOString(),
  },
  {
    id: "demo-partially-recovered-789",
    merchant_id: "00000000-0000-0000-0000-000000000001",
    invoice_id: "inv-synthetic-003",
    customer_id: "cust-synthetic-003",
    status: "PARTIALLY_RECOVERED",
    claimed_disputed_amount_minor: 25000000,
    verified_disputed_amount_minor: 25000000,
    collectible_amount_minor: 25000000,
    safely_recoverable_amount_minor: 25000000,
    recovered_amount_minor: 10000000,
    remaining_amount_minor: 15000000,
    created_at: new Date(Date.now() - 86400000 * 5).toISOString(),
    updated_at: new Date(Date.now() - 86400000).toISOString(),
  }
];

export const DEMO_AUDITS: Record<string, PaginatedAuditResponse> = {
  "demo-human-review-123": {
    data: [
      {
        id: "evt-001", case_id: "demo-human-review-123", event_type: "RECOVERY_CASE_CREATED", actor_type: "API", actor_id: null,
        state_before: null, state_after: "OVERDUE", payload_json: { trigger: "INVOICE_OVERDUE" }, created_at: new Date(Date.now() - 86400000 * 2).toISOString()
      },
      {
        id: "evt-002", case_id: "demo-human-review-123", event_type: "TRIAGE_COMPLETED", actor_type: "AI_AGENT", actor_id: null,
        state_before: "OVERDUE", state_after: "ISSUE_IDENTIFIED", payload_json: { issue_type: "PRICE_DISPUTE" }, created_at: new Date(Date.now() - 86400000 * 1.5).toISOString()
      },
      {
        id: "evt-003", case_id: "demo-human-review-123", event_type: "EVIDENCE_ANALYSIS_COMPLETED", actor_type: "AI_AGENT", actor_id: null,
        state_before: "ISSUE_IDENTIFIED", state_after: "EVIDENCE_ANALYSIS", payload_json: { finding: "SUPPORTED" }, created_at: new Date(Date.now() - 86400000 * 1).toISOString()
      },
      {
        id: "evt-004", case_id: "demo-human-review-123", event_type: "RESOLUTION_PROPOSED", actor_type: "AI_AGENT", actor_id: null,
        state_before: "EVIDENCE_ANALYSIS", state_after: "RESOLUTION_READY", payload_json: { proposed_amount_minor: 15000000 }, created_at: new Date(Date.now() - 43200000).toISOString()
      },
      {
        id: "evt-005", case_id: "demo-human-review-123", event_type: "POLICY_EVALUATED", actor_type: "POLICY_ENGINE", actor_id: null,
        state_before: "RESOLUTION_READY", state_after: "HUMAN_REVIEW", payload_json: { decision: "HUMAN_APPROVAL_REQUIRED", reason_code: "HIGH_VALUE_DISPUTE" }, created_at: new Date(Date.now() - 3600000).toISOString()
      }
    ],
    total: 5, page: 1, page_size: 50
  },
  "demo-payment-pending-456": {
    data: [
      {
        id: "evt-006", case_id: "demo-payment-pending-456", event_type: "RECOVERY_CASE_CREATED", actor_type: "API", actor_id: null,
        state_before: null, state_after: "OVERDUE", payload_json: { trigger: "INVOICE_OVERDUE" }, created_at: new Date(Date.now() - 86400000 * 3).toISOString()
      },
      {
        id: "evt-007", case_id: "demo-payment-pending-456", event_type: "RESOLUTION_PROPOSED", actor_type: "AI_AGENT", actor_id: null,
        state_before: "EVIDENCE_ANALYSIS", state_after: "RESOLUTION_READY", payload_json: { proposed_amount_minor: 5000000 }, created_at: new Date(Date.now() - 86400000).toISOString()
      },
      {
        id: "evt-008", case_id: "demo-payment-pending-456", event_type: "POLICY_EVALUATED", actor_type: "POLICY_ENGINE", actor_id: null,
        state_before: "RESOLUTION_READY", state_after: "POLICY_REVIEW", payload_json: { decision: "APPROVED", reason_code: null }, created_at: new Date(Date.now() - 43200000).toISOString()
      },
      {
        id: "evt-009", case_id: "demo-payment-pending-456", event_type: "RECOVERY_EXECUTION_INITIATED", actor_type: "API", actor_id: null,
        state_before: "POLICY_REVIEW", state_after: "PAYMENT_PENDING", payload_json: { proposal_id: "synthetic-proposal-id", amount_minor: 5000000 }, created_at: new Date(Date.now() - 7200000).toISOString()
      }
    ],
    total: 4, page: 1, page_size: 50
  },
  "demo-partially-recovered-789": {
    data: [
      {
        id: "evt-010", case_id: "demo-partially-recovered-789", event_type: "RECOVERY_EXECUTION_INITIATED", actor_type: "API", actor_id: null,
        state_before: "POLICY_REVIEW", state_after: "PAYMENT_PENDING", payload_json: { amount_minor: 10000000 }, created_at: new Date(Date.now() - 86400000 * 2).toISOString()
      },
      {
        id: "evt-011", case_id: "demo-partially-recovered-789", event_type: "PAYMENT_CAPTURED", actor_type: "PROVIDER", actor_id: null,
        state_before: "PAYMENT_PENDING", state_after: "PARTIALLY_RECOVERED", payload_json: { amount_minor: 10000000 }, created_at: new Date(Date.now() - 86400000).toISOString()
      }
    ],
    total: 2, page: 1, page_size: 50
  }
};
