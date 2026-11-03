import os
from datetime import date, time
from decimal import Decimal
from types import SimpleNamespace
from urllib.parse import urlencode
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID as PGUUID
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

os.environ.setdefault("DATABASE_URL", "sqlite+pysqlite:///:memory:")

from app.config.database import get_db
from app.config.settings import settings
from app.integrations.email_provider import email_provider
from app.models.base import Base
from app.models.bookingInquiry import BookingInquiry
from app.models.enum import BookingUnit, CurrencyCode, InquiryStatus, ListingStatus, ListingType, PricingRuleType
from app.models.listing import Listing
from app.models.listingVariant import ListingVariant
from app.models.pricingRule import PricingRule
from app.models.transportBooking import TransportBooking
from app.payments.models import Payment, PaymentEvent
from app.payments.providers.payhere import PayHereProvider
from app.payments.router import get_optional_user, router


# The production models use Postgres column types; let SQLite stand in for them in tests.
@compiles(PGUUID, "sqlite")
def _uuid(_t, _c, **_kw):
    return "CHAR(32)"


@compiles(JSONB, "sqlite")
def _jsonb(_t, _c, **_kw):
    return "JSON"


@compiles(ARRAY, "sqlite")
def _array(_t, _c, **_kw):
    return "JSON"


TABLES = (
    "users", "vehicle_categories", "transport_bookings", "payments", "payment_events",
    "booking_inquiries", "listings", "listing_variants", "pricing_rules",
)
MERCHANT_ID = "1239021"
SECRET = "testsecret"
OWNER_ID = uuid4()


@pytest.fixture
def session_factory():
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    import app.models  # noqa: F401

    Base.metadata.create_all(engine, tables=[Base.metadata.tables[n] for n in TABLES])
    yield sessionmaker(autocommit=False, autoflush=False, bind=engine)
    engine.dispose()


@pytest.fixture
def config(monkeypatch):
    monkeypatch.setattr(settings, "PAYMENT_PROVIDER", "payhere")
    monkeypatch.setattr(settings, "PAYHERE_MODE", "sandbox")
    monkeypatch.setattr(settings, "PAYHERE_MERCHANT_ID", MERCHANT_ID)
    monkeypatch.setattr(settings, "PAYHERE_MERCHANT_SECRET", SECRET)
    monkeypatch.setattr(settings, "PUBLIC_API_URL", "https://api.example.com")
    monkeypatch.setattr(settings, "CLIENT_RETURN_URL", "http://localhost:3000/payment/return")
    monkeypatch.setattr(settings, "CLIENT_CANCEL_URL", "http://localhost:3000/payment/cancel")


@pytest.fixture
def emails(monkeypatch):
    sent = []
    monkeypatch.setattr(email_provider, "send_transport_payment_received", lambda n: sent.append(n) or True)
    return sent


@pytest.fixture
def current_user():
    return {"user": None}


@pytest.fixture
def client(session_factory, config, emails, current_user):
    app = FastAPI()
    app.include_router(router, prefix="/api/v1/payments")

    def _db():
        db = session_factory()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = _db
    app.dependency_overrides[get_optional_user] = lambda: current_user["user"]
    return TestClient(app)


def make_booking(session_factory, **overrides) -> TransportBooking:
    values = dict(
        booking_reference="TR-20261101-AB12",
        user_id=None,
        vehicle_category_id=uuid4(),
        customer_name="Ada Lovelace",
        customer_email="ada@example.com",
        customer_phone="0771234567",
        pickup_location="Colombo Airport",
        destination_location="Galle",
        travel_date=date(2027, 1, 5),
        pickup_time=time(9, 0),
        base_fare=Decimal("10"),
        price_per_km=Decimal("1"),
        route_price=Decimal("100.00"),
        extra_charges=Decimal("0"),
        total_price=Decimal("100.00"),
        currency="USD",
        booking_status="pending",
        payment_status="unpaid",
    )
    values.update(overrides)
    with session_factory() as db:
        booking = TransportBooking(**values)
        db.add(booking)
        db.commit()
        db.refresh(booking)
        return SimpleNamespace(id=booking.id, reference=booking.booking_reference, email=booking.customer_email)


def guest_body(booking, **overrides):
    body = {
        "target_type": "transport_booking",
        "target_id": str(booking.id),
        "booking_reference": booking.reference,
        "customer_email": booking.email,
    }
    body.update(overrides)
    return body


def signed_notification(order_id, code="2", amount="100.00", currency="USD", **overrides):
    provider = PayHereProvider(MERCHANT_ID, SECRET)
    data = {
        "merchant_id": MERCHANT_ID,
        "order_id": order_id,
        "payment_id": "320032",
        "payhere_amount": amount,
        "payhere_currency": currency,
        "status_code": code,
        "md5sig": provider.notification_signature(order_id, amount, currency, code),
    }
    data.update(overrides)
    return urlencode(data)


def notify(client, body):
    return client.post(
        "/api/v1/payments/payhere/notify",
        content=body,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )


def start_checkout(client, booking):
    res = client.post("/api/v1/payments/checkout", json=guest_body(booking))
    assert res.status_code == 200, res.text
    return res.json()


def reload(session_factory, booking):
    with session_factory() as db:
        b = db.get(TransportBooking, booking.id)
        p = db.execute(select(Payment)).scalars().first()
        events = db.execute(select(PaymentEvent)).scalars().all()
        return b.payment_status, b.booking_status, (p.status if p else None), events


def test_checkout_uses_server_side_amount_and_ignores_client_amount(client, session_factory):
    booking = make_booking(session_factory)
    res = client.post("/api/v1/payments/checkout", json={**guest_body(booking), "amount": "1.00"})
    assert res.status_code == 200
    data = res.json()
    assert data["fields"]["amount"] == "100.00"
    assert data["fields"]["currency"] == "USD"
    assert data["fields"]["custom_1"] == data["payment_id"]
    assert data["url"] == "https://sandbox.payhere.lk/pay/checkout"
    assert "merchant_secret" not in str(data).lower()


def test_checkout_rejects_other_users_booking(client, session_factory, current_user):
    booking = make_booking(session_factory, user_id=OWNER_ID)
    current_user["user"] = SimpleNamespace(id=uuid4(), role="TOURIST")
    res = client.post(
        "/api/v1/payments/checkout",
        json={"target_type": "transport_booking", "target_id": str(booking.id)},
    )
    assert res.status_code == 404


def test_checkout_allows_owner(client, session_factory, current_user):
    booking = make_booking(session_factory, user_id=OWNER_ID)
    current_user["user"] = SimpleNamespace(id=OWNER_ID, role="TOURIST")
    res = client.post(
        "/api/v1/payments/checkout",
        json={"target_type": "transport_booking", "target_id": str(booking.id)},
    )
    assert res.status_code == 200


def test_guest_checkout_needs_matching_reference_and_email(client, session_factory):
    booking = make_booking(session_factory)
    wrong = client.post("/api/v1/payments/checkout", json=guest_body(booking, customer_email="eve@example.com"))
    assert wrong.status_code == 404
    missing = client.post(
        "/api/v1/payments/checkout",
        json={"target_type": "transport_booking", "target_id": str(booking.id)},
    )
    assert missing.status_code == 404


def test_checkout_refuses_already_paid_booking(client, session_factory):
    booking = make_booking(session_factory, payment_status="paid")
    res = client.post("/api/v1/payments/checkout", json=guest_body(booking))
    assert res.status_code == 409


def test_checkout_disabled_when_no_provider(client, session_factory, monkeypatch):
    monkeypatch.setattr(settings, "PAYMENT_PROVIDER", "")
    booking = make_booking(session_factory)
    assert client.post("/api/v1/payments/checkout", json=guest_body(booking)).status_code == 503


def test_success_notification_marks_booking_paid_once(client, session_factory, emails):
    booking = make_booking(session_factory)
    order_id = start_checkout(client, booking)["order_id"]
    body = signed_notification(order_id)

    assert notify(client, body).status_code == 200
    assert notify(client, body).status_code == 200  # PayHere retry

    paid, status, payment_status, events = reload(session_factory, booking)
    assert (paid, status, payment_status) == ("paid", "confirmed", "succeeded")
    assert len(emails) == 1
    assert len(events) == 2 and all(e.signature_valid for e in events)


def test_invalid_signature_changes_nothing_and_is_logged(client, session_factory, emails):
    booking = make_booking(session_factory)
    order_id = start_checkout(client, booking)["order_id"]
    res = notify(client, signed_notification(order_id, md5sig="0" * 32))
    assert res.status_code == 400
    paid, status, payment_status, events = reload(session_factory, booking)
    assert (paid, status, payment_status) == ("unpaid", "pending", "initiated")
    assert len(events) == 1 and events[0].signature_valid is False
    assert emails == []


def test_amount_or_currency_mismatch_rejected(client, session_factory, emails):
    booking = make_booking(session_factory)
    order_id = start_checkout(client, booking)["order_id"]
    assert notify(client, signed_notification(order_id, amount="1.00")).status_code == 400
    assert notify(client, signed_notification(order_id, currency="LKR")).status_code == 400
    paid, _, payment_status, _ = reload(session_factory, booking)
    assert (paid, payment_status) == ("unpaid", "initiated")
    assert emails == []


def test_unknown_order_rejected_but_logged(client, session_factory):
    res = notify(client, signed_notification("TRT-UNKNOWN"))
    assert res.status_code == 400
    with session_factory() as db:
        assert db.execute(select(PaymentEvent)).scalars().all()[0].payment_id is None


@pytest.mark.parametrize(
    "code,expected",
    [("0", "pending"), ("-1", "cancelled"), ("-2", "failed")],
)
def test_non_success_codes_leave_booking_unpaid(client, session_factory, emails, code, expected):
    booking = make_booking(session_factory)
    order_id = start_checkout(client, booking)["order_id"]
    assert notify(client, signed_notification(order_id, code=code)).status_code == 200
    paid, status, payment_status, _ = reload(session_factory, booking)
    assert (paid, status, payment_status) == ("unpaid", "pending", expected)
    assert emails == []


def test_pending_then_success(client, session_factory, emails):
    booking = make_booking(session_factory)
    order_id = start_checkout(client, booking)["order_id"]
    notify(client, signed_notification(order_id, code="0"))
    notify(client, signed_notification(order_id, code="2"))
    paid, _, payment_status, _ = reload(session_factory, booking)
    assert (paid, payment_status) == ("paid", "succeeded")
    assert len(emails) == 1


def test_chargeback_after_success(client, session_factory):
    booking = make_booking(session_factory)
    order_id = start_checkout(client, booking)["order_id"]
    notify(client, signed_notification(order_id, code="2"))
    assert notify(client, signed_notification(order_id, code="-3")).status_code == 200
    paid, _, payment_status, _ = reload(session_factory, booking)
    assert (paid, payment_status) == ("chargedback", "chargedback")


def test_failure_after_success_is_ignored(client, session_factory):
    booking = make_booking(session_factory)
    order_id = start_checkout(client, booking)["order_id"]
    notify(client, signed_notification(order_id, code="2"))
    assert notify(client, signed_notification(order_id, code="-2")).status_code == 200
    paid, _, payment_status, _ = reload(session_factory, booking)
    assert (paid, payment_status) == ("paid", "succeeded")


def test_email_failure_does_not_fail_webhook(client, session_factory, monkeypatch):
    def boom(_notice):
        raise RuntimeError("smtp down")

    monkeypatch.setattr(email_provider, "send_transport_payment_received", boom)
    booking = make_booking(session_factory)
    order_id = start_checkout(client, booking)["order_id"]
    assert notify(client, signed_notification(order_id)).status_code == 200
    paid, _, _, _ = reload(session_factory, booking)
    assert paid == "paid"


def test_status_endpoint_for_guest_and_wrong_email(client, session_factory):
    booking = make_booking(session_factory)
    data = start_checkout(client, booking)
    url = f"/api/v1/payments/{data['payment_id']}/status"
    ok = client.get(url, params={"email": "ADA@example.com"})
    assert ok.status_code == 200 and ok.json()["status"] == "initiated"
    assert client.get(url, params={"email": "eve@example.com"}).status_code == 404
    assert client.get(url).status_code == 404


def test_status_endpoint_for_admin(client, session_factory, current_user):
    booking = make_booking(session_factory)
    data = start_checkout(client, booking)
    current_user["user"] = SimpleNamespace(id=uuid4(), role="ADMIN")
    assert client.get(f"/api/v1/payments/{data['payment_id']}/status").status_code == 200


# ---- cart inquiries (stays, packages, safaris, experiences) -------------------------------

def make_inquiry(session_factory, price=100.0, listing_price=100.0, total=1.0, status=InquiryStatus.PENDING_CONTACT):
    """An inquiry whose stored total is deliberately wrong; only database prices may be charged."""
    with session_factory() as db:
        listing = Listing(
            destination_id=uuid4(), listing_type=ListingType.SAFARI, title="Yala safari",
            status=ListingStatus.PUBLISHED, base_currency=CurrencyCode.USD,
        )
        db.add(listing)
        db.flush()
        variant = ListingVariant(listing_id=listing.id, name="Morning", booking_unit=BookingUnit.PER_GROUP)
        db.add(variant)
        db.flush()
        db.add(PricingRule(
            variant_id=variant.id, pricing_rule_type=PricingRuleType.FIXED, min_guest=1, max_guest=8,
            amount=listing_price, currency=CurrencyCode.USD, priority=1,
        ))
        inquiry = BookingInquiry(
            reference="INQ-TEST0001", first_name="Ada", last_name="Lovelace", email="ada@example.com",
            phone="0771234567", nationality="UK", number_of_travelers=2, subtotal=total, total=total,
            currency=CurrencyCode.USD, status=status,
            cart_items=[{
                "listing_id": str(listing.id), "title": "Yala safari", "travel_date": "2027-03-01T09:00:00",
                "travel_count": 1, "price": price, "base_currency": "USD",
            }],
        )
        db.add(inquiry)
        db.commit()
        db.refresh(inquiry)
        return SimpleNamespace(id=inquiry.id, reference=inquiry.reference, email=inquiry.email)


def inquiry_body(inquiry, **overrides):
    body = {
        "target_type": "booking_inquiry",
        "target_id": str(inquiry.id),
        "booking_reference": inquiry.reference,
        "customer_email": inquiry.email,
    }
    body.update(overrides)
    return body


def test_inquiry_checkout_charges_database_price_not_stored_total(client, session_factory):
    inquiry = make_inquiry(session_factory, price=100.0, listing_price=100.0, total=1.0)
    res = client.post("/api/v1/payments/checkout", json=inquiry_body(inquiry))
    assert res.status_code == 200, res.text
    data = res.json()
    assert data["fields"]["amount"] == "112.00"  # 100.00 + 12% tax; the inquiry's own total was 1.00
    assert Decimal(str(data["amount"])) == Decimal("112.00") and data["currency"] == "USD"


def test_inquiry_checkout_rejects_cheaper_cart_price(client, session_factory):
    inquiry = make_inquiry(session_factory, price=10.0, listing_price=100.0)
    res = client.post("/api/v1/payments/checkout", json=inquiry_body(inquiry))
    assert res.status_code == 409


def test_inquiry_checkout_rejects_changed_expected_amount(client, session_factory):
    inquiry = make_inquiry(session_factory)
    assert client.post("/api/v1/payments/checkout", json=inquiry_body(inquiry, expected_amount="50.00")).status_code == 409
    assert client.post("/api/v1/payments/checkout", json=inquiry_body(inquiry, expected_amount="112.00")).status_code == 200


def test_inquiry_checkout_needs_reference_and_email(client, session_factory):
    inquiry = make_inquiry(session_factory)
    assert client.post("/api/v1/payments/checkout", json=inquiry_body(inquiry, customer_email="eve@example.com")).status_code == 404
    assert client.post("/api/v1/payments/checkout", json=inquiry_body(inquiry, booking_reference="INQ-OTHER")).status_code == 404


def test_cancelled_inquiry_cannot_be_paid(client, session_factory):
    inquiry = make_inquiry(session_factory, status=InquiryStatus.CANCELLED)
    assert client.post("/api/v1/payments/checkout", json=inquiry_body(inquiry)).status_code == 409


def test_inquiry_payment_success_sends_receipt_and_team_alert_once(client, session_factory, monkeypatch):
    receipts, alerts = [], []
    monkeypatch.setattr(email_provider, "send_inquiry_payment_received", lambda n: receipts.append(n) or True)
    monkeypatch.setattr(email_provider, "send_inquiry_payment_team_alert", lambda n: alerts.append(n) or True)
    inquiry = make_inquiry(session_factory)
    order_id = client.post("/api/v1/payments/checkout", json=inquiry_body(inquiry)).json()["order_id"]
    body = signed_notification(order_id, amount="112.00")
    assert notify(client, body).status_code == 200
    assert notify(client, body).status_code == 200  # retry
    assert len(receipts) == 1 and len(alerts) == 1
    assert receipts[0].booking_reference == "INQ-TEST0001" and receipts[0].customer_name == "Ada Lovelace"
    with session_factory() as db:
        assert db.execute(select(Payment)).scalars().first().status == "succeeded"
        assert db.get(BookingInquiry, inquiry.id).status == InquiryStatus.PENDING_CONTACT  # workflow untouched


def test_inquiry_status_endpoint_for_guest(client, session_factory):
    inquiry = make_inquiry(session_factory)
    data = client.post("/api/v1/payments/checkout", json=inquiry_body(inquiry)).json()
    url = f"/api/v1/payments/{data['payment_id']}/status"
    assert client.get(url, params={"email": inquiry.email}).status_code == 200
    assert client.get(url, params={"email": "eve@example.com"}).status_code == 404
