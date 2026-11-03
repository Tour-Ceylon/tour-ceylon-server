"""Approve-then-pay for stays: the emailed pay link, from approval to the booking being marked paid."""
import os
from datetime import datetime, timedelta, timezone
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

from app.api.deps import get_current_user
from app.api.v1 import vendor_booking_inquiries
from app.config.database import get_db
from app.config.settings import settings
from app.integrations.email_provider import EmailProvider, email_provider
from app.models.base import Base
from app.models.booking import Booking
from app.models.bookingInquiry import BookingInquiry
from app.models.enum import (
    BookingStatus, BookingUnit, CurrencyCode, InquiryStatus, ListingStatus, ListingType,
    PaymentMethod, PaymentTransactionStatus, PricingRuleType,
)
from app.models.listing import Listing
from app.models.listingVariant import ListingVariant
from app.models.pricingRule import PricingRule
from app.models.stay import StayProperty, StayRoomType
from app.payments import links, offers
from app.payments.errors import PaymentError
from app.payments.models import Payment
from app.payments.providers.payhere import PayHereProvider
from app.payments.router import get_optional_user, router as payments_router
from app.services.inquiry_approval import notify_inquiry_approved


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
    "users", "bookings", "booking_inquiries", "listings", "listing_variants", "pricing_rules",
    "stay_properties", "stay_room_types", "payments", "payment_events",
)
MERCHANT_ID = "1239021"
SECRET = "testsecret"


@pytest.fixture
def session_factory():
    engine = create_engine(
        "sqlite+pysqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool,
    )
    import app.models  # noqa: F401

    Base.metadata.create_all(engine, tables=[Base.metadata.tables[n] for n in TABLES])
    yield sessionmaker(autocommit=False, autoflush=False, bind=engine)
    engine.dispose()


@pytest.fixture(autouse=True)
def config(monkeypatch):
    monkeypatch.setattr(settings, "PAYMENT_PROVIDER", "payhere")
    monkeypatch.setattr(settings, "PAYHERE_MODE", "sandbox")
    monkeypatch.setattr(settings, "PAYHERE_MERCHANT_ID", MERCHANT_ID)
    monkeypatch.setattr(settings, "PAYHERE_MERCHANT_SECRET", SECRET)
    monkeypatch.setattr(settings, "PUBLIC_API_URL", "https://api.example.com")
    monkeypatch.setattr(settings, "CLIENT_RETURN_URL", "https://www.example.com/payment/return")
    monkeypatch.setattr(settings, "CLIENT_CANCEL_URL", "https://www.example.com/payment/cancel")
    monkeypatch.setattr(settings, "CLIENT_APP_URL", "https://www.example.com")
    monkeypatch.setattr(settings, "SECRET_KEY", "a-long-random-test-secret-key-value")
    monkeypatch.setattr(settings, "PAYMENT_LINK_TTL_HOURS", 72)


@pytest.fixture
def emails(monkeypatch):
    sent = {"pay_request": [], "accepted": [], "receipt": [], "team": []}
    monkeypatch.setattr(email_provider, "send_stay_payment_request", lambda i, o: sent["pay_request"].append((i, o)) or True)
    monkeypatch.setattr(email_provider, "send_vendor_booking_accepted_email", lambda i: sent["accepted"].append(i) or True)
    monkeypatch.setattr(email_provider, "send_inquiry_payment_received", lambda n: sent["receipt"].append(n) or True)
    monkeypatch.setattr(email_provider, "send_inquiry_payment_team_alert", lambda n: sent["team"].append(n) or True)
    return sent


@pytest.fixture
def admin():
    return {"user": SimpleNamespace(id=uuid4(), role="ADMIN")}


@pytest.fixture
def client(session_factory, emails, admin):
    app = FastAPI()
    app.include_router(payments_router, prefix="/api/v1/payments")
    app.include_router(vendor_booking_inquiries.router, prefix="/api/v1/vendor/booking-inquiries")

    def _db():
        db = session_factory()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = _db
    app.dependency_overrides[get_optional_user] = lambda: None
    app.dependency_overrides[get_current_user] = lambda: admin["user"]
    return TestClient(app)


def make_stay_inquiry(session_factory, status=InquiryStatus.PENDING_CONTACT, with_booking=True):
    """2 x Deluxe at 100.00 a night for 3 nights: 600.00 + 12% tax = 672.00."""
    with session_factory() as db:
        listing = Listing(destination_id=uuid4(), listing_type=ListingType.HOTEL, title="Test Beach Hotel",
                          status=ListingStatus.PUBLISHED, base_currency=CurrencyCode.USD)
        db.add(listing)
        db.flush()
        prop = StayProperty(listing_id=listing.id, name="Test Beach Hotel", property_type="hotel")
        db.add(prop)
        db.flush()
        room = StayRoomType(property_id=prop.id, name="Deluxe", base_price=Decimal("100.00"), currency="USD")
        db.add(room)
        db.flush()
        booking = None
        if with_booking:
            booking = Booking(
                booking_reference="BKG-1", user_id=uuid4(), status=BookingStatus.PENDING, total_amount=Decimal("600"),
                currency=CurrencyCode.USD, payment_method=PaymentMethod.PAY_AT_PROPERTY,
                payment_status=PaymentTransactionStatus.PENDING, booked_at=datetime.utcnow(),
            )
            db.add(booking)
            db.flush()
        inquiry = BookingInquiry(
            reference="STY-TEST0001", first_name="Ada", last_name="Lovelace", email="ada@example.com",
            phone="0771234567", nationality="UK", number_of_travelers=2, subtotal=200, total=224,
            currency=CurrencyCode.USD, status=status, booking_id=booking.id if booking else None,
            cart_items=[{
                "listing_id": str(listing.id), "title": "Test Beach Hotel", "travel_date": "2027-03-01T00:00:00",
                "travel_date_end": "2027-03-04T00:00:00", "travel_count": 2, "price": 200, "base_currency": "USD",
                "selected_rooms": [{"roomId": str(room.id), "roomName": "Deluxe", "qty": 2, "price": 100}],
            }],
        )
        db.add(inquiry)
        db.commit()
        return SimpleNamespace(id=inquiry.id, reference=inquiry.reference, email=inquiry.email,
                               booking_id=booking.id if booking else None)


def approve(session_factory, inquiry, status=InquiryStatus.QUOTED):
    with session_factory() as db:
        db.get(BookingInquiry, inquiry.id).status = status
        db.commit()


def signed(order_id, amount, code="2"):
    sig = PayHereProvider(MERCHANT_ID, SECRET).notification_signature(order_id, amount, "USD", code)
    return urlencode({"merchant_id": MERCHANT_ID, "order_id": order_id, "payment_id": "320032",
                      "payhere_amount": amount, "payhere_currency": "USD", "status_code": code, "md5sig": sig})


def token_for(inquiry):
    return links.create_payment_token(inquiry.id)[0]


# ---- links ----------------------------------------------------------------------------------

def test_token_round_trip_and_expiry(monkeypatch):
    inquiry_id = uuid4()
    token, expires_at = links.create_payment_token(inquiry_id)
    assert links.read_payment_token(token) == inquiry_id
    assert timedelta(hours=71) < expires_at - datetime.now(timezone.utc) <= timedelta(hours=72)
    assert links.payment_url(token) == f"https://www.example.com/pay/{token}"

    monkeypatch.setattr(settings, "PAYMENT_LINK_TTL_HOURS", -1)
    expired, _ = links.create_payment_token(inquiry_id)
    with pytest.raises(PaymentError) as err:
        links.read_payment_token(expired)
    assert err.value.status_code == 410


def test_tampered_or_foreign_token_is_rejected(monkeypatch):
    token, _ = links.create_payment_token(uuid4())
    for bad in (token + "x", token[:-3] + "abc", "not-a-token", ""):
        with pytest.raises(PaymentError) as err:
            links.read_payment_token(bad)
        assert err.value.status_code == 404
    monkeypatch.setattr(settings, "SECRET_KEY", "another-secret-key-entirely-different")
    with pytest.raises(PaymentError):
        links.read_payment_token(token)


# ---- approve, then pay ----------------------------------------------------------------------

def test_stay_cannot_be_paid_before_the_team_approves(client, session_factory):
    inquiry = make_stay_inquiry(session_factory)
    body = {"target_type": "booking_inquiry", "target_id": str(inquiry.id),
            "booking_reference": inquiry.reference, "customer_email": inquiry.email}
    res = client.post("/api/v1/payments/checkout", json=body)
    assert res.status_code == 409 and "confirms availability" in res.json()["detail"]
    approve(session_factory, inquiry)
    assert client.post("/api/v1/payments/checkout", json=body).status_code == 200


def test_offer_only_for_approved_unpaid_stays(session_factory, monkeypatch):
    inquiry = make_stay_inquiry(session_factory)
    with session_factory() as db:
        assert offers.build_inquiry_offer(db, db.get(BookingInquiry, inquiry.id)) is None  # not approved yet
    approve(session_factory, inquiry)
    with session_factory() as db:
        offer = offers.build_inquiry_offer(db, db.get(BookingInquiry, inquiry.id))
        assert offer is not None
        assert offer.amount == Decimal("672.00") and offer.currency == "USD"
        assert offer.url.startswith("https://www.example.com/pay/")
        assert offer.lines[0].nights == 3 and offer.lines[0].rooms == [{"name": "Deluxe", "qty": 2}]
        monkeypatch.setattr(settings, "PAYMENT_PROVIDER", "")
        assert offers.build_inquiry_offer(db, db.get(BookingInquiry, inquiry.id)) is None  # payments off


def test_approval_emails_a_pay_link_for_a_stay_and_the_usual_email_otherwise(session_factory, emails):
    inquiry = make_stay_inquiry(session_factory, status=InquiryStatus.QUOTED)
    with session_factory() as db:
        notify_inquiry_approved(db, db.get(BookingInquiry, inquiry.id))
    assert len(emails["pay_request"]) == 1 and emails["accepted"] == []
    detailed, offer = emails["pay_request"][0]
    assert detailed.reference == "STY-TEST0001" and offer.amount == Decimal("672.00")

    # a tour-only request keeps the existing confirmation email
    with session_factory() as db:
        tour = Listing(destination_id=uuid4(), listing_type=ListingType.TOUR, title="Tour",
                       status=ListingStatus.PUBLISHED, base_currency=CurrencyCode.USD)
        db.add(tour)
        db.flush()
        variant = ListingVariant(listing_id=tour.id, name="Standard", booking_unit=BookingUnit.PER_PERSON)
        db.add(variant)
        db.flush()
        db.add(PricingRule(variant_id=variant.id, pricing_rule_type=PricingRuleType.PER_PERSON, min_guest=1,
                           max_guest=9, amount=50.0, currency=CurrencyCode.USD, priority=1))
        other = BookingInquiry(
            reference="TOU-1", first_name="B", last_name="C", email="b@example.com", phone="1", nationality="X",
            number_of_travelers=1, subtotal=50, total=56, currency=CurrencyCode.USD, status=InquiryStatus.QUOTED,
            cart_items=[{"listing_id": str(tour.id), "title": "Tour", "travel_date": "2027-03-01T00:00:00",
                         "travel_count": 1, "price": 50, "base_currency": "USD"}],
        )
        db.add(other)
        db.commit()
        notify_inquiry_approved(db, other)
    assert len(emails["accepted"]) == 1 and len(emails["pay_request"]) == 1


def test_pay_email_contains_link_total_and_expiry(session_factory, monkeypatch):
    inquiry = make_stay_inquiry(session_factory, status=InquiryStatus.QUOTED)
    sent = []
    provider = EmailProvider()
    provider.smtp_configured = True
    provider.email_from = "noreply@example.com"
    monkeypatch.setattr(provider, "_send_message_smtp", lambda msg: sent.append(msg))
    with session_factory() as db:
        row = db.get(BookingInquiry, inquiry.id)
        from app.services.booking_inquiry_service import BookingInquiryService
        detailed = BookingInquiryService(db).get_inquiry_by_id(row.id)
        offer = offers.build_inquiry_offer(db, row)
    assert provider.send_stay_payment_request(detailed, offer) is True
    message = sent[0]
    assert message["To"] == "ada@example.com" and "STY-TEST0001" in message["Subject"]
    plain = message.get_payload()[0].get_payload(decode=True).decode()
    html = message.get_payload()[1].get_payload(decode=True).decode()
    for text in (plain, html):
        assert "672.00 USD" in text and "/pay/" in text
    assert "2 x Deluxe" in plain and "3 night(s)" in plain


# ---- the pay page and its checkout ----------------------------------------------------------

def test_pay_link_summary_states(client, session_factory):
    inquiry = make_stay_inquiry(session_factory)
    token = token_for(inquiry)
    url = f"/api/v1/payments/pay-link/{token}"

    data = client.get(url).json()
    assert data["state"] == "not_approved" and "confirms availability" in data["message"]

    approve(session_factory, inquiry)
    data = client.get(url).json()
    assert data["state"] == "ready" and Decimal(str(data["amount"])) == Decimal("672.00")
    assert data["lines"][0]["nights"] == 3 and data["lines"][0]["rooms"] == [{"name": "Deluxe", "qty": 2}]
    assert data["customer_email"] == "ada@example.com"

    approve(session_factory, inquiry, InquiryStatus.CANCELLED)
    assert client.get(url).json()["state"] == "cancelled"

    assert client.get("/api/v1/payments/pay-link/garbage").status_code == 404


def test_expired_link_is_gone(client, session_factory, monkeypatch):
    inquiry = make_stay_inquiry(session_factory, status=InquiryStatus.QUOTED)
    monkeypatch.setattr(settings, "PAYMENT_LINK_TTL_HOURS", -1)
    token = token_for(inquiry)
    assert client.get(f"/api/v1/payments/pay-link/{token}").status_code == 410
    assert client.post(f"/api/v1/payments/pay-link/{token}/checkout").status_code == 410


def test_link_checkout_requires_approval_and_charges_the_server_price(client, session_factory):
    inquiry = make_stay_inquiry(session_factory)
    token = token_for(inquiry)
    assert client.post(f"/api/v1/payments/pay-link/{token}/checkout").status_code == 409
    approve(session_factory, inquiry)
    res = client.post(f"/api/v1/payments/pay-link/{token}/checkout")
    assert res.status_code == 200, res.text
    data = res.json()
    assert data["fields"]["amount"] == "672.00" and data["fields"]["currency"] == "USD"
    assert data["url"] == "https://sandbox.payhere.lk/pay/checkout"


def test_payment_success_marks_the_booking_paid_and_closes_the_link(client, session_factory, emails):
    inquiry = make_stay_inquiry(session_factory, status=InquiryStatus.QUOTED)
    token = token_for(inquiry)
    order_id = client.post(f"/api/v1/payments/pay-link/{token}/checkout").json()["order_id"]

    res = client.post("/api/v1/payments/payhere/notify", content=signed(order_id, "672.00"),
                      headers={"Content-Type": "application/x-www-form-urlencoded"})
    assert res.status_code == 200

    with session_factory() as db:
        assert db.execute(select(Payment)).scalars().first().status == "succeeded"
        booking = db.get(Booking, inquiry.booking_id)
        assert booking.payment_status == PaymentTransactionStatus.SUCCEEDED
        assert booking.payment_method == PaymentMethod.ONLINE
    assert len(emails["receipt"]) == 1 and len(emails["team"]) == 1

    assert client.get(f"/api/v1/payments/pay-link/{token}").json()["state"] == "paid"
    assert client.post(f"/api/v1/payments/pay-link/{token}/checkout").status_code == 409


def test_chargeback_is_recorded_on_the_booking(client, session_factory):
    inquiry = make_stay_inquiry(session_factory, status=InquiryStatus.QUOTED)
    order_id = client.post(f"/api/v1/payments/pay-link/{token_for(inquiry)}/checkout").json()["order_id"]
    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    client.post("/api/v1/payments/payhere/notify", content=signed(order_id, "672.00", "2"), headers=headers)
    client.post("/api/v1/payments/payhere/notify", content=signed(order_id, "672.00", "-3"), headers=headers)
    with session_factory() as db:
        assert db.get(Booking, inquiry.booking_id).payment_status == PaymentTransactionStatus.REFUNDED


# ---- resend from the portal ------------------------------------------------------------------

def test_resend_payment_link_endpoint(client, session_factory, emails):
    inquiry = make_stay_inquiry(session_factory)
    url = f"/api/v1/vendor/booking-inquiries/{inquiry.id}/payment-link"
    assert client.post(url).status_code == 409  # not approved yet

    approve(session_factory, inquiry)
    res = client.post(url)
    assert res.status_code == 200, res.text
    data = res.json()
    assert data["sent"] is True and "/pay/" in data["paymentUrl"]
    assert len(emails["pay_request"]) == 1
    token = data["paymentUrl"].rsplit("/", 1)[1]
    assert links.read_payment_token(token) == inquiry.id


def test_vendor_list_reports_payment_status(client, session_factory):
    inquiry = make_stay_inquiry(session_factory, status=InquiryStatus.QUOTED)
    order_id = client.post(f"/api/v1/payments/pay-link/{token_for(inquiry)}/checkout").json()["order_id"]
    client.post("/api/v1/payments/payhere/notify", content=signed(order_id, "672.00"),
                headers={"Content-Type": "application/x-www-form-urlencoded"})
    res = client.get("/api/v1/vendor/booking-inquiries/")
    assert res.status_code == 200, res.text
    assert res.json()["items"][0]["paymentStatus"] == "succeeded"
