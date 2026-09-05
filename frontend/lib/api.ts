import { UUID } from 'crypto';

export const MERCHANT_ID = "00000000-0000-0000-0000-000000000001";

export function getApiBaseUrl(): string {
  return process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000';
}

export const defaultHeaders = {
  'Content-Type': 'application/json',
  'Accept': 'application/json',
  'X-Merchant-ID': MERCHANT_ID,
};

// ---------------------------------------------------------------------------
// Schemas
// ---------------------------------------------------------------------------

export interface RecoveryCaseSummary {
  id: string;
  merchant_id: string;
  invoice_id: string;
  customer_id: string;
  status: string;
  claimed_disputed_amount_minor: number;
  verified_disputed_amount_minor: number | null;
  collectible_amount_minor: number | null;
  safely_recoverable_amount_minor: number | null;
  recovered_amount_minor: number;
  remaining_amount_minor: number;
  created_at: string;
  updated_at: string;
}

export interface PaginatedCasesResponse {
  data: RecoveryCaseSummary[];
  total: number;
  page: number;
  page_size: number;
}

export interface TriageResponse {
  case_id: string;
  issue_type: string;
  state_before: string;
  state_after: string;
}

export interface EvidenceResponse {
  case_id: string;
  finding: string;
  state_before: string;
  state_after: string;
}

export interface ResolveResponse {
  case_id: string;
  proposal_id: string;
  action: string;
  proposed_amount_minor: number;
  collectible_amount_minor: number;
  safely_recoverable_amount_minor: number;
  state_before: string;
  state_after: string;
}

export interface PolicyCheckResponse {
  policy_decision_id: string;
  recovery_action_id: string | null;
  decision: string;
  policy_version: string;
  reason_code: string | null;
  state_before: string;
  state_after: string;
}

export interface ExecuteRecoveryResponse {
  recovery_action_id: string;
  status: string;
  amount_minor: number | null;
  state_before: string;
  state_after: string;
}

export interface ApprovalResponse {
  id: string;
  case_id: string;
  action_id: string;
  decision: string;
  requested_amount_minor: number | null;
  action_fingerprint: string;
  justification: string | null;
  approved_by: string | null;
  created_at: string;
  resolved_at: string | null;
}

export interface AuditEventResponse {
  id: string;
  case_id: string;
  event_type: string;
  actor_type: string;
  actor_id: string | null;
  state_before: string | null;
  state_after: string | null;
  payload_json: any | null;
  created_at: string;
}

export interface PaginatedAuditResponse {
  data: AuditEventResponse[];
  total: number;
  page: number;
  page_size: number;
}

// ---------------------------------------------------------------------------
// API Methods
// ---------------------------------------------------------------------------

async function fetchApi<T>(path: string, options: RequestInit = {}): Promise<T> {
  const url = `${getApiBaseUrl()}${path}`;
  const res = await fetch(url, {
    ...options,
    headers: { ...defaultHeaders, ...options.headers },
  });
  if (!res.ok) {
    const errorData = await res.json().catch(() => null);
    throw new Error(errorData?.detail?.message || `API error: ${res.statusText}`);
  }
  return res.json();
}

export async function fetchCases(page = 1, pageSize = 50): Promise<PaginatedCasesResponse> {
  return fetchApi<PaginatedCasesResponse>(`/v1/recovery-cases?page=${page}&page_size=${pageSize}`);
}

export async function fetchCase(caseId: string): Promise<RecoveryCaseSummary> {
  return fetchApi<RecoveryCaseSummary>(`/v1/recovery-cases/${caseId}`);
}

export async function fetchCaseAudit(caseId: string): Promise<PaginatedAuditResponse> {
  return fetchApi<PaginatedAuditResponse>(`/v1/recovery-cases/${caseId}/audit`);
}

export async function runTriage(caseId: string): Promise<TriageResponse> {
  return fetchApi<TriageResponse>(`/v1/recovery-cases/${caseId}/triage`, {
    method: 'POST',
    body: JSON.stringify({ force: false }),
  });
}

export async function analyzeEvidence(caseId: string): Promise<EvidenceResponse> {
  return fetchApi<EvidenceResponse>(`/v1/recovery-cases/${caseId}/evidence`, {
    method: 'POST',
    body: JSON.stringify({ scope: 'AUTO' }),
  });
}

export async function generateProposal(caseId: string, force = false): Promise<ResolveResponse> {
  return fetchApi<ResolveResponse>(`/v1/recovery-cases/${caseId}/resolve`, {
    method: 'POST',
    body: JSON.stringify({ force }),
  });
}

export async function checkPolicy(caseId: string, proposalId: string): Promise<PolicyCheckResponse> {
  return fetchApi<PolicyCheckResponse>(`/v1/recovery-cases/${caseId}/policy-check`, {
    method: 'POST',
    body: JSON.stringify({ proposal_id: proposalId }),
  });
}

export async function createApproval(caseId: string, proposalId: string, actionId: string, decision: "APPROVED" | "REJECTED", reason?: string): Promise<ApprovalResponse> {
  return fetchApi<ApprovalResponse>(`/v1/recovery-cases/${caseId}/approvals`, {
    method: 'POST',
    body: JSON.stringify({
      proposal_id: proposalId,
      recovery_action_id: actionId,
      decision,
      reason
    }),
  });
}

export async function executeRecovery(caseId: string, proposalId: string, humanApprovalId?: string): Promise<ExecuteRecoveryResponse> {
  return fetchApi<ExecuteRecoveryResponse>(`/v1/recovery-cases/${caseId}/execute`, {
    method: 'POST',
    body: JSON.stringify({
      proposal_id: proposalId,
      human_approval_id: humanApprovalId || null,
    }),
  });
}

export function formatCurrency(minorUnits: number | null | undefined): string {
  if (minorUnits == null) return "₹0.00";
  return `₹${(minorUnits / 100).toFixed(2)}`;
}

export interface HealthResponse {
  status: string;
}

export interface HealthCheckResult {
  connected: boolean;
  data?: HealthResponse;
  error?: string;
}

export async function fetchHealthStatus(): Promise<HealthCheckResult> {
  const baseUrl = getApiBaseUrl();
  try {
    const res = await fetch(`${baseUrl}/v1/health`);
    if (!res.ok) return { connected: false, error: res.statusText };
    return { connected: true, data: await res.json() };
  } catch (err: any) {
    return { connected: false, error: err.message };
  }
}
