from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.recovery import AuditEvent, Payment
from app.services.webhook_processor import PaymentLookupService, WebhookIdempotencyStore


class DbWebhookIdempotencyStore(WebhookIdempotencyStore):
    def __init__(self, session: Session):
        self.session = session

    def is_processed(self, provider: str, event_id: str) -> bool:
        stmt = select(AuditEvent).where(AuditEvent.external_event_id == event_id)
        return self.session.execute(stmt).scalars().first() is not None

    def mark_processed(self, provider: str, event_id: str) -> None:
        pass  # Audits are logged automatically during processing

    def is_payment_processed(self, provider: str, provider_payment_id: str) -> bool:
        stmt = select(Payment).where(Payment.razorpay_payment_id == provider_payment_id)
        return self.session.execute(stmt).scalars().first() is not None

    def mark_payment_processed(self, provider: str, provider_payment_id: str) -> None:
        pass


class DbPaymentLookupService(PaymentLookupService):
    def __init__(self, session: Session):
        self.session = session

    def get_payment_context(
        self, provider_payment_link_id: str | None, provider_reference_id: str | None
    ) -> dict[str, Any] | None:
        if not provider_payment_link_id:
            return None
        stmt = select(Payment).where(Payment.razorpay_payment_link_id == provider_payment_link_id)
        payment = self.session.execute(stmt).scalars().first()
        if not payment:
            return None

        case = payment.case
        return {
            "expected_provider_payment_link_id": payment.razorpay_payment_link_id,
            "expected_provider_reference_id": None,
            "expected_amount_minor": payment.amount,
            "expected_currency": payment.currency,
            "current_state": case.status,
            "verified_recovered_amount": case.recovered_amount,
            "applicable_recoverable_balance": case.safely_recoverable_amount,
        }
