import hashlib
import hmac
import json
import logging
from dataclasses import dataclass, field
from typing import Any, Protocol

logger = logging.getLogger(__name__)


class WebhookVerificationError(Exception):
    pass


class WebhookValidationError(Exception):
    pass


@dataclass(frozen=True)
class VerifiedWebhookEvent:
    event_id: str
    event_type: str
    provider_payment_id: str
    provider_payment_link_id: str | None
    provider_reference_id: str | None
    amount_minor: int
    currency: str
    created_at: int
    raw_payload: dict[str, Any] = field(repr=False)


@dataclass(frozen=True)
class WebhookProcessingResult:
    success: bool
    event_id: str | None
    event_type: str | None
    domain_event_generated: bool
    is_duplicate: bool
    error_message: str | None
    verified_event: VerifiedWebhookEvent | None = None


class WebhookIdempotencyStore(Protocol):
    def is_processed(self, provider: str, event_id: str) -> bool: ...
    def mark_processed(self, provider: str, event_id: str) -> None: ...
    def is_payment_processed(self, provider: str, provider_payment_id: str) -> bool: ...
    def mark_payment_processed(self, provider: str, provider_payment_id: str) -> None: ...


class PaymentLookupService(Protocol):
    def get_payment_context(
        self, provider_payment_link_id: str | None, provider_reference_id: str | None
    ) -> dict[str, Any] | None: ...


class WebhookProcessor:
    def __init__(
        self,
        secret: str,
        idempotency_store: WebhookIdempotencyStore,
        payment_lookup: PaymentLookupService,
        state_machine: Any = None,
    ):
        if not secret:
            raise ValueError("Webhook secret is required")
        self._secret = secret
        self._idempotency_store = idempotency_store
        self._payment_lookup = payment_lookup
        self._state_machine = state_machine

    def verify_signature(self, raw_body: bytes, signature: str) -> bool:
        expected_sig = hmac.new(self._secret.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()
        return hmac.compare_digest(expected_sig, signature)

    def process_webhook(self, raw_body: bytes, signature: str) -> WebhookProcessingResult:
        if not signature:
            return WebhookProcessingResult(False, None, None, False, False, "Missing signature")

        if not self.verify_signature(raw_body, signature):
            # Fail closed on invalid signature
            return WebhookProcessingResult(False, None, None, False, False, "Invalid signature")

        try:
            payload = json.loads(raw_body.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            return WebhookProcessingResult(
                False, None, None, False, False, "Malformed JSON payload"
            )

        event_id = payload.get("id")
        event_type = payload.get("event")

        if not event_id or not event_type:
            return WebhookProcessingResult(
                False, event_id, event_type, False, False, "Missing event ID or type"
            )

        if self._idempotency_store.is_processed("razorpay", event_id):
            return WebhookProcessingResult(
                True, event_id, event_type, False, True, "Duplicate event"
            )

        if event_type not in (
            "payment_link.paid",
            "payment_link.partially_paid",
            "payment.captured",
        ):
            self._idempotency_store.mark_processed("razorpay", event_id)
            return WebhookProcessingResult(
                True, event_id, event_type, False, False, "Ignored event type"
            )

        try:
            pl_entity = payload.get("payload", {}).get("payment_link", {}).get("entity", {})
            payment_entity = payload.get("payload", {}).get("payment", {}).get("entity", {})

            # Extract identifiers securely
            amount_minor = payment_entity.get("amount")
            if amount_minor is None:
                amount_minor = pl_entity.get("amount_paid")

            currency = payment_entity.get("currency") or pl_entity.get("currency")
            provider_payment_id = payment_entity.get("id")

            provider_payment_link_id = pl_entity.get("id")
            provider_reference_id = pl_entity.get("reference_id") or payment_entity.get(
                "notes", {}
            ).get("reference_id")

            if amount_minor is None or not currency or not provider_payment_id:
                return WebhookProcessingResult(
                    False, event_id, event_type, False, False, "Incomplete payment data in payload"
                )

            verified_event = VerifiedWebhookEvent(
                event_id=event_id,
                event_type=event_type,
                provider_payment_id=provider_payment_id,
                provider_payment_link_id=provider_payment_link_id,
                provider_reference_id=provider_reference_id,
                amount_minor=int(amount_minor),
                currency=currency,
                created_at=payload.get("created_at", 0),
                raw_payload=payload,
            )

            # Provider identifier validation / internal mapping
            context = self._payment_lookup.get_payment_context(
                provider_payment_link_id, provider_reference_id
            )
            if not context:
                self._idempotency_store.mark_processed("razorpay", event_id)
                return WebhookProcessingResult(
                    True,
                    event_id,
                    event_type,
                    False,
                    False,
                    "Unknown provider reference",
                    verified_event,
                )

            # Exact internal binding validation
            expected_link = context.get("expected_provider_payment_link_id")
            if (
                expected_link
                and provider_payment_link_id
                and expected_link != provider_payment_link_id
            ):
                return WebhookProcessingResult(
                    False,
                    event_id,
                    event_type,
                    False,
                    False,
                    "Binding mismatch: payment link ID",
                    verified_event,
                )

            expected_ref = context.get("expected_provider_reference_id")
            if expected_ref and provider_reference_id and expected_ref != provider_reference_id:
                return WebhookProcessingResult(
                    False,
                    event_id,
                    event_type,
                    False,
                    False,
                    "Binding mismatch: reference ID",
                    verified_event,
                )

            # Amount validation
            expected_amount = context.get("expected_amount_minor")
            if expected_amount is not None and verified_event.amount_minor != expected_amount:
                msg = (
                    f"Amount mismatch: expected {expected_amount}, "
                    f"got {verified_event.amount_minor}"
                )
                return WebhookProcessingResult(
                    False, event_id, event_type, False, False, msg, verified_event
                )

            if currency != context.get("expected_currency", "INR"):
                # Must fail safely and not process
                return WebhookProcessingResult(
                    False,
                    event_id,
                    event_type,
                    False,
                    False,
                    f"Currency mismatch: {currency}",
                    verified_event,
                )

            # Payment-level idempotency
            if self._idempotency_store.is_payment_processed("razorpay", provider_payment_id):
                # The payment itself was already processed (e.g. through a different event ID)
                self._idempotency_store.mark_processed("razorpay", event_id)
                return WebhookProcessingResult(
                    True,
                    event_id,
                    event_type,
                    False,
                    True,
                    "Duplicate provider payment ID",
                    verified_event,
                )

            if self._state_machine:
                from app.services.state_machine import RecoveryEvent, TransitionContext

                t_ctx = TransitionContext(
                    payment_verified=True,
                    verified_recovered_amount=context.get("verified_recovered_amount", 0)
                    + verified_event.amount_minor,
                    applicable_recoverable_balance=context.get("applicable_recoverable_balance", 0),
                )

                try:
                    self._state_machine.transition(
                        current_state=context.get("current_state"),
                        event=RecoveryEvent.PAYMENT_CONFIRMED,
                        context=t_ctx,
                    )
                except Exception as e:
                    return WebhookProcessingResult(
                        False,
                        event_id,
                        event_type,
                        False,
                        False,
                        f"State machine guard error: {str(e)}",
                        verified_event,
                    )

            self._idempotency_store.mark_processed("razorpay", event_id)
            self._idempotency_store.mark_payment_processed("razorpay", provider_payment_id)
            return WebhookProcessingResult(
                True, event_id, event_type, True, False, None, verified_event
            )

        except Exception:
            # Mask underlying error details
            return WebhookProcessingResult(
                False,
                event_id,
                event_type,
                False,
                False,
                "Unexpected error processing webhook payload",
            )
