"""Fail-closed validation for untrusted Resolution Agent output.

Implements ai-contracts.md §17.5, §19, §20 (validation pipeline), §5 (evidence provenance —
the AI must not invent evidence IDs), §22 (forbidden authority/action fields), and
§34 (AI output is not authorization).

The Resolution Agent is advisory and untrusted. Invalid, contradictory, or unverifiable
recommendations must fail closed (§21, §35): they must never create an executable
Recovery Action or bypass downstream Policy Engine, State Machine, or human approval.
This module is the single choke point that converts an untrusted raw model response
into a validated :class:`ResolutionOutput`, or raises :class:`ResolutionValidationError`.

The validation is deterministic and has no side effects: no AI, no policy, no
financial calculation, no state mutation, no I/O.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

from pydantic import ValidationError

from app.ai.resolution_contracts import (
    ResolutionOutput,
    ResolutionProposalAction,
    ResolutionStrategy,
)

# Allowlist of legitimate output fields for ResolutionOutput.
_ALLOWED_OUTPUT_FIELDS: frozenset[str] = frozenset(ResolutionOutput.model_fields)

# Denylist of prohibited field fragments that attempt to smuggle financial
# authority, an executable recovery action, or a state/policy decision into
# resolution output (ai-contracts.md §22, §4, §34).
_PROHIBITED_FIELD_FRAGMENTS: tuple[str, ...] = (
    "collectible",
    "recovered_amount",
    "safely_recoverable",
    "authoriz",
    "approve",
    "concession_granted",
    "execute",
    "razorpay",
    "policy_decision",
    "transition",
    "case_state",
    "legal_lock",
    "mark_paid",
    "payment_id",
    "order_id",
)

# Actions that directly recommend monetary recovery.
_MONETARY_RECOVERY_ACTIONS: frozenset[ResolutionProposalAction] = frozenset(
    {
        ResolutionProposalAction.CREATE_FULL_RECOVERY,
        ResolutionProposalAction.CREATE_PARTIAL_RECOVERY,
    }
)

# Actions that represent escalation to human/legal channels.
_ESCALATION_ACTIONS: frozenset[ResolutionProposalAction] = frozenset(
    {
        ResolutionProposalAction.ESCALATE_HUMAN,
        ResolutionProposalAction.ESCALATE_LEGAL,
    }
)


class ResolutionValidationError(ValueError):
    """Raised when raw Resolution Agent output is malformed, unsafe, or unverifiable.

    Corresponds to the ``AI_OUTPUT_INVALID`` failure path (ai-contracts.md §21, §35).
    """


def validate_resolution_output(
    raw: Any,
    *,
    known_evidence_ids: Iterable[str] = (),
) -> ResolutionOutput:
    """Validate an untrusted raw model output into a safe :class:`ResolutionOutput`.

    Pipeline (ai-contracts.md §26):
      1. Structural: the payload must be a mapping.
      2. Forbidden fields: reject smuggled authority/action/state fields (§22).
      3. Schema: parse via the strict, extra-forbidding contract (§17.5).
      4. Provenance: every cited evidence ID must be in ``known_evidence_ids`` (§5).
      5. Monetary vs non-monetary action consistency (§17.5, §19):
         - Monetary recovery actions require positive ``amount_minor`` and evidence citations.
         - Non-monetary actions require ``amount_minor=None``.
      6. Escalation and blocker consistency:
         - Escalation actions/strategies require ``requires_human_review=True``.
         - ``CREATE_FULL_RECOVERY`` cannot be recommended when unresolved blockers exist.

    Args:
        raw: Untrusted structured output from the model (typically a ``dict``).
        known_evidence_ids: Evidence and communication IDs supplied in context.
            Any referenced ID outside this set is treated as invented and rejected.

    Returns:
        A validated, frozen :class:`ResolutionOutput`.

    Raises:
        ResolutionValidationError: If output is malformed, contradictory, or unverifiable.
    """
    # 1. Structural check
    if not isinstance(raw, Mapping):
        raise ResolutionValidationError(
            f"resolution output must be a mapping, got {type(raw).__name__}"
        )

    # 2. Forbidden authority / execution fields
    _reject_prohibited_fields(raw)

    # 3. Schema + basic constraint validation via strict contract
    try:
        output = ResolutionOutput.model_validate(dict(raw))
    except ValidationError as exc:
        raise ResolutionValidationError(f"malformed resolution output: {exc}") from exc

    # 4. Evidence provenance — no invented IDs
    _reject_invented_evidence_ids(output, known_evidence_ids)

    # 5. Monetary vs non-monetary action consistency
    _validate_monetary_consistency(output)

    # 6. Escalation and blocker consistency
    _validate_escalation_and_blockers(output)

    return output


def _reject_prohibited_fields(raw: Mapping[str, Any]) -> None:
    """Reject any key that names financial authority, action execution, or state."""
    for key in raw:
        if not isinstance(key, str) or key in _ALLOWED_OUTPUT_FIELDS:
            continue
        lowered = key.lower()
        for fragment in _PROHIBITED_FIELD_FRAGMENTS:
            if fragment in lowered:
                raise ResolutionValidationError(
                    f"prohibited authority/action field '{key}' present in "
                    "resolution output; the Resolution Agent is advisory only"
                )


def _reject_invented_evidence_ids(
    output: ResolutionOutput,
    known_evidence_ids: Iterable[str],
) -> None:
    """Ensure every cited evidence ID was actually supplied (ai-contracts.md §5)."""
    known = set(known_evidence_ids)
    invented = [eid for eid in output.evidence_ids if eid not in known]
    if invented:
        raise ResolutionValidationError(
            f"resolution output references unknown evidence IDs {sorted(set(invented))}; "
            "the AI must not invent evidence IDs or provenance"
        )


def _validate_monetary_consistency(output: ResolutionOutput) -> None:
    """Enforce rules governing monetary vs non-monetary recovery actions."""
    if output.action in _MONETARY_RECOVERY_ACTIONS:
        if output.amount_minor is None or output.amount_minor <= 0:
            raise ResolutionValidationError(
                f"recovery action '{output.action.value}' requires a positive amount_minor "
                f"recommendation, got {output.amount_minor}"
            )
        if not output.evidence_ids:
            raise ResolutionValidationError(
                f"recovery action '{output.action.value}' must cite at least one supporting "
                "evidence ID for provenance"
            )
    else:
        # Non-monetary action (ai-contracts.md §19: amount_minor must be None)
        if output.amount_minor is not None:
            raise ResolutionValidationError(
                f"non-monetary action '{output.action.value}' must have amount_minor=None, "
                f"got {output.amount_minor}"
            )


def _validate_escalation_and_blockers(output: ResolutionOutput) -> None:
    """Enforce consistency regarding human escalation and unresolved blockers."""
    if output.action in _ESCALATION_ACTIONS and not output.requires_human_review:
        raise ResolutionValidationError(
            f"escalation action '{output.action.value}' must require human review "
            "(requires_human_review=True)"
        )

    if (
        output.strategy
        in (ResolutionStrategy.HUMAN_ESCALATION, ResolutionStrategy.LEGAL_ESCALATION)
        and not output.requires_human_review
    ):
        raise ResolutionValidationError(
            f"escalation strategy '{output.strategy.value}' must require human review "
            "(requires_human_review=True)"
        )

    if (
        output.unresolved_blockers
        and output.action == ResolutionProposalAction.CREATE_FULL_RECOVERY
    ):
        raise ResolutionValidationError(
            "contradictory output: cannot recommend CREATE_FULL_RECOVERY when "
            "unresolved blockers exist"
        )
