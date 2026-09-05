import logging
import time
from typing import Any

import httpx

from app.services.payment_provider import PaymentLinkRequest, PaymentLinkResult, PaymentProvider

logger = logging.getLogger(__name__)


class RazorpayProviderError(Exception):
    """Base exception for Razorpay provider errors."""

    pass


class RazorpayProvider(PaymentProvider):
    """Razorpay implementation of the PaymentProvider interface."""

    def __init__(self, key_id: str, key_secret: str, base_url: str = "https://api.razorpay.com/v1"):
        if not key_id or not key_secret:
            raise ValueError("Razorpay credentials are required")
        self._key_id = key_id
        self._key_secret = key_secret
        self._base_url = base_url.rstrip("/")

    def _get_client(self) -> httpx.Client:
        return httpx.Client(
            auth=(self._key_id, self._key_secret),
            timeout=10.0,
        )

    def create_payment_link(self, request: PaymentLinkRequest) -> PaymentLinkResult:
        """Create a payment link using Razorpay API."""
        url = f"{self._base_url}/payment_links"

        payload: dict[str, Any] = {
            "amount": request.amount_minor,
            "currency": request.currency,
            "reference_id": request.reference_id,
            "description": request.description,
        }

        if request.expire_by:
            payload["expire_by"] = request.expire_by

        if request.notes:
            payload["notes"] = request.notes

        customer = {}
        if request.customer_name:
            customer["name"] = request.customer_name
        if request.customer_email:
            customer["email"] = request.customer_email
        if request.customer_contact:
            customer["contact"] = request.customer_contact

        if customer:
            payload["customer"] = customer

        try:
            with self._get_client() as client:
                response = client.post(url, json=payload)
                response.raise_for_status()
                data = response.json()

                return PaymentLinkResult(
                    provider_id=data["id"],
                    reference_id=data.get("reference_id", request.reference_id),
                    payment_link_url=data["short_url"],
                    status=data["status"],
                    amount_minor=data["amount"],
                    currency=data["currency"],
                    created_at=data.get("created_at", int(time.time())),
                    expired_at=data.get("expired_at"),
                    raw_response=data,
                )
        except httpx.HTTPStatusError as e:
            # Avoid leaking secrets in error messages
            logger.error("Razorpay API error: HTTP %s", e.response.status_code)
            raise RazorpayProviderError(
                f"Razorpay API error: HTTP {e.response.status_code}"
            ) from None
        except httpx.RequestError:
            logger.error("Razorpay connection error")
            raise RazorpayProviderError("Failed to connect to Razorpay") from None
        except (KeyError, ValueError):
            logger.error("Malformed Razorpay response")
            raise RazorpayProviderError("Malformed Razorpay response") from None

    def get_payment_link(self, provider_id: str) -> PaymentLinkResult:
        """Fetch an existing payment link using Razorpay API."""
        url = f"{self._base_url}/payment_links/{provider_id}"
        try:
            with self._get_client() as client:
                response = client.get(url)
                response.raise_for_status()
                data = response.json()

                return PaymentLinkResult(
                    provider_id=data["id"],
                    reference_id=data.get("reference_id", ""),
                    payment_link_url=data.get("short_url", ""),
                    status=data["status"],
                    amount_minor=data["amount"],
                    currency=data["currency"],
                    created_at=data.get("created_at", int(time.time())),
                    expired_at=data.get("expired_at"),
                    raw_response=data,
                )
        except httpx.HTTPStatusError as e:
            logger.error("Razorpay API error: HTTP %s", e.response.status_code)
            raise RazorpayProviderError(
                f"Razorpay API error: HTTP {e.response.status_code}"
            ) from None
        except httpx.RequestError:
            logger.error("Razorpay connection error")
            raise RazorpayProviderError("Failed to connect to Razorpay") from None
        except (KeyError, ValueError):
            logger.error("Malformed Razorpay response")
            raise RazorpayProviderError("Malformed Razorpay response") from None


class MockPaymentProvider(PaymentProvider):
    """In-memory mock provider for testing and benchmarks."""

    def __init__(self, failure_mode: bool = False):
        self.links: dict[str, PaymentLinkResult] = {}
        self.failure_mode = failure_mode
        self._next_id = 1

    def create_payment_link(self, request: PaymentLinkRequest) -> PaymentLinkResult:
        if self.failure_mode:
            raise RazorpayProviderError("Simulated provider failure")

        provider_id = f"plink_mock_{self._next_id:04d}"
        self._next_id += 1

        result = PaymentLinkResult(
            provider_id=provider_id,
            reference_id=request.reference_id,
            payment_link_url=f"https://mock.rzp.io/{provider_id}",
            status="created",
            amount_minor=request.amount_minor,
            currency=request.currency,
            created_at=int(time.time()),
            expired_at=request.expire_by,
            raw_response={"mock": True},
        )
        self.links[provider_id] = result
        return result

    def get_payment_link(self, provider_id: str) -> PaymentLinkResult:
        if self.failure_mode:
            raise RazorpayProviderError("Simulated provider failure")
        if provider_id not in self.links:
            raise RazorpayProviderError("Payment link not found")
        return self.links[provider_id]
