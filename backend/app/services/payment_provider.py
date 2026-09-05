import abc
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class PaymentLinkRequest:
    amount_minor: int
    currency: str
    reference_id: str
    description: str
    customer_name: str | None = None
    customer_email: str | None = None
    customer_contact: str | None = None
    expire_by: int | None = None
    notes: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class PaymentLinkResult:
    provider_id: str
    reference_id: str
    payment_link_url: str
    status: str
    amount_minor: int
    currency: str
    created_at: int
    expired_at: int | None = None
    raw_response: dict[str, Any] = field(default_factory=dict)


class PaymentProvider(abc.ABC):
    """Abstract interface for payment provider integration."""

    @abc.abstractmethod
    def create_payment_link(self, request: PaymentLinkRequest) -> PaymentLinkResult:
        """Create a payment link for the given request."""
        pass

    @abc.abstractmethod
    def get_payment_link(self, provider_id: str) -> PaymentLinkResult:
        """Fetch an existing payment link."""
        pass
