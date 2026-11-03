"""FEAT-2 (assignments) and FEAT-3 (add-ons, review moderation, customer notifications)."""
import os
from decimal import Decimal
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID as PGUUID
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

os.environ.setdefault("DATABASE_URL", "sqlite+pysqlite:///:memory:")

from app.api import deps
from app.api.v1 import includes, vendor_booking_inquiries
from app.api.v1.admin import addons, assignments, notifications, reviews, settings as admin_settings
from app.config.database import get_db
from app.models.base import Base
from app.models.bookingInquiry import BookingInquiry
from app.models.driver import Driver
from app.models.enum import CurrencyCode, InquiryStatus, ListingStatus, ListingType, ReviewStatus, UserRole
from app.models.listing import Listing
from app.models.notification import ClientNotification, NotificationType
from app.models.review import Review
from app.models.user import User


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
    "users", "listings", "booking_inquiries", "drivers", "inquiry_assignments",
    "listing_addons", "reviews", "client_notifications", "bookings",
    "driver_luggage_capacity", "luggage_size_types", "vehicle_model_presets",
    "stay_properties", "AdminSettings", "payments", "payment_events",
)


@pytest.fixture
def db():
    engine = create_engine("sqlite+pysqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    import app.models  # noqa: F401

    Base.metadata.create_all(engine, tables=[Base.metadata.tables[n] for n in TABLES])
    session = sessionmaker(autocommit=False, autoflush=False, bind=engine)()
    yield session
    session.close()


@pytest.fixture
def admin(db):
    user = User(email="admin@example.com", full_name="Admin", role=UserRole.ADMIN)
    db.add(user)
    db.commit()
    return user


def make_client(db, user):
    app = FastAPI()
    app.include_router(addons.router, prefix="/admin")
    app.include_router(assignments.router, prefix="/admin")
    app.include_router(reviews.router, prefix="/admin")
    app.include_router(notifications.router, prefix="/admin")
    app.include_router(includes.router, prefix="/listing-addons")
    app.include_router(vendor_booking_inquiries.router, prefix="/vendor/booking-inquiries")
    app.include_router(admin_settings.router, prefix="/admin")
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[deps.get_current_user] = lambda: user
    return TestClient(app)


def make_listing(db):
    listing = Listing(destination_id=uuid4(), listing_type=ListingType.TOUR, title="Ella tour",
                      status=ListingStatus.PUBLISHED, base_currency=CurrencyCode.USD)
    db.add(listing)
    db.commit()
    return listing


def make_inquiry(db, status=InquiryStatus.QUOTED, listing_id="tour-1"):
    inquiry = BookingInquiry(
        reference=f"TUR-{uuid4().hex[:8].upper()}", first_name="A", last_name="B", email="a@example.com", phone="1",
        nationality="LK", number_of_travelers=2, subtotal=100, total=112, currency=CurrencyCode.USD, status=status,
        cart_items=[{"listing_id": listing_id, "title": "Ella tour", "travel_date": "2027-03-01T00:00:00", "price": 50, "travel_count": 2}],
    )
    db.add(inquiry)
    db.commit()
    return inquiry


def make_driver(db, status="approved"):
    user = User(email=f"{uuid4().hex[:6]}@example.com", full_name="Kamal Driver", role=UserRole.DRIVER,
                business_profile={"phone": "0771111111"})
    db.add(user)
    db.flush()
    driver = Driver(user_id=user.id, nic_number=uuid4().hex[:10], vehicle_make="Toyota", vehicle_model="Hiace",
                    vehicle_plate_number=uuid4().hex[:7].upper(), seats=9, status=status)
    db.add(driver)
    db.commit()
    return driver


# ---- FEAT-3: add-ons ----

def test_addon_lifecycle_and_public_list(db, admin):
    client = make_client(db, admin)
    listing = make_listing(db)
    created = client.post("/admin/addons", json={"listing_id": str(listing.id), "name": "Airport pickup", "price": 25, "base_currency": "usd"})
    assert created.status_code == 201
    addon = created.json()
    assert addon["base_currency"] == "USD" and addon["price"] == 25.0

    assert [a["name"] for a in client.get(f"/listing-addons/listing/{listing.id}").json()] == ["Airport pickup"]

    assert client.patch(f"/admin/addons/{addon['id']}", json={"is_active": False}).status_code == 200
    assert client.get(f"/listing-addons/listing/{listing.id}").json() == []          # hidden once inactive
    assert len(client.get(f"/admin/addons?listing_id={listing.id}").json()) == 1      # still listed for admins

    assert client.delete(f"/admin/addons/{addon['id']}").status_code == 204
    assert client.get(f"/admin/addons?listing_id={listing.id}").json() == []


def test_addon_validation(db, admin):
    client = make_client(db, admin)
    assert client.post("/admin/addons", json={"listing_id": str(uuid4()), "name": "X", "price": 5}).status_code == 404
    listing = make_listing(db)
    assert client.post("/admin/addons", json={"listing_id": str(listing.id), "name": "X", "price": -1}).status_code == 422


# ---- FEAT-3: review moderation ----

def test_review_moderation(db, admin):
    client = make_client(db, admin)
    listing = make_listing(db)
    review = Review(booking_id=uuid4(), user_id=admin.id, listing_id=listing.id, rating=5, title="Great", status=ReviewStatus.PENDING)
    db.add(review)
    db.commit()

    assert client.get("/admin/reviews?status=pending").json()["total"] == 1
    assert client.get("/admin/reviews?status=published").json()["total"] == 0
    changed = client.patch(f"/admin/reviews/{review.id}/status", json={"status": "published"})
    assert changed.status_code == 200 and changed.json()["status"] == "published"
    assert client.get("/admin/reviews?status=published").json()["items"][0]["listing_title"] == "Ella tour"
    assert client.patch(f"/admin/reviews/{uuid4()}/status", json={"status": "hidden"}).status_code == 404
    assert client.patch(f"/admin/reviews/{review.id}/status", json={"status": "nonsense"}).status_code == 422


# ---- FEAT-3: customer notifications ----

def test_notification_list_filters(db, admin):
    client = make_client(db, admin)
    for kind, read in ((NotificationType.BOOKING_QUOTED, False), (NotificationType.BOOKING_CANCELLED, True)):
        db.add(ClientNotification(recipient_email="a@example.com", type=kind, title="t", message="m", reference="INQ-1", is_read=read, payload={}))
    db.commit()
    assert client.get("/admin/notifications").json()["total"] == 2
    assert client.get("/admin/notifications?type=booking_cancelled").json()["total"] == 1
    assert client.get("/admin/notifications?unread_only=true").json()["items"][0]["type"] == "booking_quoted"


# ---- FEAT-2: assignments ----

def url(inquiry):
    return f"/admin/inquiries/{inquiry.id}/assignments"


def test_cannot_assign_before_approval(db, admin):
    client = make_client(db, admin)
    pending = make_inquiry(db, status=InquiryStatus.PENDING_CONTACT)
    response = client.post(url(pending), json={"assignee_type": "guide", "guide_name": "Nimal"})
    assert response.status_code == 409 and "Approve the request first" in response.json()["detail"]


def test_assign_guide_and_driver_then_unassign(db, admin):
    client = make_client(db, admin)
    inquiry = make_inquiry(db)
    driver = make_driver(db)

    guide = client.post(url(inquiry), json={"assignee_type": "guide", "guide_name": " Nimal ", "guide_phone": "0772222222"})
    assert guide.status_code == 201 and guide.json()["guide_name"] == "Nimal"

    assigned = client.post(url(inquiry), json={"assignee_type": "driver", "driver_id": str(driver.id)})
    assert assigned.status_code == 201
    assert assigned.json()["driver"]["full_name"] == "Kamal Driver" and assigned.json()["driver"]["phone"] == "0771111111"

    assert client.post(url(inquiry), json={"assignee_type": "driver", "driver_id": str(driver.id)}).status_code == 409   # duplicate

    assert client.delete(f"{url(inquiry)}/{guide.json()['id']}").status_code == 204
    statuses = {a["id"]: a["status"] for a in client.get(url(inquiry)).json()}
    assert statuses[guide.json()["id"]] == "cancelled" and statuses[assigned.json()["id"]] == "assigned"

    # a cancelled assignment frees the driver to be assigned again
    client.delete(f"{url(inquiry)}/{assigned.json()['id']}")
    assert client.post(url(inquiry), json={"assignee_type": "driver", "driver_id": str(driver.id)}).status_code == 201


def test_assignment_rules(db, admin):
    client = make_client(db, admin)
    inquiry = make_inquiry(db)
    assert client.post(url(inquiry), json={"assignee_type": "driver", "driver_id": str(make_driver(db, status="pending_review").id)}).status_code == 409
    assert client.post(url(inquiry), json={"assignee_type": "driver", "driver_id": str(uuid4())}).status_code == 404
    assert client.post(url(inquiry), json={"assignee_type": "guide"}).status_code == 422
    assert client.post(url(inquiry), json={"assignee_type": "driver"}).status_code == 422
    assert client.post(url(make_inquiry(db, listing_id="transfer-sedan")), json={"assignee_type": "guide", "guide_name": "X"}).status_code == 409
    assert client.get(f"/admin/inquiries/{uuid4()}/assignments").status_code == 404
    assert client.delete(f"{url(inquiry)}/{uuid4()}").status_code == 404


# ---- ERR-3: a driver decision is mirrored on the user so the pending screen can clear ----

def test_driver_approval_updates_user_status(db):
    from app.repositories.driver_repository import DriverRepository

    driver = make_driver(db, status="pending_review")
    driver.user.vendor_status = "pending"
    db.commit()
    repo = DriverRepository(db)

    repo.update_driver_status(driver.id, "approved")
    db.refresh(driver.user)
    assert driver.user.vendor_status == "approved"

    repo.update_driver_status(driver.id, "suspended")
    db.refresh(driver.user)
    assert driver.user.vendor_status == "suspended"


# ---- UI-11: internal notes live on the server, staff only ----

def test_internal_notes_roundtrip_and_permissions(db, admin):
    inquiry = make_inquiry(db)
    client = make_client(db, admin)
    path = f"/vendor/booking-inquiries/{inquiry.id}/internal-notes"

    assert client.get(path).json()["notes"] == ""
    saved = client.put(path, json={"notes": "  Called the guest, wants a vegetarian menu  "})
    assert saved.status_code == 200 and saved.json()["notes"] == "Called the guest, wants a vegetarian menu"
    assert client.get(path).json()["notes"] == "Called the guest, wants a vegetarian menu"
    assert client.put(path, json={"notes": "   "}).json()["notes"] == ""          # blank clears it
    assert client.put(path, json={"notes": "x" * 5001}).status_code == 422
    assert client.get(f"/vendor/booking-inquiries/{uuid4()}/internal-notes").status_code == 404

    stranger = User(email="v@example.com", full_name="Other vendor", role=UserRole.VENDOR)
    db.add(stranger)
    db.commit()
    assert make_client(db, stranger).get(path).status_code == 403                 # a vendor who does not own it


def test_notes_never_reach_the_customer_views(db, admin):
    from app.services.booking_inquiry_service import BookingInquiryService

    inquiry = make_inquiry(db)
    inquiry.internal_notes = "SECRET staff note"
    db.commit()
    service = BookingInquiryService(db)
    assert "SECRET" not in service.get_public_view(inquiry.reference).model_dump_json()
    assert "SECRET" not in service.get_inquiry_by_id(inquiry.id).model_dump_json()


# ---- UI-11: the platform fee comes from settings ----

def test_platform_fee_setting(db, admin):
    client = make_client(db, admin)
    assert client.get("/admin/settings").json()["platformFeePercent"] == 15.0      # the old hardcoded figure is the default
    updated = client.patch("/admin/settings", json={"siteName": "TRT", "contactEmail": "a@b.com", "defaultCurrency": "USD", "platformFeePercent": 12.5})
    assert updated.status_code == 200 and updated.json()["platformFeePercent"] == 12.5
    # omitting the fee leaves it alone
    kept = client.patch("/admin/settings", json={"siteName": "TRT2", "contactEmail": "a@b.com", "defaultCurrency": "USD"})
    assert kept.json()["platformFeePercent"] == 12.5
    assert client.patch("/admin/settings", json={"siteName": "x", "contactEmail": "a@b.com", "defaultCurrency": "USD", "platformFeePercent": 140}).status_code == 422


# ---- FEAT-4: the real payments list and per-currency totals ----

def test_payment_summary_never_mixes_currencies(db, admin):
    from app.api.v1.admin import payments as admin_payments
    from app.payments.models import Payment

    for i, (amount, currency, status) in enumerate((("100.00", "USD", "succeeded"), ("50.50", "USD", "succeeded"),
                                                    ("9000", "LKR", "succeeded"), ("70", "USD", "failed"))):
        db.add(Payment(target_type="booking_inquiry", target_id=uuid4(), provider="payhere", order_id=f"ORD-{i}",
                       amount=Decimal(amount), currency=currency, status=status))
    db.commit()

    app = FastAPI()
    app.include_router(admin_payments.router, prefix="/admin")
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[deps.get_current_user] = lambda: admin
    client = TestClient(app)

    received = {r["currency"]: (float(r["total"]), r["count"]) for r in client.get("/admin/payments/summary").json()["received"]}
    assert received == {"LKR": (9000.0, 1), "USD": (150.5, 2)}          # failed payment excluded, currencies kept apart
    assert client.get("/admin/payments?status=failed").json()["total"] == 1
