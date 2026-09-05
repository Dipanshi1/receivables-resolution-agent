import hashlib
import json
import logging
from dataclasses import asdict, dataclass
from typing import Any, Protocol

from app.domain.enums import RecoveryActionType, RecoveryCaseStatus
from app.services.payment_provider import PaymentLinkRequest, PaymentProvider
from app.services.razorpay_adapter import RazorpayProviderError

logger = logging.getLogger(__name__)


class ExecutionGuardError(Exception):
    """Raised when an execution fails a deterministic guard check."""

    pass


@dataclass(frozen=True)
class ExecutionInput:
    action_id: str
    action_type: RecoveryActionType
    amount_minor: int | None
    currency: str
    case_id: str
    merchant_id: str
    invoice_id: str

    current_case_state: RecoveryCaseStatus
    is_legal_locked: bool
    is_automation_locked: bool

    verified_collectible_amount_minor: int
    safely_recoverable_amount_minor: int
    autonomous_authority_minor: int

    is_policy_approved: bool
    has_valid_human_approval: bool
    action_already_executed: bool

    customer_name: str | None = None
    customer_email: str | None = None
    customer_contact: str | None = None


@dataclass(frozen=True)
class ExecutionResult:
    action_id: str
    success: bool
    provider_id: str | None
    provider_reference: str | None
    payment_link_url: str | None
    error_message: str | None


class ExecutionIdempotencyStore(Protocol):
    def get(self, key: str) -> dict[str, Any] | None: ...
    def set(self, key: str, request_hash: str, result: ExecutionResult) -> None: ...


class _InMemoryExecutionIdempotencyStore:
    def __init__(self) -> None:
        self._store: dict[str, dict[str, Any]] = {}

    def get(self, key: str) -> dict[str, Any] | None:
        return self._store.get(key)

    def set(self, key: str, request_hash: str, result: ExecutionResult) -> None:
        self._store[key] = {
            "request_hash": request_hash,
            "result": asdict(result),
        }


class RecoveryExecutor:
    """Deterministic execution boundary for recovery actions."""

    def __init__(
        self,
        payment_provider: PaymentProvider,
        idempotency_store: ExecutionIdempotencyStore | None = None,
    ):
        self._provider = payment_provider
        self._idempotency_store = idempotency_store or _InMemoryExecutionIdempotencyStore()

    def _compute_request_hash(self, inputs: ExecutionInput) -> str:
        data = asdict(inputs)
        # Convert enums to strings for stable serialization
        if hasattr(data.get("action_type"), "value"):
            data["action_type"] = data["action_type"].value
        if hasattr(data.get("current_case_state"), "value"):
            data["current_case_state"] = data["current_case_state"].value

        canonical_json = json.dumps(data, sort_keys=True)
        return hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()

    def _validate_execution_guards(self, inputs: ExecutionInput) -> None:
        """Enforces deterministic rules before allowing execution."""
        if inputs.action_type not in (
            RecoveryActionType.CREATE_PAYMENT_LINK,
            RecoveryActionType.CREATE_PARTIAL_RECOVERY,
        ):
            raise ExecutionGuardError(
                f"Action type {inputs.action_type} is not executable via payment provider"
            )

        if inputs.amount_minor is None or inputs.amount_minor <= 0:
            raise ExecutionGuardError("Execution amount must be strictly positive")

        if inputs.current_case_state not in (
            RecoveryCaseStatus.POLICY_REVIEW,
            RecoveryCaseStatus.RECOVERY_INITIATED,
        ):
            raise ExecutionGuardError(
                f"Case state {inputs.current_case_state} does not permit execution"
            )

        if inputs.is_legal_locked:
            raise ExecutionGuardError("Execution blocked: Case is legally locked")
        if inputs.is_automation_locked:
            raise ExecutionGuardError("Execution blocked: Case is automation locked")

        if not inputs.is_policy_approved:
            raise ExecutionGuardError(
                "Execution blocked: Policy decision does not approve this action"
            )

        if inputs.amount_minor > inputs.verified_collectible_amount_minor:
            msg = (
                f"Amount {inputs.amount_minor} exceeds verified collectible "
                f"{inputs.verified_collectible_amount_minor}"
            )
            raise ExecutionGuardError(msg)

        if inputs.amount_minor > inputs.safely_recoverable_amount_minor:
            msg = (
                f"Amount {inputs.amount_minor} exceeds safely recoverable "
                f"{inputs.safely_recoverable_amount_minor}"
            )
            raise ExecutionGuardError(msg)

        if (
            inputs.amount_minor > inputs.autonomous_authority_minor
            and not inputs.has_valid_human_approval
        ):
            raise ExecutionGuardError(
                "Execution blocked: Amount exceeds autonomous authority "
                "without valid human approval"
            )

        if inputs.action_already_executed:
            raise ExecutionGuardError("Execution blocked: Action has already been executed")

        if inputs.currency != "INR":
            raise ExecutionGuardError(
                f"Execution blocked: Currency {inputs.currency} not supported by MVP"
            )

    def execute_action(self, inputs: ExecutionInput) -> ExecutionResult:
        """Validate and execute a recovery action via the payment provider."""
        # 1. Idempotency Check
        idempotency_key = f"exec-{inputs.merchant_id}-{inputs.case_id}-{inputs.action_id}"
        request_hash = self._compute_request_hash(inputs)

        existing = self._idempotency_store.get(idempotency_key)
        if existing is not None:
            if existing["request_hash"] != request_hash:
                return ExecutionResult(
                    action_id=inputs.action_id,
                    success=False,
                    provider_id=None,
                    provider_reference=None,
                    payment_link_url=None,
                    error_message="Idempotency key collision with different request parameters",
                )
            # Return cached result
            res_dict = existing["result"]
            return ExecutionResult(
                action_id=res_dict["action_id"],
                success=res_dict["success"],
                provider_id=res_dict["provider_id"],
                provider_reference=res_dict["provider_reference"],
                payment_link_url=res_dict["payment_link_url"],
                error_message=res_dict["error_message"],
            )

        # 2. Guard Validation
        try:
            self._validate_execution_guards(inputs)
        except ExecutionGuardError as e:
            return ExecutionResult(
                action_id=inputs.action_id,
                success=False,
                provider_id=None,
                provider_reference=None,
                payment_link_url=None,
                error_message=str(e),
            )

        # 3. Provider Request Formatting
        reference_id = f"RRA-{inputs.case_id}-{inputs.action_id}"[:40]

        description = f"Payment for invoice {inputs.invoice_id}"
        notes = {
            "merchant_id": str(inputs.merchant_id),
            "invoice_id": str(inputs.invoice_id),
            "recovery_case_id": str(inputs.case_id),
            "recovery_action_id": str(inputs.action_id),
            "recovery_type": inputs.action_type.value,
        }

        request = PaymentLinkRequest(
            amount_minor=inputs.amount_minor,  # type: ignore[arg-type]
            currency=inputs.currency,
            reference_id=reference_id,
            description=description,
            customer_name=inputs.customer_name,
            customer_email=inputs.customer_email,
            customer_contact=inputs.customer_contact,
            notes=notes,
        )

        # 4. Execution
        try:
            p_result = self._provider.create_payment_link(request)
            result = ExecutionResult(
                action_id=inputs.action_id,
                success=True,
                provider_id=p_result.provider_id,
                provider_reference=p_result.reference_id,
                payment_link_url=p_result.payment_link_url,
                error_message=None,
            )
            self._idempotency_store.set(idempotency_key, request_hash, result)
            return result
        except RazorpayProviderError as e:
            result = ExecutionResult(
                action_id=inputs.action_id,
                success=False,
                provider_id=None,
                provider_reference=None,
                payment_link_url=None,
                error_message=str(e),
            )
            # We don't cache failures since they may be transient (like network errors)
            return result
