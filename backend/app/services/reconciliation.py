import logging
from dataclasses import dataclass
from typing import Protocol

from app.domain.enums import RecoveryCaseStatus
from app.services.audit import AuditService
from app.services.financial_calculation import (
    FinancialCalculationInput,
    FinancialCalculationResult,
    calculate_financial_position,
)
from app.services.state_machine import RecoveryEvent, StateMachineService, TransitionContext
from app.services.webhook_processor import VerifiedWebhookEvent

logger = logging.getLogger(__name__)


class ReconciliationError(Exception):
    pass


@dataclass(frozen=True)
class ReconciliationContext:
    case_id: str
    action_id: str
    payment_id: str
    current_case_state: RecoveryCaseStatus
    expected_currency: str
    expected_amount_minor: int
    gross_invoice_amount_minor: int
    valid_adjustments_minor: int
    verified_payments_minor_before: int
    verified_recovered_amount_minor_before: int
    claimed_disputed_amount_minor: int
    verified_disputed_amount_minor: int | None
    is_already_reconciled: bool


class ReconciliationRepository(Protocol):
    def get_context_by_provider_identifiers(
        self, provider_payment_link_id: str | None, provider_reference_id: str | None
    ) -> ReconciliationContext | None: ...
    def save_reconciliation(
        self,
        case_id: str,
        payment_id: str,
        new_state: RecoveryCaseStatus,
        calc_result: FinancialCalculationResult,
    ) -> None: ...


class ReconciliationService:
    def __init__(
        self,
        repository: ReconciliationRepository,
        state_machine: StateMachineService,
        audit_service: AuditService,
    ):
        self._repository = repository
        self._state_machine = state_machine
        self._audit_service = audit_service

    def reconcile_payment(self, verified_event: VerifiedWebhookEvent) -> FinancialCalculationResult:
        """
        Reconciles a verified webhook payment event against the internal financial state.
        Uses FinancialCalculationService to calculate new bounds.
        """
        context = self._repository.get_context_by_provider_identifiers(
            verified_event.provider_payment_link_id, verified_event.provider_reference_id
        )

        if not context:
            self._audit_service.record_event(
                case_id="UNKNOWN",
                event_type="WEBHOOK_RESOURCE_UNMAPPED",
                actor_type="SYSTEM",
                payload={
                    "event_id": verified_event.event_id,
                    "provider_payment_id": verified_event.provider_payment_id,
                },
                external_event_id=verified_event.event_id,
            )
            raise ReconciliationError("Unknown payment or case")

        if context.is_already_reconciled:
            self._audit_service.record_event(
                case_id=context.case_id,
                event_type="PAYMENT_DUPLICATE_REJECTED",
                actor_type="SYSTEM",
                payload={"provider_payment_id": verified_event.provider_payment_id},
                external_event_id=verified_event.event_id,
            )
            raise ReconciliationError("Payment is already reconciled")

        if verified_event.currency != context.expected_currency:
            self._audit_service.record_event(
                case_id=context.case_id,
                event_type="PAYMENT_RECONCILIATION_FAILED",
                actor_type="SYSTEM",
                payload={
                    "reason": "Currency mismatch",
                    "expected": context.expected_currency,
                    "got": verified_event.currency,
                },
                external_event_id=verified_event.event_id,
            )
            raise ReconciliationError("Currency mismatch")

        if verified_event.amount_minor != context.expected_amount_minor:
            self._audit_service.record_event(
                case_id=context.case_id,
                event_type="PAYMENT_RECONCILIATION_FAILED",
                actor_type="SYSTEM",
                payload={
                    "reason": "Amount mismatch",
                    "expected": context.expected_amount_minor,
                    "got": verified_event.amount_minor,
                },
                external_event_id=verified_event.event_id,
            )
            raise ReconciliationError("Amount mismatch")

        # Assume this new payment is added to verified_recovered_amount_minor
        new_recovered_amount = (
            context.verified_recovered_amount_minor_before + verified_event.amount_minor
        )

        try:
            # Prepare inputs for authoritative calculation
            calc_input = FinancialCalculationInput(
                currency=context.expected_currency,
                gross_invoice_amount_minor=context.gross_invoice_amount_minor,
                valid_adjustments_minor=context.valid_adjustments_minor,
                verified_payments_minor=context.verified_payments_minor_before,
                claimed_disputed_amount_minor=context.claimed_disputed_amount_minor,
                verified_disputed_amount_minor=context.verified_disputed_amount_minor,
                verified_recovered_amount_minor=new_recovered_amount,
            )
            calc_result = calculate_financial_position(calc_input)
        except ValueError as e:
            # e.g., over-recovery
            self._audit_service.record_event(
                case_id=context.case_id,
                event_type="PAYMENT_RECONCILIATION_FAILED",
                actor_type="SYSTEM",
                payload={"reason": "Financial invariant violation", "details": str(e)},
                external_event_id=verified_event.event_id,
            )
            raise ReconciliationError(f"Over-recovery or invalid calculation: {str(e)}") from e

        # Audit the verified payment before state transition
        self._audit_service.record_event(
            case_id=context.case_id,
            event_type="PAYMENT_CONFIRMED",
            actor_type="SYSTEM",
            payload={
                "payment_id": context.payment_id,
                "amount_minor": verified_event.amount_minor,
                "provider_payment_id": verified_event.provider_payment_id,
            },
            external_event_id=verified_event.event_id,
        )

        # State transition using StateMachineService
        t_ctx = TransitionContext(
            payment_verified=True,
            verified_recovered_amount=calc_result.verified_recovered_amount_minor,
            applicable_recoverable_balance=calc_result.safely_recoverable_amount_minor,
        )

        try:
            new_state = self._state_machine.transition(
                current_state=context.current_case_state,
                event=RecoveryEvent.PAYMENT_CONFIRMED,
                context=t_ctx,
            )
        except Exception as e:
            self._audit_service.record_event(
                case_id=context.case_id,
                event_type="STATE_TRANSITION_FAILED",
                actor_type="SYSTEM",
                payload={"reason": "State machine guard rejected", "details": str(e)},
                external_event_id=verified_event.event_id,
            )
            raise ReconciliationError(f"State transition failed: {str(e)}") from e

        # Audit the state transition
        if new_state.state_after != context.current_case_state:
            self._audit_service.record_event(
                case_id=context.case_id,
                event_type="STATE_TRANSITION",
                actor_type="STATE_MACHINE",
                state_before=context.current_case_state.value,
                state_after=new_state.state_after.value,
                payload={"trigger": "PAYMENT_CONFIRMED"},
                external_event_id=verified_event.event_id,
            )

        # Audit the reconciliation result
        self._audit_service.record_event(
            case_id=context.case_id,
            event_type="RECONCILIATION_COMPLETED",
            actor_type="FINANCIAL_CALCULATION_SERVICE",
            payload={
                "collectible_amount_minor": calc_result.collectible_amount_minor,
                "safely_recoverable_amount_minor": calc_result.safely_recoverable_amount_minor,
                "verified_recovered_amount_minor": calc_result.verified_recovered_amount_minor,
                "remaining_amount_minor": calc_result.remaining_amount_minor,
                "calculation_version": calc_result.calculation_version,
            },
            external_event_id=verified_event.event_id,
        )

        # Persist
        self._repository.save_reconciliation(
            context.case_id, context.payment_id, new_state.state_after, calc_result
        )

        return calc_result
