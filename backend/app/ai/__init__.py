"""AI reasoning layer for the Receivables Resolution Agent.

This package contains the *advisory, untrusted* AI components. Per
docs/02-engineering/ai-contracts.md, the AI layer interprets and recommends; it
never calculates authoritative financial amounts, authorizes recovery,
evaluates policy, approves human approval, transitions case state, executes
payments, or mutates authoritative financial state. The deterministic services
in ``app.services`` own all of that.

Phase 4A implements the Triage Agent (semantic issue classification).
Phase 4B implements the Evidence Agent (evidence interpretation & fact extraction).
Phase 4C implements the Resolution Agent (resolution strategy & action recommendation).
"""

from __future__ import annotations

from app.ai.evidence_agent import (
    EvidenceAgent,
    EvidenceModelPort,
    EvidencePrompt,
    build_evidence_prompt,
    compute_evidence_input_hash,
)
from app.ai.evidence_contracts import (
    EVIDENCE_PROMPT_VERSION,
    ClaimAssessment,
    EvidenceAgentResult,
    EvidenceConflict,
    EvidenceFindingStatus,
    EvidenceInput,
    EvidenceItem,
    EvidenceOutcomeStatus,
    EvidenceOutput,
    EvidenceRunMetadata,
    ExtractedFact,
    FactKind,
)
from app.ai.evidence_validation import (
    EvidenceValidationError,
    validate_evidence_output,
)
from app.ai.resolution_agent import (
    ResolutionAgent,
    ResolutionModelPort,
    ResolutionPrompt,
    build_resolution_prompt,
    compute_resolution_input_hash,
)
from app.ai.resolution_contracts import (
    RESOLUTION_PROMPT_VERSION,
    ResolutionAgentResult,
    ResolutionInput,
    ResolutionOutcomeStatus,
    ResolutionOutput,
    ResolutionReasonCode,
    ResolutionRunMetadata,
    ResolutionStrategy,
)
from app.ai.resolution_validation import (
    ResolutionValidationError,
    validate_resolution_output,
)
from app.ai.triage_agent import (
    DEFAULT_MAX_ATTEMPTS,
    RawModelResponse,
    TriageAgent,
    TriageModelPort,
    TriagePrompt,
    build_triage_prompt,
    compute_triage_input_hash,
)
from app.ai.triage_contracts import (
    TRIAGE_PROMPT_VERSION,
    CommunicationSnippet,
    EvidenceRef,
    TriageAgentResult,
    TriageInput,
    TriageOutcomeStatus,
    TriageOutput,
    TriageRiskFlag,
    TriageRunMetadata,
)
from app.ai.triage_validation import TriageValidationError, validate_triage_output

__all__ = [
    "DEFAULT_MAX_ATTEMPTS",
    "EVIDENCE_PROMPT_VERSION",
    "RESOLUTION_PROMPT_VERSION",
    "TRIAGE_PROMPT_VERSION",
    "ClaimAssessment",
    "CommunicationSnippet",
    "EvidenceAgent",
    "EvidenceAgentResult",
    "EvidenceConflict",
    "EvidenceFindingStatus",
    "EvidenceInput",
    "EvidenceItem",
    "EvidenceModelPort",
    "EvidenceOutcomeStatus",
    "EvidenceOutput",
    "EvidencePrompt",
    "EvidenceRef",
    "EvidenceRunMetadata",
    "EvidenceValidationError",
    "ExtractedFact",
    "FactKind",
    "RawModelResponse",
    "ResolutionAgent",
    "ResolutionAgentResult",
    "ResolutionInput",
    "ResolutionModelPort",
    "ResolutionOutcomeStatus",
    "ResolutionOutput",
    "ResolutionPrompt",
    "ResolutionReasonCode",
    "ResolutionRunMetadata",
    "ResolutionStrategy",
    "ResolutionValidationError",
    "TriageAgent",
    "TriageAgentResult",
    "TriageInput",
    "TriageModelPort",
    "TriageOutcomeStatus",
    "TriageOutput",
    "TriagePrompt",
    "TriageRiskFlag",
    "TriageRunMetadata",
    "TriageValidationError",
    "build_evidence_prompt",
    "build_resolution_prompt",
    "build_triage_prompt",
    "compute_evidence_input_hash",
    "compute_resolution_input_hash",
    "compute_triage_input_hash",
    "validate_evidence_output",
    "validate_resolution_output",
    "validate_triage_output",
]
