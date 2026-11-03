from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any, Dict, Mapping, Optional

from app.payments.constants import PaymentStatus


class PaymentProviderError(Exception):
    """Raised for configuration or input problems; messages never contain secrets."""


@dataclass(frozen=True)
class CheckoutCustomer:
    first_name: str
    last_name: str
    email: str
    phone: str
    address: str = ""
    city: str = ""
    country: str = "Sri Lanka"


@dataclass(frozen=True)
class CheckoutRequest:
    """Everything a provider needs to start a checkout; built server-side."""

    order_id: str
    amount: Decimal
    currency: str
    description: str
    customer: CheckoutCustomer
    internal_reference: str = ""
    internal_payment_id: str = ""


@dataclass(frozen=True)
class CheckoutInstructions:
    url: str
    method: str  # "POST" form auto-submit, or "GET" redirect
    fields: Dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class NormalizedPaymentEvent:
    provider: str
    signature_valid: bool
    order_id: Optional[str]
    provider_payment_id: Optional[str]
    amount: Optional[Decimal]
    currency: Optional[str]
    status: Optional[PaymentStatus]
    status_code: Optional[str]
    raw: Dict[str, Any]


class PaymentProvider(ABC):
    name: str

    @abstractmethod
    def create_checkout(self, request: CheckoutRequest) -> CheckoutInstructions:
        ...

    @abstractmethod
    def parse_and_verify_webhook(
        self, raw_body: bytes, headers: Mapping[str, str]
    ) -> NormalizedPaymentEvent:
        ...

    def refund(self, provider_payment_id: str, amount: Decimal):
        raise NotImplementedError("Refunds are not implemented for this provider yet")
