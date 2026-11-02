"""Inquiry lifecycle (FEAT-1), notifications (NOTIF-1), server totals (FLOW-3),
customer self-service (FLOW-2/6/7) and quote requests (FLOW-4)."""
import os
from datetime import datetime
from decimal import Decimal
from types import SimpleNamespace

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID as PGUUID
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

os.environ.setdefault("DATABASE_URL", "sqlite+pysqlite:///:memory:")

from app.api.v1 import booking_inquiries
from app.config.database import get_db
from app.models.base import Base
from app.models.bookingInquiry import BookingInquiry
from app.models.enum import InquiryStatus, PaymentMethod
from app.models.notification import ClientNotification
from app.schemas.booking_inquiry_schema import BookingInquiryCreate, QuoteRequestCreate
from app.services.booking_inquiry_service import BookingInquiryService
from app.services.inquiry_totals import compute_totals


@compiles(PGUUID, "sqlite")
def _uuid(_t, _c, **_kw):
    return "CHAR(32)"


@compiles(JSONB, "sqlite")
def _jsonb(_t, _c, **_kw):
    return "JSON"


@compiles(ARRAY, "sqlite")
def _array(_t, _c, **_kw):
    return "JSON"


TABLES = ("users", "bookings", "booking_inquiries", "client_notifications", "listings", "stay_properties")


@pytest.fixture
def db():
    engine = create_engine(
        "sqlite+pysqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool,
    )
    import app.models  # noqa: F401

    Base.metadata.create_all(engine, tables=[Base.metadata.tables[n] for n in TABLES])
    session = sessionmaker(autocommit=False, autoflush=False, bind=engine)()
    yield session
    session.close()


def make_create(**overrides):
    payload = {
        "firstName": "Asha", "lastName": "Perera", "email": "Asha@Example.com", "phone": "0771234567",
        "nationality": "LK", "numberOfTravelers": 2, "paymentMethod": "bank_transfer",
        "cartItems": [{
            "listingId": "tour-1", "title": "Ella day tour", "travelDate": "2026-12-01",
            "travelCount": 2, "price": 100, "baseCurrency": "USD",
        }],
        "subtotal": 1, "total": 1, "currency": "USD",   # deliberately wrong: the server must ignore these
    }
    payload.update(overrides)
    return BookingInquiryCreate(**payload)


def make_inquiry(db, **overrides) -> BookingInquiry:
    service = BookingInquiryService(db)
    created = service.create_inquiry(make_create(**overrides))
    return db.get(BookingInquiry, created.id)


# ---- FLOW-3: totals ----

def item(**kw):
    base = dict(price=Decimal("100"), travel_count=1, travel_date=datetime(2026, 12, 1),
                travel_date_end=None, selected_rooms=None, base_currency="USD")
    base.update(kw)
    return SimpleNamespace(**base)


def test_three_night_stay_is_priced_per_night_times_nights():
    stay = item(selected_rooms=[{"qty": 1}], travel_date_end=datetime(2026, 12, 4))
    totals = compute_totals([stay])
    assert totals.subtotal == Decimal("300.00")
    assert totals.taxes == Decimal("36.00")
    assert totals.total == Decimal("336.00")


def test_tour_is_priced_per_traveler():
    assert compute_totals([item(travel_count=3)]).subtotal == Decimal("300.00")


def test_server_ignores_client_totals(db):
    inquiry = make_inquiry(db)
    assert inquiry.subtotal == Decimal("200.00")      # 100 x 2 travelers, not the submitted 1
    assert inquiry.total == Decimal("224.00")          # + 12% tax


# ---- FLOW-1: payment method ----

def test_payment_method_is_stored_as_a_field(db):
    inquiry = make_inquiry(db)
    assert inquiry.payment_method == PaymentMethod.BANK_TRANSFER.value
    assert "Payment Preference" not in (inquiry.special_requests or "")


def test_unknown_payment_method_is_rejected():
    with pytest.raises(Exception):
        make_create(paymentMethod="cash_in_a_bag")


# ---- FEAT-1 / NOTIF-1: lifecycle and notifications ----

def notifications(db):
    return db.execute(select(ClientNotification)).scalars().all()


def test_full_lifecycle_and_notifications(db):
    inquiry = make_inquiry(db)
    service = BookingInquiryService(db)

    service.transition_status(inquiry, InquiryStatus.CONTACTED)
    assert inquiry.status == InquiryStatus.CONTACTED
    assert notifications(db) == []                        # "contacted" needs no notification

    service.transition_status(inquiry, InquiryStatus.QUOTED)
    assert [n.type.value for n in notifications(db)] == ["booking_quoted"]
    assert notifications(db)[0].recipient_email.lower() == "asha@example.com"

    service.transition_status(inquiry, InquiryStatus.CONVERTED_TO_BOOKING)
    assert "booking_confirmed" in [n.type.value for n in notifications(db)]

    service.transition_status(inquiry, InquiryStatus.CANCELLED)
    assert "booking_cancelled" in [n.type.value for n in notifications(db)]


def test_cancelled_is_final(db):
    inquiry = make_inquiry(db)
    service = BookingInquiryService(db)
    service.transition_status(inquiry, InquiryStatus.CANCELLED)
    with pytest.raises(HTTPException) as err:
        service.transition_status(inquiry, InquiryStatus.QUOTED)
    assert err.value.status_code == 409


def test_same_status_is_a_noop_and_does_not_duplicate_notifications(db):
    inquiry = make_inquiry(db)
    service = BookingInquiryService(db)
    service.transition_status(inquiry, InquiryStatus.CANCELLED)
    service.transition_status(inquiry, InquiryStatus.CANCELLED)
    assert len(notifications(db)) == 1


# ---- FLOW-2 / FLOW-6 / FLOW-7: customer self-service ----

def test_lists_my_inquiries_by_email_case_insensitively(db):
    make_inquiry(db)
    service = BookingInquiryService(db)
    assert len(service.list_inquiries_for_email("asha@EXAMPLE.com")) == 1
    assert service.list_inquiries_for_email("someone@else.com") == []


def test_customer_cancel_needs_matching_email(db):
    inquiry = make_inquiry(db)
    service = BookingInquiryService(db)
    assert service.cancel_for_customer(inquiry.reference, "wrong@example.com") is None
    view = service.cancel_for_customer(inquiry.reference, "asha@example.com")
    assert view.status == InquiryStatus.CANCELLED
    assert "booking_cancelled" in [n.type.value for n in notifications(db)]


def test_customer_cannot_cancel_a_confirmed_booking(db):
    inquiry = make_inquiry(db)
    service = BookingInquiryService(db)
    service.transition_status(inquiry, InquiryStatus.CONVERTED_TO_BOOKING)
    with pytest.raises(HTTPException) as err:
        service.cancel_for_customer(inquiry.reference, "asha@example.com")
    assert err.value.status_code == 409


def test_public_reference_view_has_no_contact_details(db):
    inquiry = make_inquiry(db)
    app = FastAPI()
    app.include_router(booking_inquiries.router, prefix="/booking-inquiries")
    app.dependency_overrides[get_db] = lambda: db
    response = TestClient(app).get(f"/booking-inquiries/reference/{inquiry.reference}")
    assert response.status_code == 200
    body = response.json()
    assert body["reference"] == inquiry.reference
    assert body["total"] == 224.0 and body["taxes"] == 24.0
    assert body["paymentMethod"] == "bank_transfer"
    text = response.text.lower()
    assert "asha@example.com" not in text and "0771234567" not in text
    assert TestClient(app).get("/booking-inquiries/reference/NOPE").status_code == 404


# ---- FLOW-4: quote request ----

def test_quote_request_has_no_price_and_no_payment(db):
    created = BookingInquiryService(db).create_quote_request(QuoteRequestCreate(
        firstName="Asha", lastName="Perera", email="asha@example.com", phone="0771234567",
        numberOfTravelers=4, listingId="package-9", listingTitle="Hill country 7 days",
        message="Vegetarian meals please",
    ))
    inquiry = db.get(BookingInquiry, created.id)
    assert inquiry.reference.startswith("QUO-")
    assert inquiry.total == Decimal("0") and inquiry.payment_method is None
    assert inquiry.status == InquiryStatus.PENDING_CONTACT
    assert "[Custom quote request]" in inquiry.special_requests
