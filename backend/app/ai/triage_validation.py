"""Fail-closed validation for untrusted Triage Agent output.

Implements ai-contracts.md §8.6 (schema validation), §27 (semantic validation),
§5 (evidence provenance — the AI must not invent evidence IDs), and §8.8
(forbidden authority/action fields).

Invalid or unsafe output must fail closed (§26, §35): it must never proceed to
financial resolution. This module is the single choke point that converts an
untrusted raw model response into a validated :class:`TriageOutput`, or raises
:class:`TriageValidationError`.

The validation is deterministic and has no side effects: no AI, no policy, no
financial calculation, no state mutation, no I/O.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

from pydantic import ValidationError

from app.ai.triage_contracts import TriageOutput

# Allowlist of legitimate output fields (anything else is rejected).
_ALLOWED_OUTPUT_FIELDS: frozenset[str] = frozenset(TriageOutput.model_fields)

# Denylist of substrings that mark an attempt to smuggle financial authority,
# an executable action, or a state/authorization decision into triage output
# (ai-contracts.md §8.8, §4, §34). Any extra key containing one of these yields
# a precise, security-specific error. ``extra="forbid"`` on TriageOutput is the
# robust allowlist backstop; this denylist exists for clarity/traceability.
_PROHIBITED_FIELD_FRAGMENTS: tuple[str, ...] = (
    "amount",
    "collectible",
    "recover",
    "authoriz",
    "approve",
    "concession",
    "payment",
    "paid",
    "balance",
    "state",
    "execute",
    "razorpay",
    "action",
    "policy",
    "transition",
    "lock",
)


class TriageValidationError(ValueError):
    """Raised when raw Triage output is malformed or unsafe.

    Corresponds to the ``AI_OUTPUT_INVALID`` failure path (ai-contracts.md §8.7).
    """


def validate_triage_output(
    raw: Any,
    *,
    known_evidence_ids: Iterable[str] = (),
) -> TriageOutput:
    """Validate an untrusted raw model output into a safe :class:`TriageOutput`.

    Pipeline (ai-contracts.md §26):
      1. Structural: the payload must be a mapping.
      2. Forbidden fields: reject smuggled authority/action/state fields (§8.8).
      3. Schema: parse via the strict, extra-forbidding contract (§8.6).
      4. Provenance: every ``supporting_evidence_ids`` entry must be a known
         evidence ID — the AI must not invent IDs (§5).

    Args:
        raw: Untrusted structured output from the model (typically a ``dict``).
        known_evidence_ids: Evidence IDs supplied to the agent. Any referenced
            ID outside this set is treated as invented and rejected.

    Returns:
        A validated, frozen :class:`TriageOutput`.

    Raises:
        TriageValidationError: If the output is malformed or unsafe. The caller
            must fail closed and must not proceed to financial resolution.
    """
    # 1. Structural check
    if not isinstance(raw, Mapping):
        raise TriageValidationError(
            f"triage output must be a mapping, got {type(raw).__name__}"
        )

    # 2. Forbidden authority/action fields (defense-in-depth over extra=forbid)
    _reject_prohibited_fields(raw)

    # 3. Schema + semantic validation via the strict contract
    try:
        output = TriageOutput.model_validate(dict(raw))
    except ValidationError as exc:
        raise TriageValidationError(f"malformed triage output: {exc}") from exc

    # 4. Evidence provenance — no invented IDs
    _reject_invented_evidence_ids(output, known_evidence_ids)

    return output


def _reject_prohibited_fields(raw: Mapping[str, Any]) -> None:
    """Reject any extra key that names financial authority, action, or state."""
    for key in raw:
        if not isinstance(key, str) or key in _ALLOWED_OUTPUT_FIELDS:
            continue
        lowered = key.lower()
        for fragment in _PROHIBITED_FIELD_FRAGMENTS:
            if fragment in lowered:
                raise TriageValidationError(
                    f"prohibited authority/action field '{key}' present in "
                    "triage output; the Triage Agent is advisory only"
                )


def _reject_invented_evidence_ids(
    output: TriageOutput,
    known_evidence_ids: Iterable[str],
) -> None:
    """Ensure every cited evidence ID was actually supplied (ai-contracts.md §5)."""
    known = set(known_evidence_ids)
    invented = [eid for eid in output.supporting_evidence_ids if eid not in known]
    if invented:
        raise TriageValidationError(
            f"triage output references unknown evidence IDs {invented}; "
            "the AI must not invent evidence IDs"
        )
