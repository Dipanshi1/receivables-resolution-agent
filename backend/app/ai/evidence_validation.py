"""Fail-closed validation for untrusted Evidence Agent output.

Implements ai-contracts.md §9.5, §9.6 (schema validation), §27 (semantic validation),
§5 (evidence provenance — the AI must not invent evidence IDs or provenance), and
§15 (forbidden authority/action fields).

The Evidence Agent is advisory and untrusted. Invalid, contradictory, or unverifiable
output must fail closed (§26, §35): it must never proceed to financial calculation
or resolution proposal without human review. This module is the single choke point
that converts an untrusted raw model response into a validated :class:`EvidenceOutput`,
or raises :class:`EvidenceValidationError`.

The validation is deterministic and has no side effects: no AI, no policy, no
financial calculation, no state mutation, no I/O.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

from pydantic import ValidationError

from app.ai.evidence_contracts import EvidenceFindingStatus, EvidenceOutput

# Allowlist of legitimate output fields for EvidenceOutput.
_ALLOWED_OUTPUT_FIELDS: frozenset[str] = frozenset(EvidenceOutput.model_fields)

# Denylist of prohibited field fragments that attempt to smuggle financial
# authority, an executable recovery action, or a state/policy decision into
# evidence output (ai-contracts.md §15, §4, §34).
_PROHIBITED_FIELD_FRAGMENTS: tuple[str, ...] = (
    "collectible",
    "recovered_amount",
    "safely_recoverable",
    "authoriz",
    "approve",
    "concession",
    "execute",
    "razorpay",
    "action",
    "policy_decision",
    "transition",
    "case_state",
    "lock",
    "mark_paid",
)


class EvidenceValidationError(ValueError):
    """Raised when raw Evidence Agent output is malformed, unsafe, or unverifiable.

    Corresponds to the ``AI_OUTPUT_INVALID`` failure path (ai-contracts.md §14, §35).
    """


def validate_evidence_output(
    raw: Any,
    *,
    known_evidence_ids: Iterable[str] = (),
) -> EvidenceOutput:
    """Validate an untrusted raw model output into a safe :class:`EvidenceOutput`.

    Pipeline (ai-contracts.md §26):
      1. Structural: the payload must be a mapping.
      2. Forbidden fields: reject smuggled authority/action/state fields (§15).
      3. Schema: parse via the strict, extra-forbidding contract (§9.5).
      4. Provenance: every cited evidence ID across claims, facts, conflicts,
         and stale evidence must be in ``known_evidence_ids`` (§5).
      5. Semantic consistency:
         - A claim marked SUPPORTED or PARTIALLY_SUPPORTED must cite supporting evidence.
         - An output cannot report finding=SUPPORTED while reporting evidence conflicts.
         - An output marked finding=CONFLICTING must specify at least one conflict.
         - Conflicting evidence must require human review (§12).
         - Missing/insufficient evidence must require human review (§13, §14).

    Args:
        raw: Untrusted structured output from the model (typically a ``dict``).
        known_evidence_ids: Evidence and communication IDs supplied to the agent.
            Any referenced ID outside this set is treated as invented and rejected.

    Returns:
        A validated, frozen :class:`EvidenceOutput`.

    Raises:
        EvidenceValidationError: If output is malformed, contradictory, or unverifiable.
    """
    # 1. Structural check
    if not isinstance(raw, Mapping):
        raise EvidenceValidationError(
            f"evidence output must be a mapping, got {type(raw).__name__}"
        )

    # 2. Forbidden authority / action fields
    _reject_prohibited_fields(raw)

    # 3. Schema + basic constraint validation via strict contract
    try:
        output = EvidenceOutput.model_validate(dict(raw))
    except ValidationError as exc:
        raise EvidenceValidationError(f"malformed evidence output: {exc}") from exc

    # 4. Evidence provenance — no invented IDs across any field
    _reject_invented_evidence_ids(output, known_evidence_ids)

    # 5. Semantic consistency & fail-closed safety checks
    _validate_semantic_consistency(output)

    return output


def _reject_prohibited_fields(raw: Mapping[str, Any]) -> None:
    """Reject any key that names financial authority, action, or state."""
    for key in raw:
        if not isinstance(key, str) or key in _ALLOWED_OUTPUT_FIELDS:
            continue
        lowered = key.lower()
        for fragment in _PROHIBITED_FIELD_FRAGMENTS:
            if fragment in lowered:
                raise EvidenceValidationError(
                    f"prohibited authority/action field '{key}' present in "
                    "evidence output; the Evidence Agent is advisory only"
                )


def _reject_invented_evidence_ids(
    output: EvidenceOutput,
    known_evidence_ids: Iterable[str],
) -> None:
    """Ensure every cited evidence ID was actually supplied (ai-contracts.md §5)."""
    known = set(known_evidence_ids)
    all_cited: list[str] = []

    for claim in output.claims:
        all_cited.extend(claim.evidence_ids)

    for fact in output.facts:
        all_cited.extend(fact.evidence_ids)

    for conflict in output.conflicts:
        all_cited.extend(conflict.evidence_ids)

    all_cited.extend(output.stale_evidence_ids)

    invented = [eid for eid in all_cited if eid not in known]
    if invented:
        raise EvidenceValidationError(
            f"evidence output references unknown evidence IDs {sorted(set(invented))}; "
            "the AI must not invent evidence IDs or provenance"
        )


def _validate_semantic_consistency(output: EvidenceOutput) -> None:
    """Enforce deterministic consistency across findings, claims, and conflicts."""
    # Claim provenance: supported claims must have supporting evidence
    for claim in output.claims:
        if (
            claim.status
            in (
                EvidenceFindingStatus.SUPPORTED,
                EvidenceFindingStatus.PARTIALLY_SUPPORTED,
            )
            and not claim.evidence_ids
        ):
            raise EvidenceValidationError(
                f"claim '{claim.claim}' is marked {claim.status} but cites no "
                "supporting evidence IDs; supported claims must have verifiable provenance"
            )

    # Conflict consistency: finding cannot be SUPPORTED if conflicts exist
    if output.conflicts and output.finding == EvidenceFindingStatus.SUPPORTED:
        raise EvidenceValidationError(
            "contradictory output: finding cannot be SUPPORTED when material "
            "evidence conflicts are reported"
        )

    # Conflict consistency: finding=CONFLICTING requires at least one conflict item
    if output.finding == EvidenceFindingStatus.CONFLICTING and not output.conflicts:
        raise EvidenceValidationError(
            "finding marked CONFLICTING must specify at least one evidence conflict"
        )

    # Conflicting evidence requires human review (ai-contracts.md §12)
    has_conflict = bool(output.conflicts or output.finding == EvidenceFindingStatus.CONFLICTING)
    if has_conflict and not output.requires_human_review:
        raise EvidenceValidationError(
            "conflicting evidence must require human review (requires_human_review=True)"
        )

    # Missing evidence requires human review (ai-contracts.md §13)
    if output.missing_evidence and not output.requires_human_review:
        raise EvidenceValidationError(
            "missing required evidence must require human review (requires_human_review=True)"
        )

    # Insufficient evidence requires human review (ai-contracts.md §14)
    if (
        output.finding == EvidenceFindingStatus.INSUFFICIENT_EVIDENCE
        and not output.requires_human_review
    ):
        raise EvidenceValidationError(
            "insufficient evidence must require human review (requires_human_review=True)"
        )
