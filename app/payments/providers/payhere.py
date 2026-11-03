import hashlib
import hmac
from decimal import Decimal, InvalidOperation
from typing import Mapping
from urllib.parse import parse_qsl

from app.config.settings import settings
from app.payments.base import (
    CheckoutInstructions,
    CheckoutRequest,
    NormalizedPaymentEvent,
    PaymentProvider,
    PaymentProviderError,
)
from app.payments.constants import PaymentStatus

SANDBOX_URL = "https://sandbox.payhere.lk/pay/checkout"
LIVE_URL = "https://www.payhere.lk/pay/checkout"
SUPPORTED_CURRENCIES = frozenset({"LKR", "USD", "GBP", "EUR", "AUD"})

STATUS_CODE_MAP = {
    "2": PaymentStatus.SUCCEEDED,
    "0": PaymentStatus.PENDING,
    "-1": PaymentStatus.CANCELLED,
    "-2": PaymentStatus.FAILED,
    "-3": PaymentStatus.CHARGEDBACK,
}


def _md5_upper(value: str) -> str:
    return hashlib.md5(value.encode("utf-8")).hexdigest().upper()


def format_amount(amount: Decimal) -> str:
    """PayHere needs exactly two decimals and no thousands separator."""
    return f"{Decimal(amount).quantize(Decimal('0.01')):f}"


class PayHereProvider(PaymentProvider):
    name = "payhere"

    def __init__(self, merchant_id: str, merchant_secret: str, mode: str = "sandbox"):
        if not merchant_id or not merchant_secret:
            raise PaymentProviderError("PayHere merchant id and secret are required")
        if mode not in ("sandbox", "live"):
            raise PaymentProviderError("PAYHERE_MODE must be 'sandbox' or 'live'")
        self._merchant_id = merchant_id
        self._secret_md5 = _md5_upper(merchant_secret)
        self._mode = mode

    def __repr__(self) -> str:  # never expose the secret
        return f"PayHereProvider(merchant_id={self._merchant_id!r}, mode={self._mode!r})"

    @property
    def checkout_url(self) -> str:
        return SANDBOX_URL if self._mode == "sandbox" else LIVE_URL

    @property
    def notify_path(self) -> str:
        return f"{settings.API_V1_PREFIX}/payments/payhere/notify"

    def checkout_hash(self, order_id: str, amount: str, currency: str) -> str:
        return _md5_upper(f"{self._merchant_id}{order_id}{amount}{currency}{self._secret_md5}")

    def notification_signature(
        self, order_id: str, amount: str, currency: str, status_code: str
    ) -> str:
        return _md5_upper(
            f"{self._merchant_id}{order_id}{amount}{currency}{status_code}{self._secret_md5}"
        )

    def create_checkout(self, request: CheckoutRequest) -> CheckoutInstructions:
        currency = (request.currency or "").upper()
        if currency not in SUPPORTED_CURRENCIES:
            raise PaymentProviderError(
                f"Currency {request.currency!r} is not supported by PayHere "
                f"({', '.join(sorted(SUPPORTED_CURRENCIES))})"
            )
        if request.amount <= 0:
            raise PaymentProviderError("Amount must be greater than zero")

        for name in ("PUBLIC_API_URL", "CLIENT_RETURN_URL", "CLIENT_CANCEL_URL"):
            if not getattr(settings, name):
                raise PaymentProviderError(f"{name} is not configured")

        amount = format_amount(request.amount)
        c = request.customer
        fields = {
            "merchant_id": self._merchant_id,
            "return_url": settings.CLIENT_RETURN_URL,
            "cancel_url": settings.CLIENT_CANCEL_URL,
            "notify_url": settings.PUBLIC_API_URL.rstrip("/") + self.notify_path,
            "order_id": request.order_id,
            "items": request.description,
            "currency": currency,
            "amount": amount,
            "first_name": c.first_name,
            "last_name": c.last_name,
            "email": c.email,
            "phone": c.phone,
            "address": c.address,
            "city": c.city,
            "country": c.country,
            "custom_1": request.internal_payment_id,
            "custom_2": request.internal_reference,
            "hash": self.checkout_hash(request.order_id, amount, currency),
        }
        return CheckoutInstructions(url=self.checkout_url, method="POST", fields=fields)

    def parse_and_verify_webhook(
        self, raw_body: bytes, headers: Mapping[str, str]
    ) -> NormalizedPaymentEvent:
        try:
            data = dict(parse_qsl(raw_body.decode("utf-8"), keep_blank_values=True))
        except UnicodeDecodeError:
            data = {}

        order_id = data.get("order_id")
        amount_str = data.get("payhere_amount")
        currency = data.get("payhere_currency")
        status_code = data.get("status_code")
        merchant_id = data.get("merchant_id")
        received_sig = (data.get("md5sig") or "").upper()

        amount = None
        if amount_str is not None:
            try:
                amount = Decimal(amount_str)
            except InvalidOperation:
                amount = None

        signature_valid = False
        if (
            order_id
            and amount is not None
            and currency
            and status_code is not None
            and received_sig
            and merchant_id == self._merchant_id
        ):
            expected = self.notification_signature(order_id, amount_str, currency, status_code)
            signature_valid = hmac.compare_digest(expected, received_sig)

        return NormalizedPaymentEvent(
            provider=self.name,
            signature_valid=signature_valid,
            order_id=order_id,
            provider_payment_id=data.get("payment_id"),
            amount=amount,
            currency=currency,
            status=STATUS_CODE_MAP.get(status_code or ""),
            status_code=status_code,
            raw=data,
        )
