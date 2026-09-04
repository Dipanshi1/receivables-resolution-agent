"""AI reasoning layer for the Receivables Resolution Agent.

This package contains the *advisory, untrusted* AI components. Per
docs/02-engineering/ai-contracts.md, the AI layer interprets and recommends; it
never calculates authoritative financial amounts, authorizes recovery,
evaluates policy, approves human approval, transitions case state, executes
payments, or mutates authoritative financial state. The deterministic services
in ``app.services`` own all of that.

Phase 4A implements only the Triage Agent (semantic issue classification).
"""

from __future__ import annotations

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
    "TRIAGE_PROMPT_VERSION",
    "CommunicationSnippet",
    "EvidenceRef",
    "RawModelResponse",
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
    "build_triage_prompt",
    "compute_triage_input_hash",
    "validate_triage_output",
]
