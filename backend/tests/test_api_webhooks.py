"""API tests for the Razorpay webhook endpoint.

Tests verify:
- Missing signature → 400
- Invalid HMAC → 400 (via WebhookProcessor)
- Valid signature but unknown event type → 200 OK
- Duplicate webhook → 200 OK (idempotent)
"""

import hashlib
import hmac
import json
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi.testclient import TestClient

from app.api.deps import get_db_session
from app.main import app


def _override_session(session):
    async def _get():
        yield session
    return _get


def _make_session():
    session = AsyncMock()
    # Return empty result sets by default
    empty_result = MagicMock()
    empty_result.scalars.return_value.all.return_value = []
    session.execute = AsyncMock(return_value=empty_result)
    session.commit = AsyncMock()
    session.add = MagicMock()
    return session


def _compute_sig(secret: str, body: bytes) -> str:
    return hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()


def test_webhook_missing_signature_rejected():
    """Missing X-Razorpay-Signature header returns 400."""
    session = _make_session()
    app.dependency_overrides[get_db_session] = _override_session(session)

    try:
        client = TestClient(app)
        response = client.post(
            "/v1/webhooks/razorpay",
            content=b'{"event": "payment.captured"}',
            headers={"Content-Type": "application/json"},
        )
        assert response.status_code == 400
        data = response.json()
        assert data["detail"]["code"] == "WEBHOOK_SIGNATURE_INVALID"
    finally:
        app.dependency_overrides.clear()


def test_webhook_invalid_signature_rejected():
    """Invalid HMAC signature returns 400."""
    session = _make_session()
    app.dependency_overrides[get_db_session] = _override_session(session)

    try:
        with patch("app.api.v1.endpoints.webhooks.get_settings") as mock_settings:
            settings = MagicMock()
            settings.razorpay_webhook_secret = "test_secret"
            mock_settings.return_value = settings

            client = TestClient(app)
            body = b'{"id": "evt_1", "event": "payment_link.paid"}'
            response = client.post(
                "/v1/webhooks/razorpay",
                content=body,
                headers={
                    "Content-Type": "application/json",
                    "x-razorpay-signature": "bad_signature_value",
                },
            )
            assert response.status_code == 400
            data = response.json()
            assert data["detail"]["code"] == "WEBHOOK_SIGNATURE_INVALID"
    finally:
        app.dependency_overrides.clear()


def test_webhook_valid_signature_unknown_event_ack():
    """Valid signature with unknown event type returns 200 OK."""
    secret = "test_secret_abc"
    body = json.dumps({
        "id": "evt_unknown_001",
        "event": "some.other.event",
        "created_at": 1000000,
        "payload": {},
    }).encode("utf-8")
    sig = _compute_sig(secret, body)

    session = _make_session()
    app.dependency_overrides[get_db_session] = _override_session(session)

    try:
        with patch("app.api.v1.endpoints.webhooks.get_settings") as mock_settings:
            settings = MagicMock()
            settings.razorpay_webhook_secret = secret
            mock_settings.return_value = settings

            client = TestClient(app)
            response = client.post(
                "/v1/webhooks/razorpay",
                content=body,
                headers={
                    "Content-Type": "application/json",
                    "x-razorpay-signature": sig,
                },
            )
            assert response.status_code == 200
            assert response.json()["status"] == "ok"
    finally:
        app.dependency_overrides.clear()


def test_webhook_unconfigured_secret_returns_500():
    """When webhook secret is not configured, endpoint returns 500 (fail closed)."""
    session = _make_session()
    app.dependency_overrides[get_db_session] = _override_session(session)

    try:
        with patch("app.api.v1.endpoints.webhooks.get_settings") as mock_settings:
            settings = MagicMock()
            settings.razorpay_webhook_secret = ""  # empty = not configured
            mock_settings.return_value = settings

            client = TestClient(app)
            response = client.post(
                "/v1/webhooks/razorpay",
                content=b'{"event": "payment_link.paid"}',
                headers={
                    "Content-Type": "application/json",
                    "x-razorpay-signature": "anything",
                },
            )
            assert response.status_code == 500
    finally:
        app.dependency_overrides.clear()


def test_webhook_duplicate_event_is_idempotent():
    """Duplicate event_id (already in audit log) returns 200 OK without re-processing."""
    secret = "dedupe_secret"
    event_id = "evt_dup_001"
    body = json.dumps(
        {
            "id": event_id,
            "account_id": "acc_123",
            "contains": ["payment", "payment_link"],
            "entity": "event",
            "event": "payment_link.paid",
            "created_at": 1000000,
            "payload": {
                "payment_link": {
                    "entity": {
                        "id": "plink_x",
                        "amount_paid": 50000,
                        "currency": "INR",
                        "reference_id": "ref_x",
                    }
                },
                "payment": {"entity": {"id": "pay_x", "amount": 50000, "currency": "INR"}},
            },
        }
    ).encode("utf-8")
    sig = _compute_sig(secret, body)

    session = _make_session()

    # Pre-seed the processed event IDs
    audit_result = MagicMock()
    audit_result.scalars.return_value.all.return_value = [event_id]

    pay_result = MagicMock()
    pay_result.scalars.return_value.all.return_value = []

    payments_result = MagicMock()
    payments_result.scalars.return_value.all.return_value = []

    call_count = 0

    async def side_execute(stmt):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return audit_result  # processed event IDs
        if call_count == 2:
            return pay_result   # processed payment IDs
        return payments_result  # payments with links

    session.execute = AsyncMock(side_effect=side_execute)

    app.dependency_overrides[get_db_session] = _override_session(session)

    try:
        with patch("app.api.v1.endpoints.webhooks.get_settings") as mock_settings:
            settings = MagicMock()
            settings.razorpay_webhook_secret = secret
            mock_settings.return_value = settings

            client = TestClient(app)
            response = client.post(
                "/v1/webhooks/razorpay",
                content=body,
                headers={
                    "Content-Type": "application/json",
                    "x-razorpay-signature": sig,
                },
            )
            # Idempotent — already processed event is ack'd with 200
            assert response.status_code == 200
            assert response.json()["status"] == "ok"
            # DB was NOT committed again (no duplicate financial effect)
            session.commit.assert_not_called()
    finally:
        app.dependency_overrides.clear()
