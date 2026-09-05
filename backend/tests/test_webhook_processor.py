import hashlib
import hmac
import json

import pytest

from app.services.webhook_processor import (
    PaymentLookupService,
    WebhookIdempotencyStore,
    WebhookProcessor,
)


class MockIdempotencyStore(WebhookIdempotencyStore):
    def __init__(self):
        self._processed = set()
        self._processed_payments = set()

    def is_processed(self, provider: str, event_id: str) -> bool:
        return (provider, event_id) in self._processed

    def mark_processed(self, provider: str, event_id: str) -> None:
        self._processed.add((provider, event_id))

    def is_payment_processed(self, provider: str, provider_payment_id: str) -> bool:
        return (provider, provider_payment_id) in self._processed_payments

    def mark_payment_processed(self, provider: str, provider_payment_id: str) -> None:
        self._processed_payments.add((provider, provider_payment_id))


class MockPaymentLookup(PaymentLookupService):
    def __init__(self):
        self.context = {
            "plink_123": {
                "expected_currency": "INR",
                "current_state": "PAYMENT_PENDING",
                "verified_recovered_amount": 0,
                "applicable_recoverable_balance": 1000000,
                "expected_provider_payment_link_id": "plink_123",
                "expected_provider_reference_id": "ref_123",
                "expected_amount_minor": 50000,
            }
        }

    def get_payment_context(
        self, provider_payment_link_id: str | None, provider_reference_id: str | None
    ) -> dict | None:
        return self.context.get(provider_payment_link_id)


class MockStateMachine:
    def __init__(self):
        self.transition_called = False

    def transition(self, current_state, event, context):

        # State machine guard for overpayment:
        if context.verified_recovered_amount > context.applicable_recoverable_balance:
            raise Exception("Overpayment not permitted")

        self.transition_called = True
        return (
            "PARTIALLY_RECOVERED"
            if context.verified_recovered_amount < context.applicable_recoverable_balance
            else "FULLY_RECOVERED"
        )


@pytest.fixture
def secret():
    return "test_secret_key"


@pytest.fixture
def processor(secret):
    return WebhookProcessor(
        secret=secret,
        idempotency_store=MockIdempotencyStore(),
        payment_lookup=MockPaymentLookup(),
        state_machine=MockStateMachine(),
    )


def generate_signature(payload: str, secret: str) -> str:
    return hmac.new(secret.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256).hexdigest()


def test_valid_signature_accepted(processor, secret):
    payload = json.dumps(
        {
            "event": "payment_link.paid",
            "id": "evt_123",
            "payload": {
                "payment_link": {
                    "entity": {
                        "id": "plink_123",
                        "reference_id": "ref_123",
                        "amount_paid": 50000,
                        "currency": "INR",
                    }
                },
                "payment": {"entity": {"id": "pay_123", "amount": 50000, "currency": "INR"}},
            },
        }
    )
    sig = generate_signature(payload, secret)

    result = processor.process_webhook(payload.encode("utf-8"), sig)
    assert result.success is True
    assert result.domain_event_generated is True
    assert result.is_duplicate is False
    assert processor._state_machine.transition_called is True


def test_invalid_signature_rejected(processor, secret):
    payload = json.dumps({"event": "payment_link.paid", "id": "evt_123"})
    sig = generate_signature(payload, "wrong_secret")

    result = processor.process_webhook(payload.encode("utf-8"), sig)
    assert result.success is False
    assert "Invalid signature" in result.error_message
    assert processor._state_machine.transition_called is False


def test_missing_signature_rejected(processor):
    payload = json.dumps({"event": "payment_link.paid", "id": "evt_123"})

    result = processor.process_webhook(payload.encode("utf-8"), "")
    assert result.success is False
    assert "Missing signature" in result.error_message


def test_malformed_payload_rejected(processor, secret):
    payload = "{bad_json: true"
    sig = generate_signature(payload, secret)

    result = processor.process_webhook(payload.encode("utf-8"), sig)
    assert result.success is False
    assert "Malformed JSON payload" in result.error_message


def test_missing_event_id(processor, secret):
    payload = json.dumps({"event": "payment_link.paid"})
    sig = generate_signature(payload, secret)

    result = processor.process_webhook(payload.encode("utf-8"), sig)
    assert result.success is False
    assert "Missing event ID" in result.error_message


def test_duplicate_event_is_idempotent(processor, secret):
    payload = json.dumps(
        {
            "event": "payment_link.paid",
            "id": "evt_dup",
            "payload": {
                "payment_link": {"entity": {"id": "plink_123", "reference_id": "ref_123"}},
                "payment": {"entity": {"id": "pay_123", "amount": 50000, "currency": "INR"}},
            },
        }
    )
    sig = generate_signature(payload, secret)

    # First time
    result1 = processor.process_webhook(payload.encode("utf-8"), sig)
    assert result1.success is True

    processor._state_machine.transition_called = False

    # Second time
    result2 = processor.process_webhook(payload.encode("utf-8"), sig)
    assert result2.success is True
    assert result2.is_duplicate is True
    assert result2.domain_event_generated is False
    assert processor._state_machine.transition_called is False


def test_unknown_provider_reference_rejected_safely(processor, secret):
    payload = json.dumps(
        {
            "event": "payment_link.paid",
            "id": "evt_unk",
            "payload": {
                "payment_link": {"entity": {"id": "plink_UNKNOWN"}},
                "payment": {"entity": {"id": "pay_123", "amount": 50000, "currency": "INR"}},
            },
        }
    )
    sig = generate_signature(payload, secret)

    result = processor.process_webhook(payload.encode("utf-8"), sig)
    assert result.success is True  # We handled it safely
    assert result.domain_event_generated is False
    assert "Unknown provider reference" in result.error_message


def test_mismatched_currency_rejected(processor, secret):
    payload = json.dumps(
        {
            "event": "payment_link.paid",
            "id": "evt_usd",
            "payload": {
                "payment_link": {"entity": {"id": "plink_123", "reference_id": "ref_123"}},
                "payment": {"entity": {"id": "pay_123", "amount": 50000, "currency": "USD"}},
            },
        }
    )
    sig = generate_signature(payload, secret)

    result = processor.process_webhook(payload.encode("utf-8"), sig)
    assert result.success is False
    assert "Currency mismatch: USD" in result.error_message


def test_state_machine_guard_failure(processor, secret):
    # This payload has an amount of 2,000,000 which exceeds the
    # 1,000,000 applicable_recoverable_balance
    processor._payment_lookup.context["plink_123"]["expected_amount_minor"] = 2000000
    payload = json.dumps(
        {
            "event": "payment_link.paid",
            "id": "evt_overpay",
            "payload": {
                "payment_link": {"entity": {"id": "plink_123", "reference_id": "ref_123"}},
                "payment": {"entity": {"id": "pay_123", "amount": 2000000, "currency": "INR"}},
            },
        }
    )
    sig = generate_signature(payload, secret)

    result = processor.process_webhook(payload.encode("utf-8"), sig)
    assert result.success is False
    assert "State machine guard error" in result.error_message


def test_amount_mismatch_rejected(processor, secret):
    # Context expects 50000, but payload has 40000
    payload = json.dumps(
        {
            "event": "payment_link.paid",
            "id": "evt_amt_mismatch",
            "payload": {
                "payment_link": {"entity": {"id": "plink_123", "reference_id": "ref_123"}},
                "payment": {"entity": {"id": "pay_123", "amount": 40000, "currency": "INR"}},
            },
        }
    )
    sig = generate_signature(payload, secret)

    result = processor.process_webhook(payload.encode("utf-8"), sig)
    assert result.success is False
    assert "Amount mismatch" in result.error_message


def test_binding_mismatch_rejected(processor, secret):
    # Context expects ref_123, but payload has ref_WRONG
    payload = json.dumps(
        {
            "event": "payment_link.paid",
            "id": "evt_bind_mismatch",
            "payload": {
                "payment_link": {"entity": {"id": "plink_123", "reference_id": "ref_WRONG"}},
                "payment": {"entity": {"id": "pay_123", "amount": 50000, "currency": "INR"}},
            },
        }
    )
    sig = generate_signature(payload, secret)

    result = processor.process_webhook(payload.encode("utf-8"), sig)
    assert result.success is False
    assert "Binding mismatch" in result.error_message


def test_duplicate_provider_payment_id_rejected(processor, secret):
    # Two different events, but same provider_payment_id (pay_123)
    payload1 = json.dumps(
        {
            "event": "payment_link.paid",
            "id": "evt_first",
            "payload": {
                "payment_link": {"entity": {"id": "plink_123", "reference_id": "ref_123"}},
                "payment": {"entity": {"id": "pay_123", "amount": 50000, "currency": "INR"}},
            },
        }
    )
    sig1 = generate_signature(payload1, secret)
    result1 = processor.process_webhook(payload1.encode("utf-8"), sig1)
    assert result1.success is True

    payload2 = json.dumps(
        {
            "event": "payment_link.paid",
            "id": "evt_second_different",  # different event ID
            "payload": {
                "payment_link": {"entity": {"id": "plink_123", "reference_id": "ref_123"}},
                "payment": {
                    "entity": {"id": "pay_123", "amount": 50000, "currency": "INR"}
                },  # same payment ID
            },
        }
    )
    sig2 = generate_signature(payload2, secret)
    result2 = processor.process_webhook(payload2.encode("utf-8"), sig2)

    assert result2.success is True
    assert result2.is_duplicate is True
    assert "Duplicate provider payment ID" in result2.error_message


def test_ignored_event_type(processor, secret):
    payload = json.dumps({"event": "payment.failed", "id": "evt_fail"})
    sig = generate_signature(payload, secret)

    result = processor.process_webhook(payload.encode("utf-8"), sig)
    assert result.success is True
    assert result.domain_event_generated is False
    assert "Ignored event type" in result.error_message
