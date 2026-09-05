"use client";

import React, { useEffect, useState } from 'react';
import {
  fetchCase, fetchCaseAudit, runTriage, analyzeEvidence,
  generateProposal, checkPolicy, createApproval, executeRecovery,
  formatCurrency, RecoveryCaseSummary, PaginatedAuditResponse
} from '@/lib/api';

export default function CaseDetailPage({ params }: { params: { id: string } }) {
  const [data, setData] = useState<RecoveryCaseSummary | null>(null);
  const [audit, setAudit] = useState<PaginatedAuditResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [actionLoading, setActionLoading] = useState(false);

  // Workflow context
  const [proposalId, setProposalId] = useState<string | null>(null);
  const [actionId, setActionId] = useState<string | null>(null);
  const [approvalId, setApprovalId] = useState<string | null>(null);
  const [policyDecision, setPolicyDecision] = useState<any>(null);
  const [aiRecommendation, setAiRecommendation] = useState<any>(null);

  const loadData = async () => {
    try {
      const [caseData, auditData] = await Promise.all([
        fetchCase(params.id),
        fetchCaseAudit(params.id)
      ]);
      setData(caseData);
      setAudit(auditData);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [params.id]);

  const handleAction = async (actionFn: () => Promise<any>, onSuccess?: (res: any) => void) => {
    setActionLoading(true);
    try {
      const res = await actionFn();
      if (onSuccess) onSuccess(res);
      await loadData();
    } catch (err: any) {
      alert(`Action failed: ${err.message}`);
    } finally {
      setActionLoading(false);
    }
  };

  if (loading) return <div className="text-center py-10 animate-pulse text-slate-400">Loading case details...</div>;
  if (error) return <div className="bg-red-900/20 text-red-400 p-4 rounded border border-red-900">Error: {error}</div>;
  if (!data) return null;

  const getActiveStep = () => {
    const status = data.status;
    if (["CLOSED", "FULLY_RECOVERED", "CANCELLED"].includes(status)) return 5;
    if (["PAYMENT_PENDING", "PARTIALLY_RECOVERED"].includes(status)) return 4;
    if (["HUMAN_REVIEW", "POLICY_REVIEW", "RECOVERY_INITIATED"].includes(status)) return 3;
    if (["RESOLUTION_READY"].includes(status)) return 2;
    if (["EVIDENCE_ANALYSIS", "ISSUE_IDENTIFIED"].includes(status)) return 1;
    return 0; // OVERDUE, TRIAGING
  };

  return (
    <div className="space-y-8">
      {/* Header */}
      <div className="bg-slate-900 p-6 rounded-lg border border-slate-800 flex justify-between items-center shadow-md">
        <div>
          <div className="flex items-center gap-3 mb-2">

            <h2 className="text-2xl font-bold font-mono">
              {data.id}
              {data.is_demo && (
                <span className="ml-3 inline-block bg-amber-900/50 text-amber-500 text-xs px-2 py-1 rounded border border-amber-800 align-middle">
                  DEMO DATA
                </span>
              )}
            </h2>

            <span className="bg-blue-900/50 text-blue-400 px-3 py-1 rounded-full text-xs font-bold tracking-wider">
              {data.status}
            </span>
          </div>
          <div className="text-sm text-slate-400 flex gap-6">
            <span><strong className="text-slate-300">Invoice:</strong> {data.invoice_id}</span>
            <span><strong className="text-slate-300">Customer:</strong> {data.customer_id}</span>
          </div>
        </div>
      </div>

      {/* Financial Position */}
      <div className="bg-slate-900 border border-slate-800 rounded-lg p-6 shadow-md">
        <h3 className="text-lg font-semibold mb-4 border-b border-slate-800 pb-2">Financial Position</h3>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-6">
          <div>
            <div className="text-xs text-slate-400 uppercase tracking-wider mb-1">Claimed Disputed</div>
            <div className="text-xl font-medium">{formatCurrency(data.claimed_disputed_amount_minor)}</div>
          </div>
          <div>
            <div className="text-xs text-slate-400 uppercase tracking-wider mb-1">Verified Disputed</div>
            <div className="text-xl font-medium">{formatCurrency(data.verified_disputed_amount_minor)}</div>
          </div>
          <div>
            <div className="text-xs text-slate-400 uppercase tracking-wider mb-1">Collectible</div>
            <div className="text-xl font-medium text-blue-400">{formatCurrency(data.collectible_amount_minor)}</div>
          </div>
          <div>
            <div className="text-xs text-slate-400 uppercase tracking-wider mb-1">Safely Recoverable</div>
            <div className="text-xl font-medium text-emerald-400">{formatCurrency(data.safely_recoverable_amount_minor)}</div>
          </div>
          <div>
            <div className="text-xs text-slate-400 uppercase tracking-wider mb-1">Recovered</div>
            <div className="text-xl font-medium text-emerald-500">{formatCurrency(data.recovered_amount_minor)}</div>
          </div>
          <div>
            <div className="text-xs text-slate-400 uppercase tracking-wider mb-1">Remaining Risk</div>
            <div className="text-xl font-medium text-red-400">{formatCurrency(data.remaining_amount_minor)}</div>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
        {/* Workflow Actions */}
        <div className="bg-slate-900 border border-slate-800 rounded-lg p-6 shadow-md">
          <h3 className="text-lg font-semibold mb-4 border-b border-slate-800 pb-2">Recovery Workflow</h3>

          <div className="space-y-6">

            {/* Step 1: Diagnosis & Evidence */}
            <div className={`p-4 rounded border ${getActiveStep() >= 0 ? 'border-blue-900/50 bg-blue-900/10' : 'border-slate-800 opacity-50'}`}>
              <h4 className="font-semibold text-blue-400 mb-2">1. Diagnosis & Evidence Analysis</h4>
              <p className="text-sm text-slate-400 mb-4">Analyze the invoice context, categorize the dispute, and verify external evidence.</p>
              <div className="flex gap-2">
                {['OVERDUE', 'TRIAGING'].includes(data.status) && (
                  <button disabled={actionLoading} onClick={() => handleAction(() => runTriage(data.id))} className="bg-blue-600 hover:bg-blue-500 disabled:opacity-50 text-white px-3 py-1.5 rounded text-sm font-medium">
                    Run Triage
                  </button>
                )}
                {['ISSUE_IDENTIFIED'].includes(data.status) && (
                  <button disabled={actionLoading} onClick={() => handleAction(() => analyzeEvidence(data.id))} className="bg-blue-600 hover:bg-blue-500 disabled:opacity-50 text-white px-3 py-1.5 rounded text-sm font-medium">
                    Analyze Evidence
                  </button>
                )}
                {!['OVERDUE', 'TRIAGING', 'ISSUE_IDENTIFIED'].includes(data.status) && (
                  <span className="text-emerald-400 text-sm font-medium flex items-center gap-1">✓ Completed</span>
                )}
              </div>
            </div>

            {/* Step 2: Resolution Recommendation */}
            <div className={`p-4 rounded border ${getActiveStep() >= 1 ? 'border-blue-900/50 bg-blue-900/10' : 'border-slate-800 opacity-50'}`}>
              <h4 className="font-semibold text-blue-400 mb-2">2. AI Resolution Recommendation</h4>
              <p className="text-sm text-slate-400 mb-4">Generate an AI-driven resolution proposal based on verified financial data.</p>

              {aiRecommendation && (
                <div className="mb-4 bg-slate-950 p-3 rounded border border-slate-800 text-sm">
                  <div className="mb-1"><span className="text-slate-500">Action:</span> <span className="font-mono text-blue-300">{aiRecommendation.action}</span></div>
                  <div><span className="text-slate-500">Proposed Amount:</span> <span className="font-mono text-emerald-300">{formatCurrency(aiRecommendation.proposed_amount_minor)}</span></div>
                </div>
              )}

              <div className="flex gap-2">
                {(['EVIDENCE_ANALYSIS', 'RESOLUTION_READY'].includes(data.status) || (!proposalId && getActiveStep() >= 1 && getActiveStep() < 4)) && (
                  <button disabled={actionLoading} onClick={() => handleAction(() => generateProposal(data.id, data.status === "RESOLUTION_READY"), (res) => {
                    setProposalId(res.proposal_id);
                    setAiRecommendation(res);
                  })} className="bg-blue-600 hover:bg-blue-500 disabled:opacity-50 text-white px-3 py-1.5 rounded text-sm font-medium">
                    {proposalId ? "Regenerate Proposal" : "Generate Proposal"}
                  </button>
                )}
                {proposalId && !['EVIDENCE_ANALYSIS', 'RESOLUTION_READY'].includes(data.status) && (
                  <span className="text-emerald-400 text-sm font-medium flex items-center gap-1">✓ Generated</span>
                )}
              </div>
            </div>

            {/* Step 3: Policy & Approval */}
            <div className={`p-4 rounded border ${getActiveStep() >= 2 ? 'border-purple-900/50 bg-purple-900/10' : 'border-slate-800 opacity-50'}`}>
              <h4 className="font-semibold text-purple-400 mb-2">3. Policy Engine & Human Approval</h4>
              <p className="text-sm text-slate-400 mb-4">Evaluate the AI proposal against merchant policies. Human approval required if triggered.</p>

              {policyDecision && (
                <div className="mb-4 bg-slate-950 p-3 rounded border border-slate-800 text-sm">
                  <div className="mb-1"><span className="text-slate-500">Decision:</span> <span className={`font-mono ${policyDecision.decision === 'APPROVED' ? 'text-emerald-400' : 'text-amber-400'}`}>{policyDecision.decision}</span></div>
                  {policyDecision.reason_code && <div><span className="text-slate-500">Reason:</span> <span className="font-mono text-slate-300">{policyDecision.reason_code}</span></div>}
                </div>
              )}

              <div className="flex gap-2">
                {proposalId && ['RESOLUTION_READY', 'POLICY_REVIEW'].includes(data.status) && (
                  <button disabled={actionLoading} onClick={() => handleAction(() => checkPolicy(data.id, proposalId), (res) => {
                    setPolicyDecision(res);
                    if (res.recovery_action_id) setActionId(res.recovery_action_id);
                  })} className="bg-purple-600 hover:bg-purple-500 disabled:opacity-50 text-white px-3 py-1.5 rounded text-sm font-medium">
                    Evaluate Policy
                  </button>
                )}
              </div>

              {data.status === 'HUMAN_REVIEW' && proposalId && actionId && (
                <div className="mt-4 p-4 border border-amber-900/50 bg-amber-900/20 rounded">
                  <h4 className="font-semibold text-amber-500 mb-2">Review Required</h4>
                  <div className="flex gap-3">
                    <button disabled={actionLoading} onClick={() => handleAction(() => createApproval(data.id, proposalId, actionId, 'APPROVED', 'Manually approved via dashboard'), (res) => setApprovalId(res.id))} className="bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 text-white px-3 py-1.5 rounded text-sm font-medium">
                      Approve
                    </button>
                    <button disabled={actionLoading} onClick={() => handleAction(() => createApproval(data.id, proposalId, actionId, 'REJECTED', 'Manually rejected via dashboard'))} className="bg-red-600 hover:bg-red-500 disabled:opacity-50 text-white px-3 py-1.5 rounded text-sm font-medium">
                      Reject
                    </button>
                  </div>
                </div>
              )}
            </div>

            {/* Step 4: Execution */}
            <div className={`p-4 rounded border ${getActiveStep() >= 3 ? 'border-emerald-900/50 bg-emerald-900/10' : 'border-slate-800 opacity-50'}`}>
              <h4 className="font-semibold text-emerald-400 mb-2">4. Recovery Execution & Payment</h4>
              <p className="text-sm text-slate-400 mb-4">Execute the authorized recovery action (e.g., generate a Razorpay payment link).</p>

              <div className="flex gap-2">
                {proposalId && (data.status === 'RECOVERY_INITIATED' || data.status === 'POLICY_REVIEW') && (
                  <button disabled={actionLoading} onClick={() => handleAction(() => executeRecovery(data.id, proposalId, approvalId || undefined))} className="bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 text-white px-3 py-1.5 rounded text-sm font-medium">
                    Execute Recovery Action
                  </button>
                )}
                {getActiveStep() >= 4 && (
                  <span className="text-emerald-400 text-sm font-medium flex items-center gap-1">✓ Execution Initiated</span>
                )}
              </div>
            </div>

          </div>
        </div>

        {/* Audit Timeline */}
        <div className="bg-slate-900 border border-slate-800 rounded-lg p-6 shadow-md h-full flex flex-col">
          <h3 className="text-lg font-semibold mb-4 border-b border-slate-800 pb-2">Audit Timeline</h3>
          <div className="space-y-4 flex-1 overflow-y-auto max-h-[600px] pr-2">
            {audit?.data.map((event) => (
              <div key={event.id} className="border-l-2 border-slate-700 pl-4 py-1">
                <div className="flex justify-between items-baseline mb-1">
                  <span className="font-semibold text-blue-400">{event.event_type}</span>
                  <span className="text-[10px] text-slate-500">{new Date(event.created_at).toLocaleString()}</span>
                </div>
                <div className="text-xs text-slate-400 mb-2">
                  Actor: <span className="font-mono">{event.actor_type}</span>
                  {event.state_before && event.state_after && (
                    <span className="ml-2">({event.state_before} &rarr; {event.state_after})</span>
                  )}
                </div>
                {event.payload_json && Object.keys(event.payload_json).length > 0 && (
                  <pre className="text-[10px] bg-slate-950 p-2 rounded border border-slate-800 text-slate-300 overflow-x-auto whitespace-pre-wrap">
                    {JSON.stringify(event.payload_json, null, 2)}
                  </pre>
                )}
              </div>
            ))}
            {(!audit?.data || audit.data.length === 0) && (
              <div className="text-slate-500 text-sm italic">No audit events found.</div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
