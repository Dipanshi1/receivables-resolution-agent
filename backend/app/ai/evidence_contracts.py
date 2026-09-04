"""Strict typed contracts for the Evidence Agent (advisory, untrusted AI layer).

The Evidence Agent interprets business evidence (invoices, purchase orders,
GRNs, contracts, customer communications, etc.) to determine whether customer
claims are supported by evidence and to extract candidate structured facts.
It is advisory and untrusted (docs/02-engineering/ai-contracts.md §9).

It must never:
  - calculate authoritative collectible / recovered / financial amounts,
  - determine collectible / recoverable amount,
  - authorize recovery or grant a concession,
  - evaluate policy authority or approve human approval,
  - change RecoveryCase state or transition the state machine,
  - execute Razorpay / mark a payment successful,
  - mutate authoritative financial state, or bypass deterministic controls.

These contracts encode that boundary structurally:
  - OUTPUT carries no authoritative financial amount, no action, and no
    authority field; ``extra="forbid"`` rejects any injected field (§15);
  - all business content on the INPUT is treated as untrusted data (§3.2, §24);
  - model confidence is recorded but is never authorization (§6, §34);
  - every material claim, fact, and conflict must cite evidence IDs present in
    the supplied input (§5, §9.5); the AI must never invent evidence IDs.

Reference: docs/02-engineering/ai-contracts.md §5, §6, §7, §9, §10, §12, §13, §15;
           docs/02-engineering/domain-model.md §13, §14;
           docs/03-evaluation/dataset-spec.md §21, §23, §28, §31, §32.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field, StrictBool, field_validator

from app.ai.triage_contracts import CommunicationSnippet
from app.domain.enums import EvidenceType

# ---------------------------------------------------------------------------
# Prompt / contract version (recorded on every AgentRun — ai-contracts.md §29)
# ---------------------------------------------------------------------------
EVIDENCE_PROMPT_VERSION = "evidence-v1"


# ---------------------------------------------------------------------------
# Evidence Finding Status (ai-contracts.md §9.4; domain-model.md §14)
# ---------------------------------------------------------------------------
class EvidenceFindingStatus(StrEnum):
    """Overall assessment status of the evidence regarding customer objections.

    Mirrors the five authoritative evidence outcome categories in
    docs/02-engineering/ai-contracts.md §9.4 and state-machine.md §7.
    """

    SUPPORTED = "SUPPORTED"
    PARTIALLY_SUPPORTED = "PARTIALLY_SUPPORTED"
    UNSUPPORTED = "UNSUPPORTED"
    CONFLICTING = "CONFLICTING"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"


# ---------------------------------------------------------------------------
# Fact Kind (observed fact vs inference)
# ---------------------------------------------------------------------------
class FactKind(StrEnum):
    """Classification of an extracted fact as directly observed vs inferred."""

    OBSERVED = "OBSERVED"
    INFERENCE = "INFERENCE"


# ---------------------------------------------------------------------------
# Evidence Outcome Status (agent-level run outcome — §14, §35)
# ---------------------------------------------------------------------------
class EvidenceOutcomeStatus(StrEnum):
    """Outcome of a bounded Evidence Agent run."""

    SUCCESS = "SUCCESS"
    NEEDS_HUMAN_REVIEW = "NEEDS_HUMAN_REVIEW"


# ---------------------------------------------------------------------------
# Evidence Item Input Contract (ai-contracts.md §9.2; domain-model.md §13)
# ---------------------------------------------------------------------------
class EvidenceItem(BaseModel):
    """A business evidence record supplied to the Evidence Agent.

    Every piece of business evidence (documents, ERP records, emails) is
    untrusted business data (ai-contracts.md §3.2, §24). The Evidence Agent
    is permitted to cite only the ``evidence_id`` values supplied here.
    """

    evidence_id: str = Field(min_length=1)
    evidence_type: EvidenceType
    source: str = Field(default="UNKNOWN", min_length=1)
    external_reference: str | None = None
    content: str | None = None
    structured_data: dict[str, Any] | None = None
    timestamp: str | None = None
    is_stale: bool = False
    summary: str | None = None

    model_config = {"frozen": True, "extra": "forbid"}


class EvidenceInput(BaseModel):
    """Typed, validated input for the Evidence Agent.

    Contains the relevant business evidence items, communications, and dispute
    context needed for evidence assessment (ai-contracts.md §9.2, §31).
    Every string field is untrusted business content.
    """

    case_id: str = Field(min_length=1)
    dispute_summary: str | None = None
    customer_claim: str | None = None
    claimed_amount_minor: int | None = Field(default=None, ge=0)
    evidence_items: tuple[EvidenceItem, ...] = ()
    communications: tuple[CommunicationSnippet, ...] = ()
    prior_recovery_context: str | None = None

    model_config = {"frozen": True, "extra": "forbid"}

    @property
    def known_evidence_ids(self) -> frozenset[str]:
        """All valid evidence/communication identifiers supplied to the agent.

        In the benchmark dataset, both evidence items and communications have
        stable identifiers (e.g. GRN-1194, EMAIL-291) that can be cited as
        provenance (dataset-spec.md §21, §32).
        """
        eids = {item.evidence_id for item in self.evidence_items}
        cids = {comm.communication_id for comm in self.communications}
        return frozenset(eids | cids)


# ---------------------------------------------------------------------------
# Structured Evidence Findings Output Sub-Models (ai-contracts.md §9.5, §10, §12)
# ---------------------------------------------------------------------------
class ClaimAssessment(BaseModel):
    """Assessment of an individual customer claim or objection against evidence.

    Must cite the evidence items supporting or refuting the claim. Citing unknown
    evidence IDs is strictly forbidden (ai-contracts.md §5).
    """

    claim: str = Field(min_length=1)
    status: EvidenceFindingStatus
    evidence_ids: tuple[str, ...] = ()
    reasoning: str | None = None
    is_inferred: StrictBool = False

    model_config = {"frozen": True, "extra": "forbid"}

    @field_validator("claim")
    @classmethod
    def _claim_must_not_be_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("claim must not be empty or whitespace-only")
        return value

    @field_validator("evidence_ids", mode="after")
    @classmethod
    def _dedupe_evidence_ids(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        seen: list[str] = []
        for item in value:
            if item not in seen:
                seen.append(item)
        return tuple(seen)


class ExtractedFact(BaseModel):
    """Candidate structured fact extracted from evidence (ai-contracts.md §10).

    Candidate facts (e.g. quantity_invoiced=100, quantity_delivered=90,
    unit_price=900000) are extracted for downstream deterministic financial
    calculation. They are candidate facts, NOT authoritative calculations.
    Must cite at least one supporting evidence ID for provenance (§5).
    """

    name: str = Field(min_length=1)
    value: str | int | float | bool
    evidence_ids: tuple[str, ...] = Field(min_length=1)
    kind: FactKind = FactKind.OBSERVED
    description: str | None = None

    model_config = {"frozen": True, "extra": "forbid"}

    @field_validator("name")
    @classmethod
    def _name_must_not_be_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("name must not be empty or whitespace-only")
        return value

    @field_validator("evidence_ids", mode="after")
    @classmethod
    def _dedupe_evidence_ids(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        seen: list[str] = []
        for item in value:
            if item not in seen:
                seen.append(item)
        return tuple(seen)


class EvidenceConflict(BaseModel):
    """Contradictory evidence detected across records (ai-contracts.md §12).

    If material evidence contains unresolved contradictions, the system must
    not silently pick one source as truth. It records the conflicting field,
    the conflicting values, and the conflicting evidence IDs.
    Must cite at least two evidence IDs representing the conflicting sources.
    """

    field: str = Field(min_length=1)
    values: tuple[str | int | float | bool, ...] = ()
    evidence_ids: tuple[str, ...] = Field(min_length=2)
    description: str | None = None

    model_config = {"frozen": True, "extra": "forbid"}

    @field_validator("field")
    @classmethod
    def _field_must_not_be_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("field must not be empty or whitespace-only")
        return value

    @field_validator("evidence_ids", mode="after")
    @classmethod
    def _dedupe_evidence_ids(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        seen: list[str] = []
        for item in value:
            if item not in seen:
                seen.append(item)
        return tuple(seen)


# ---------------------------------------------------------------------------
# Evidence Agent Output Contract (ai-contracts.md §9.5)
# ---------------------------------------------------------------------------
class EvidenceOutput(BaseModel):
    """Structured, validated Evidence Agent output.

    The model is frozen and forbids extra fields (``extra="forbid"``) so any
    attempt to inject authoritative financial amounts (e.g. ``collectible_amount``,
    ``recovered_amount``), executable actions, or policy authority is rejected
    at construction (ai-contracts.md §15).

    Every evidence reference must have provenance in the supplied input (§5).
    """

    finding: EvidenceFindingStatus
    summary: str = Field(min_length=1)
    confidence: float = Field(ge=0.0, le=1.0, allow_inf_nan=False)
    claims: tuple[ClaimAssessment, ...] = ()
    facts: tuple[ExtractedFact, ...] = ()
    conflicts: tuple[EvidenceConflict, ...] = ()
    missing_evidence: tuple[EvidenceType, ...] = ()
    stale_evidence_ids: tuple[str, ...] = ()
    requires_human_review: StrictBool = False

    model_config = {"frozen": True, "extra": "forbid"}

    @field_validator("summary")
    @classmethod
    def _summary_must_not_be_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("summary must not be empty or whitespace-only")
        return value

    @field_validator("missing_evidence", "stale_evidence_ids", mode="after")
    @classmethod
    def _dedupe_tuples(cls, value: tuple) -> tuple:
        seen: list = []
        for item in value:
            if item not in seen:
                seen.append(item)
        return tuple(seen)


# ---------------------------------------------------------------------------
# AI Execution Metadata (ai-contracts.md §7, §29, §30 — maps to AgentRun)
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class EvidenceRunMetadata:
    """Reproducibility/observability metadata for one Evidence Agent run.

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
# Evidence Agent Result (agent-level outcome — never authorization)
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class EvidenceAgentResult:
    """Result of a bounded Evidence Agent run.

    On SUCCESS, ``output`` holds validated evidence findings.
    On NEEDS_HUMAN_REVIEW, ``output`` is None — the agent never fabricates facts
    or assumptions when model output is invalid/unusable (ai-contracts.md §14, §15, §35).
    """

    status: EvidenceOutcomeStatus
    metadata: EvidenceRunMetadata
    output: EvidenceOutput | None = None
    failure_detail: str | None = None
