from decimal import Decimal
from urllib.parse import urlencode

import pytest

from app.config.settings import settings
from app.payments import registry
from app.payments.base import CheckoutCustomer, CheckoutRequest, PaymentProviderError
from app.payments.constants import PaymentStatus
from app.payments.providers.payhere import PayHereProvider, format_amount

MERCHANT_ID = "1239021"
SECRET = "testsecret"
# Hand-computed with md5sum: UPPER(MD5("testsecret")) and the two derived values below.
SECRET_MD5 = "217DF19D942A4A990EBEED63A983292F"
KNOWN_HASH = "470513B35C017BCF053A03B76D0D6B60"  # 1239021 + ORD-1 + 1000.00 + LKR + SECRET_MD5
KNOWN_SIG = "322AA2686A5FC7B349BB5E29336060C9"  # 1239021 + ORD-1 + 1000.00 + LKR + 2 + SECRET_MD5


@pytest.fixture
def provider(monkeypatch):
    monkeypatch.setattr(settings, "PUBLIC_API_URL", "https://api.example.com/")
    monkeypatch.setattr(settings, "CLIENT_RETURN_URL", "http://localhost:3000/payment/return")
    monkeypatch.setattr(settings, "CLIENT_CANCEL_URL", "http://localhost:3000/payment/cancel")
    return PayHereProvider(MERCHANT_ID, SECRET, "sandbox")


def _request(**overrides):
    base = dict(
        order_id="ORD-1",
        amount=Decimal("1000"),
        currency="LKR",
        description="Airport transfer",
        customer=CheckoutCustomer("Ada", "Lovelace", "ada@example.com", "0771234567"),
        internal_payment_id="pay-1",
        internal_reference="TR-1",
    )
    base.update(overrides)
    return CheckoutRequest(**base)


def _notification(**overrides):
    data = {
        "merchant_id": MERCHANT_ID,
        "order_id": "ORD-1",
        "payment_id": "320032",
        "payhere_amount": "1000.00",
        "payhere_currency": "LKR",
        "status_code": "2",
        "md5sig": KNOWN_SIG,
        "custom_1": "pay-1",
    }
    data.update(overrides)
    return urlencode(data).encode()


def test_secret_md5_matches_hand_computed(provider):
    assert provider._secret_md5 == SECRET_MD5


def test_checkout_hash_matches_hand_computed_value(provider):
    instructions = provider.create_checkout(_request())
    assert instructions.fields["hash"] == KNOWN_HASH
    assert instructions.fields["amount"] == "1000.00"
    assert instructions.method == "POST"
    assert instructions.url == "https://sandbox.payhere.lk/pay/checkout"
    assert instructions.fields["notify_url"] == "https://api.example.com/api/v1/payments/payhere/notify"
    assert instructions.fields["custom_1"] == "pay-1"


def test_live_mode_uses_live_url(monkeypatch):
    live = PayHereProvider(MERCHANT_ID, SECRET, "live")
    assert live.checkout_url == "https://www.payhere.lk/pay/checkout"


@pytest.mark.parametrize(
    "value,expected",
    [(Decimal("1000"), "1000.00"), (Decimal("12.5"), "12.50"), (Decimal("1234.567"), "1234.57")],
)
def test_amount_has_two_decimals_and_no_separator(value, expected):
    assert format_amount(value) == expected


def test_unsupported_currency_rejected(provider):
    with pytest.raises(PaymentProviderError):
        provider.create_checkout(_request(currency="JPY"))


def test_zero_amount_rejected(provider):
    with pytest.raises(PaymentProviderError):
        provider.create_checkout(_request(amount=Decimal("0")))


def test_valid_notification_is_accepted(provider):
    event = provider.parse_and_verify_webhook(_notification(), {})
    assert event.signature_valid is True
    assert event.status == PaymentStatus.SUCCEEDED
    assert event.order_id == "ORD-1"
    assert event.amount == Decimal("1000.00")
    assert event.provider_payment_id == "320032"


def test_invalid_signature_rejected(provider):
    event = provider.parse_and_verify_webhook(_notification(md5sig="0" * 32), {})
    assert event.signature_valid is False


def test_missing_signature_rejected(provider):
    event = provider.parse_and_verify_webhook(_notification(md5sig=""), {})
    assert event.signature_valid is False


def test_tampered_amount_rejected(provider):
    event = provider.parse_and_verify_webhook(_notification(payhere_amount="1.00"), {})
    assert event.signature_valid is False


def test_tampered_currency_rejected(provider):
    event = provider.parse_and_verify_webhook(_notification(payhere_currency="USD"), {})
    assert event.signature_valid is False


def test_other_merchant_rejected(provider):
    event = provider.parse_and_verify_webhook(_notification(merchant_id="999"), {})
    assert event.signature_valid is False


def test_garbage_body_does_not_crash(provider):
    event = provider.parse_and_verify_webhook(b"\xff\xfe", {})
    assert event.signature_valid is False


@pytest.mark.parametrize(
    "code,expected",
    [
        ("2", PaymentStatus.SUCCEEDED),
        ("0", PaymentStatus.PENDING),
        ("-1", PaymentStatus.CANCELLED),
        ("-2", PaymentStatus.FAILED),
        ("-3", PaymentStatus.CHARGEDBACK),
    ],
)
def test_status_code_mapping(provider, code, expected):
    sig = provider.notification_signature("ORD-1", "1000.00", "LKR", code)
    event = provider.parse_and_verify_webhook(_notification(status_code=code, md5sig=sig), {})
    assert event.signature_valid is True
    assert event.status == expected


def test_repr_does_not_leak_secret(provider):
    assert SECRET not in repr(provider)
    assert SECRET_MD5 not in repr(provider)


def test_registry_picks_provider_from_config(monkeypatch):
    monkeypatch.setattr(settings, "PAYMENT_PROVIDER", "payhere")
    monkeypatch.setattr(settings, "PAYHERE_MERCHANT_ID", MERCHANT_ID)
    monkeypatch.setattr(settings, "PAYHERE_MERCHANT_SECRET", SECRET)
    monkeypatch.setattr(settings, "PAYHERE_MODE", "sandbox")
    assert isinstance(registry.get_provider(), PayHereProvider)


def test_registry_rejects_unknown_and_disabled(monkeypatch):
    monkeypatch.setattr(settings, "PAYMENT_PROVIDER", "nope")
    with pytest.raises(PaymentProviderError):
        registry.get_provider()
    monkeypatch.setattr(settings, "PAYMENT_PROVIDER", "")
    with pytest.raises(PaymentProviderError):
        registry.get_provider()
