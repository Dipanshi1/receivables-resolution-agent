from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.enums import RecoveryCaseStatus
from app.domain.recovery import Payment, RecoveryCase
from app.services.financial_calculation import FinancialCalculationResult
from app.services.reconciliation import ReconciliationContext, ReconciliationRepository


class DbReconciliationRepository(ReconciliationRepository):
    def __init__(self, session: Session):
        self.session = session

    def get_context_by_provider_identifiers(
        self, provider_payment_link_id: str | None, provider_reference_id: str | None
    ) -> ReconciliationContext | None:
        if not provider_payment_link_id:
            return None

        stmt = select(Payment).where(Payment.razorpay_payment_link_id == provider_payment_link_id)
        payment = self.session.execute(stmt).scalars().first()
        if not payment:
            return None

        case = payment.case

        return ReconciliationContext(
            case_id=str(case.id),
            action_id=str(payment.recovery_action_id),
            payment_id=str(payment.id),
            current_case_state=RecoveryCaseStatus(case.status),
            expected_currency=payment.currency,
            expected_amount_minor=payment.amount,
            gross_invoice_amount_minor=case.invoice.total_amount,
            valid_adjustments_minor=0,
            verified_payments_minor_before=case.invoice.amount_paid,
            verified_recovered_amount_minor_before=case.recovered_amount,
            claimed_disputed_amount_minor=case.claimed_disputed_amount,
            verified_disputed_amount_minor=case.verified_disputed_amount,
            is_already_reconciled=(payment.status == "CAPTURED"),
        )

    def save_reconciliation(
        self,
        case_id: str,
        payment_id: str,
        new_state: RecoveryCaseStatus,
        calc_result: FinancialCalculationResult,
    ) -> None:
        case = self.session.get(RecoveryCase, case_id)
        if case:
            case.status = new_state.value
            case.collectible_amount = calc_result.collectible_amount_minor
            case.safely_recoverable_amount = calc_result.safely_recoverable_amount_minor
            case.recovered_amount = calc_result.verified_recovered_amount_minor
            case.remaining_amount = calc_result.remaining_amount_minor

        payment = self.session.get(Payment, payment_id)
        if payment:
            payment.status = "CAPTURED"

        self.session.commit()
