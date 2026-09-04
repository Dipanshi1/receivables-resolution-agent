"""Strict typed contracts for the Resolution Agent (advisory, untrusted AI layer).

The Resolution Agent recommends an appropriate resolution strategy and proposed
action based on the verified case context, evidence findings, and financial
assessment. It is advisory and untrusted (docs/02-engineering/ai-contracts.md §17).

It must never:
  - calculate authoritative collectible / recovered / financial amounts,
  - authorize recovery or grant a concession,
  - evaluate policy authority or approve human approval,
  - change RecoveryCase state or transition the state machine,
  - execute Razorpay / create payment links or mark payments successful,
  - mutate authoritative financial state, or bypass deterministic controls.

These contracts encode that boundary structurally:
  - OUTPUT carries recommendations only; ``amount_minor`` is an advisory proposed
    amount, NOT an authoritative financial calculation or authorization (§17.5, §18);
  - all business content on the INPUT is treated as untrusted data (§3.2, §24);
  - model confidence is recorded but is never authorization (§6, §34);
  - every evidence reference must cite IDs supplied in the input context (§5, §17.5);
  - ``extra="forbid"`` on all models rejects any smuggled authority or state field (§22).

Reference: docs/02-engineering/ai-contracts.md §17–§22, §24, §26, §34, §35;
           docs/02-engineering/domain-model.md §16, §23;
           docs/03-evaluation/dataset-spec.md §25, §26, §27, §31, §32.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from pydantic import BaseModel, Field, StrictBool, field_validator

from app.ai.triage_contracts import CommunicationSnippet
from app.domain.enums import ResolutionProposalAction

# ---------------------------------------------------------------------------
# Prompt / contract version (recorded on every AgentRun — ai-contracts.md §29)
# ---------------------------------------------------------------------------
RESOLUTION_PROMPT_VERSION = "resolution-v1"


# ---------------------------------------------------------------------------
# Resolution Strategy (high-level resolution approach recommended by AI)
# ---------------------------------------------------------------------------
class ResolutionStrategy(StrEnum):
    """High-level strategy recommended by the Resolution Agent.

    Represents the business approach for resolving the overdue receivable.
    Advisory only; does not authorize execution.
    """

    FULL_COLLECTION = "FULL_COLLECTION"
    PARTIAL_COLLECTION = "PARTIAL_COLLECTION"
    DOCUMENT_RECOVERY = "DOCUMENT_RECOVERY"
    COMMERCIAL_CORRECTION = "COMMERCIAL_CORRECTION"
    PROMISE_PAYMENT_PLAN = "PROMISE_PAYMENT_PLAN"
    CONTACT_HALT = "CONTACT_HALT"
    HUMAN_ESCALATION = "HUMAN_ESCALATION"
    LEGAL_ESCALATION = "LEGAL_ESCALATION"


# ---------------------------------------------------------------------------
# Standard Resolution Reason Codes (ai-contracts.md §17.5, §19, §20)
# ---------------------------------------------------------------------------
class ResolutionReasonCode(StrEnum):
    """Standard reason codes for resolution recommendations."""

    UNDISPUTED_AMOUNT = "UNDISPUTED_AMOUNT"
    FULL_AMOUNT_OWED = "FULL_AMOUNT_OWED"
    EVIDENCE_PARTIALLY_SUPPORTED = "EVIDENCE_PARTIALLY_SUPPORTED"
    EVIDENCE_UNSUPPORTED = "EVIDENCE_UNSUPPORTED"
    EVIDENCE_CONFLICT = "EVIDENCE_CONFLICT"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"
    GST_DOCUMENTATION = "GST_DOCUMENTATION"
    PO_MISMATCH = "PO_MISMATCH"
    PROMISE_TO_PAY = "PROMISE_TO_PAY"
    LEGAL_RISK = "LEGAL_RISK"
    TOUCHPOINT_LIMIT_REACHED = "TOUCHPOINT_LIMIT_REACHED"
    HIGH_VALUE_DISPUTE = "HIGH_VALUE_DISPUTE"
    CONCESSION_REQUEST = "CONCESSION_REQUEST"
    OTHER = "OTHER"


# ---------------------------------------------------------------------------
# Resolution Outcome Status (agent-level run outcome — §21, §35)
# ---------------------------------------------------------------------------
class ResolutionOutcomeStatus(StrEnum):
    """Outcome of a bounded Resolution Agent run."""

    SUCCESS = "SUCCESS"
    NEEDS_HUMAN_REVIEW = "NEEDS_HUMAN_REVIEW"


# ---------------------------------------------------------------------------
# Resolution Input Contract (ai-contracts.md §17.2)
# ---------------------------------------------------------------------------
class ResolutionInput(BaseModel):
    """Typed, validated input for the Resolution Agent.

    Aggregates the context produced by Triage, Evidence, and Financial
    Calculation services alongside relevant customer communications and
    merchant policy summaries (ai-contracts.md §17.2, §31).
    Every string field is untrusted business content.
    """

    case_id: str = Field(min_length=1)
    triage_issue_type: str | None = None
    triage_summary: str | None = None
    evidence_finding: str | None = None
    evidence_summary: str | None = None
    verified_collectible_amount_minor: int | None = Field(default=None, ge=0)
    verified_disputed_amount_minor: int | None = Field(default=None, ge=0)
    current_outstanding_amount_minor: int | None = Field(default=None, ge=0)
    observed_facts: tuple[str, ...] = ()
    unresolved_blockers: tuple[str, ...] = ()
    available_evidence_ids: tuple[str, ...] = ()
    policy_context_summary: str | None = None
    current_case_state: str | None = None
    customer_claim: str | None = None
    communications: tuple[CommunicationSnippet, ...] = ()

    model_config = {"frozen": True, "extra": "forbid"}

    @property
    def known_evidence_ids(self) -> frozenset[str]:
        """All valid evidence/communication identifiers supplied to the agent."""
        eids = set(self.available_evidence_ids)
        cids = {comm.communication_id for comm in self.communications}
        return frozenset(eids | cids)


# ---------------------------------------------------------------------------
# Resolution Output Contract (ai-contracts.md §17.5)
# ---------------------------------------------------------------------------
class ResolutionOutput(BaseModel):
    """Structured, validated Resolution Agent recommendation.

    Represents the proposed next recovery action and strategy.
    The model clearly distinguishes:
      - Observed facts/evidence: ``observed_facts``, ``evidence_ids``
      - Inferred reasoning: ``assumptions``, ``unresolved_blockers``, ``reason_summary``
      - Recommendation: ``strategy``, ``action``, ``amount_minor``, ``requires_human_review``

    ``amount_minor`` is an advisory recommendation only; it never becomes
    authoritative financial state without downstream deterministic validation
    (ai-contracts.md §17.5, §20). For non-monetary actions, ``amount_minor``
    must be None (§19).
    """

    strategy: ResolutionStrategy
    action: ResolutionProposalAction
    amount_minor: int | None = Field(default=None, ge=0)
    reason_code: str = Field(min_length=1)
    reason_summary: str = Field(min_length=1)
    confidence: float = Field(ge=0.0, le=1.0, allow_inf_nan=False)
    evidence_ids: tuple[str, ...] = ()
    unresolved_blockers: tuple[str, ...] = ()
    assumptions: tuple[str, ...] = ()
    observed_facts: tuple[str, ...] = ()
    requires_human_review: StrictBool = False

    model_config = {"frozen": True, "extra": "forbid"}

    @field_validator("reason_code", "reason_summary")
    @classmethod
    def _text_must_not_be_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("field must not be empty or whitespace-only")
        return value

    @field_validator(
        "evidence_ids",
        "unresolved_blockers",
        "assumptions",
        "observed_facts",
        mode="after",
    )
    @classmethod
    def _dedupe_tuples(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        seen: list[str] = []
        for item in value:
            if item not in seen:
                seen.append(item)
        return tuple(seen)


# ---------------------------------------------------------------------------
# AI Execution Metadata (ai-contracts.md §7, §29, §30 — maps to AgentRun)
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class ResolutionRunMetadata:
    """Reproducibility/observability metadata for one Resolution Agent run.

    Mirrors the ``agent_runs`` domain record (docs/02-engineering/domain-model §15)
    without persisting. Carries no chain-of-thought — only structured
    metadata (ai-contracts.md §30).
    """

    agent_type: str
    model_name: str
    prompt_version: str
    input_hash: str
    attempts: int
    success: bool
    latency_ms: int | None = None
    error: str | None = None
    token_usage: dict[str, int] | None = None


# ---------------------------------------------------------------------------
# Resolution Agent Result (agent-level outcome — never authorization)
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class ResolutionAgentResult:
    """Result of a bounded Resolution Agent run.

    On SUCCESS, ``output`` holds validated recommendation.
    On NEEDS_HUMAN_REVIEW, ``output`` is None — the agent never creates an
    arbitrary recovery action when model output is invalid/unusable
    (ai-contracts.md §21, §35).
    """

    status: ResolutionOutcomeStatus
    metadata: ResolutionRunMetadata
    output: ResolutionOutput | None = None
    failure_detail: str | None = None
