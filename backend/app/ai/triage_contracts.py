"""Strict typed contracts for the Triage Agent (advisory, untrusted AI layer).

The Triage Agent performs *semantic classification only*: it determines the
primary reason a receivable is overdue or blocked. It is advisory and untrusted
(docs/02-engineering/ai-contracts.md §8). It must never:

  - calculate authoritative collectible / recovered / financial amounts,
  - authorize recovery or grant a concession,
  - evaluate policy authority or approve human approval,
  - change RecoveryCase state or transition the state machine,
  - execute Razorpay / mark a payment successful,
  - mutate authoritative financial state, or bypass deterministic controls.

These contracts encode that boundary structurally:
  - the OUTPUT carries no monetary amount, no action, and no authority field;
    ``extra="forbid"`` rejects any such injected field (§8.8);
  - all business content on the INPUT is treated as untrusted data (§3.2, §24);
  - model confidence is recorded but is never authorization (§6, §34).

Reference: docs/02-engineering/ai-contracts.md §5, §6, §7, §8;
           docs/03-evaluation/dataset-spec.md §28 (safety flag vocabulary).
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from pydantic import BaseModel, Field, StrictBool, field_validator

from app.domain.enums import EvidenceType, IssueType, OutreachChannel, OutreachDirection

# ---------------------------------------------------------------------------
# Prompt / contract version (recorded on every AgentRun — ai-contracts.md §29)
# ---------------------------------------------------------------------------
TRIAGE_PROMPT_VERSION = "triage-v1"


# ---------------------------------------------------------------------------
# Triage Risk Flags (closed vocabulary — ai-contracts.md §8.6 "known values")
# ---------------------------------------------------------------------------
class TriageRiskFlag(StrEnum):
    """Risk signals the Triage Agent may surface from semantic reading.

    This is a strict closed vocabulary. Only signals that are detectable at
    triage time (from case/invoice/dispute context and customer communications)
    and grounded in the authoritative docs are included. Deterministic-layer
    flags (policy limits, touchpoint limits, stale proposals, payment integrity)
    are intentionally excluded — those belong to the Policy Engine, State
    Machine, and payment reconciliation, not to advisory triage.
    """

    # ai-contracts.md §8.5 example; explicit legal/court/lawyer language.
    LEGAL_ESCALATION = "LEGAL_ESCALATION"
    # ai-contracts.md §24; customer content attempting to instruct the system.
    PROMPT_INJECTION = "PROMPT_INJECTION"
    # dataset-spec.md §28; customer claims contradict each other / stated facts.
    EVIDENCE_CONFLICT = "EVIDENCE_CONFLICT"
    # dataset-spec.md §28; evidence required for safe resolution appears absent.
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"
    # safety-tests.md S05.04; customer alleges the invoice is fraudulent.
    FRAUD_ALLEGATION = "FRAUD_ALLEGATION"
    # safety-tests.md S05.03; explicit "do not contact us again" request.
    EXPLICIT_STOP_CONTACT = "EXPLICIT_STOP_CONTACT"


# ---------------------------------------------------------------------------
# Triage outcome status (agent-level result of a bounded run — §8.7, §35)
# ---------------------------------------------------------------------------
class TriageOutcomeStatus(StrEnum):
    """Outcome of a bounded Triage Agent run."""

    SUCCESS = "SUCCESS"
    NEEDS_HUMAN_REVIEW = "NEEDS_HUMAN_REVIEW"


# ---------------------------------------------------------------------------
# Triage Input Contract (untrusted business context — ai-contracts.md §8.2)
# ---------------------------------------------------------------------------
class EvidenceRef(BaseModel):
    """A known evidence/context record the Triage Agent is permitted to cite.

    ``evidence_id`` must correspond to a real application record. The Triage
    Agent may only reference these IDs; it must never invent new ones
    (ai-contracts.md §5).
    """

    evidence_id: str = Field(min_length=1)
    evidence_type: EvidenceType
    summary: str | None = None

    model_config = {"frozen": True, "extra": "forbid"}


class CommunicationSnippet(BaseModel):
    """An untrusted customer/business communication supplied as triage context.

    ``content`` is UNTRUSTED business data (ai-contracts.md §3.2, §24).
    Instructions embedded in this text must never be treated as system
    instructions; the prompt builder wraps it in a clearly delimited
    untrusted-content block.
    """

    communication_id: str = Field(min_length=1)
    channel: OutreachChannel | None = None
    direction: OutreachDirection | None = None
    content: str = Field(min_length=1)

    model_config = {"frozen": True, "extra": "forbid"}


class TriageInput(BaseModel):
    """Typed, validated input for the Triage Agent.

    Contains only the minimum contextual data necessary for issue
    classification (ai-contracts.md §8.2, §31 data minimization). Every free
    text field is untrusted business content. No monetary amounts are supplied
    here — triage does not reason about authoritative financial values.
    """

    case_id: str = Field(min_length=1)
    case_summary: str = Field(min_length=1)
    invoice_summary: str | None = None
    customer_summary: str | None = None
    payment_status: str | None = None
    communications: tuple[CommunicationSnippet, ...] = ()
    available_evidence: tuple[EvidenceRef, ...] = ()
    prior_recovery_summary: str | None = None

    model_config = {"frozen": True, "extra": "forbid"}


# ---------------------------------------------------------------------------
# Triage Output Contract (ai-contracts.md §8.5 / §8.6)
# ---------------------------------------------------------------------------
class TriageOutput(BaseModel):
    """Structured, validated Triage Agent output.

    Fields mirror ai-contracts.md §8.5 plus two advisory traceability fields
    required by the Phase 4A scope ("explicitly identify missing/insufficient
    evidence" and "keep claims traceable to supplied evidence/context"):

      - ``missing_evidence``: evidence types that appear absent (advisory only).
      - ``supporting_evidence_ids``: supplied evidence IDs the classification
        draws on. Validated to be a subset of the supplied IDs (§5).

    The model is frozen and forbids extra fields, so any injected authority or
    action field (e.g. ``amount_minor``, ``action``, ``authorized``,
    ``case_state``) is rejected at construction (§8.8). ``confidence`` is
    recorded for routing/observability only — it is never authorization
    (§6, §34).
    """

    issue_type: IssueType
    confidence: float = Field(ge=0.0, le=1.0, allow_inf_nan=False)
    summary: str = Field(min_length=1)
    requires_evidence_analysis: StrictBool
    risk_flags: tuple[TriageRiskFlag, ...] = ()
    missing_evidence: tuple[EvidenceType, ...] = ()
    supporting_evidence_ids: tuple[str, ...] = ()

    model_config = {"frozen": True, "extra": "forbid"}

    @field_validator("summary")
    @classmethod
    def _summary_must_not_be_blank(cls, value: str) -> str:
        """ai-contracts.md §8.6: summary must be non-empty (and not whitespace)."""
        if not value.strip():
            raise ValueError("summary must not be empty or whitespace-only")
        return value

    @field_validator(
        "risk_flags", "missing_evidence", "supporting_evidence_ids", mode="after"
    )
    @classmethod
    def _dedupe_preserving_order(cls, value: tuple) -> tuple:
        """Collapse duplicates deterministically without silently reordering."""
        seen: list = []
        for item in value:
            if item not in seen:
                seen.append(item)
        return tuple(seen)


# ---------------------------------------------------------------------------
# AI Execution Metadata (ai-contracts.md §7, §29, §30 — maps to AgentRun)
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class TriageRunMetadata:
    """Reproducibility/observability metadata for one Triage Agent run.

    Mirrors the ``agent_runs`` domain record (docs/02-engineering/domain-model
    §15) without persisting. Carries no chain-of-thought — only structured
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
# Triage Agent Result (agent-level outcome — never authorization)
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class TriageAgentResult:
    """Result of a bounded Triage Agent run.

    On SUCCESS, ``output`` holds validated classification. On
    NEEDS_HUMAN_REVIEW, ``output`` is None — the agent never guesses an issue
    type when the model output is invalid/unusable (ai-contracts.md §8.7, §35).
    """

    status: TriageOutcomeStatus
    metadata: TriageRunMetadata
    output: TriageOutput | None = None
    failure_detail: str | None = None
