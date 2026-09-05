import httpx
import pytest

from app.services.payment_provider import PaymentLinkRequest
from app.services.razorpay_adapter import (
    MockPaymentProvider,
    RazorpayProvider,
    RazorpayProviderError,
)


class MockResponse:
    def __init__(self, status_code: int, json_data: dict, request: httpx.Request | None = None):
        self.status_code = status_code
        self._json_data = json_data
        self.request = request or httpx.Request("POST", "https://api.razorpay.com/v1/payment_links")

    def json(self):
        return self._json_data

    def raise_for_status(self):
        if self.status_code >= 400:
            raise httpx.HTTPStatusError("Error", request=self.request, response=self)  # type: ignore


def test_razorpay_provider_initialization():
    with pytest.raises(ValueError, match="credentials are required"):
        RazorpayProvider("", "")


def test_razorpay_provider_create_payment_link(monkeypatch):
    provider = RazorpayProvider("key", "secret")

    def mock_post(*args, **kwargs):
        return MockResponse(
            200,
            {
                "id": "plink_test123",
                "reference_id": "REF-123",
                "short_url": "https://rzp.io/i/test123",
                "status": "created",
                "amount": 100000,
                "currency": "INR",
                "created_at": 1600000000,
            },
        )

    monkeypatch.setattr(httpx.Client, "post", mock_post)

    request = PaymentLinkRequest(
        amount_minor=100000, currency="INR", reference_id="REF-123", description="Test payment"
    )

    result = provider.create_payment_link(request)
    assert result.provider_id == "plink_test123"
    assert result.payment_link_url == "https://rzp.io/i/test123"
    assert result.status == "created"


def test_razorpay_provider_handles_http_errors(monkeypatch):
    provider = RazorpayProvider("key", "secret")

    def mock_post(*args, **kwargs):
        return MockResponse(400, {"error": "bad request"})

    monkeypatch.setattr(httpx.Client, "post", mock_post)

    request = PaymentLinkRequest(
        amount_minor=100000, currency="INR", reference_id="REF-123", description="Test payment"
    )

    with pytest.raises(RazorpayProviderError, match="HTTP 400"):
        provider.create_payment_link(request)


def test_mock_payment_provider():
    provider = MockPaymentProvider()
    request = PaymentLinkRequest(
        amount_minor=50000, currency="INR", reference_id="REF-MOCK", description="Mock payment"
    )

    result = provider.create_payment_link(request)
    assert result.provider_id.startswith("plink_mock_")
    assert result.amount_minor == 50000
    assert result.reference_id == "REF-MOCK"

    fetched = provider.get_payment_link(result.provider_id)
    assert fetched.provider_id == result.provider_id


def test_mock_payment_provider_failure_mode():
    provider = MockPaymentProvider(failure_mode=True)
    request = PaymentLinkRequest(
        amount_minor=50000, currency="INR", reference_id="REF-MOCK", description="Mock payment"
    )

    with pytest.raises(RazorpayProviderError, match="Simulated provider failure"):
        provider.create_payment_link(request)
