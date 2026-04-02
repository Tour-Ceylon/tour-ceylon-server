import os
from datetime import date, datetime, time
from decimal import Decimal
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

os.environ.setdefault("DATABASE_URL", "sqlite+pysqlite:///:memory:")

from app.api.v1 import bookings as booking_routes
from app.api.v1 import listing as listing_routes
from app.config.database import get_db
from app.models.base import Base
from app.models.destination import Destination
from app.models.enum import (
    BookingUnit,
    CurrencyCode,
    DestinationType,
    ListingStatus,
    ListingType,
    PaymentTransactionStatus,
    PropertyType,
    UserRole,
)
from app.models.listing import Listing
from app.models.listingVariant import ListingVariant
from app.models.user import User


@pytest.fixture
def db_session():
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture
def client(db_session):
    app = FastAPI()
    app.include_router(listing_routes.router, prefix="/listings", tags=["listings"])
    app.include_router(booking_routes.router, prefix="/bookings", tags=["bookings"])

    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    return TestClient(app)


@pytest.fixture
def booking_seed(db_session):
    destination = Destination(
        name="Colombo",
        destination_type=DestinationType.CITY,
        latitude=6.9271,
        longitude=79.8612,
    )
    db_session.add(destination)
    db_session.flush()

    listing = Listing(
        destination_id=destination.id,
        listing_type=ListingType.HOTEL,
        title="City Stay",
        slug="city-stay",
        description="Central hotel",
        status=ListingStatus.PUBLISHED,
        base_currency=CurrencyCode.LKR,
        is_active=True,
    )
    db_session.add(listing)
    db_session.flush()

    variant = ListingVariant(
        listing_id=listing.id,
        name=f"Deluxe-{uuid4()}",
        booking_unit=BookingUnit.PER_ROOM,
        capacity_min=1,
        capacity_max=2,
        is_default=True,
        is_active=True,
    )
    user = User(
        email="traveler@example.com",
        full_name="Traveler",
        country="Sri Lanka",
        role=UserRole.TOURIST,
        is_active=True,
    )
    db_session.add_all([variant, user])
    db_session.commit()

    return {
        "destination": destination,
        "listing": listing,
        "variant": variant,
        "user": user,
    }


def test_create_listing_returns_nested_hotel_detail(client, db_session):
    destination = Destination(
        name="Kandy",
        destination_type=DestinationType.CITY,
        latitude=7.2906,
        longitude=80.6337,
    )
    db_session.add(destination)
    db_session.commit()

    response = client.post(
        "/listings/",
        json={
            "listing_type": "hotel",
            "destination_id": str(destination.id),
            "title": "Hill Retreat",
            "description": "A mountain stay",
            "status": "published",
            "base_currency": "LKR",
            "is_active": True,
            "hotel_detail": {
                "property_type": "hotel",
                "star_rating": 5,
                "check_in_time": "14:00:00",
                "check_out_time": "11:00:00",
                "child_policy": "Children welcome",
            },
        },
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["listing_type"] == "hotel"
    assert payload["hotel_detail"]["star_rating"] == 5
    assert payload["destination"]["name"] == "Kandy"


def test_active_listings_endpoint_is_not_captured_by_id_route(client, db_session):
    destination = Destination(
        name="Ella",
        destination_type=DestinationType.CITY,
        latitude=6.8667,
        longitude=81.0466,
    )
    db_session.add(destination)
    db_session.flush()

    active_listing = Listing(
        destination_id=destination.id,
        listing_type=ListingType.HOTEL,
        title="Active Stay",
        slug=f"active-stay-{uuid4()}",
        description="Visible listing",
        status=ListingStatus.PUBLISHED,
        base_currency=CurrencyCode.LKR,
        is_active=True,
    )
    inactive_listing = Listing(
        destination_id=destination.id,
        listing_type=ListingType.HOTEL,
        title="Inactive Stay",
        slug=f"inactive-stay-{uuid4()}",
        description="Hidden listing",
        status=ListingStatus.DRAFT,
        base_currency=CurrencyCode.LKR,
        is_active=False,
    )
    db_session.add_all([active_listing, inactive_listing])
    db_session.commit()

    response = client.get("/listings/active")

    assert response.status_code == 200
    payload = response.json()
    assert len(payload) == 1
    assert payload[0]["title"] == "Active Stay"


def test_create_booking_returns_nested_items_and_travelers(client, booking_seed):
    response = client.post(
        "/bookings/",
        json={
            "booking_reference": "BK-1001",
            "user_id": str(booking_seed["user"].id),
            "status": "pending",
            "total_amount": "350.00",
            "currency": "LKR",
            "payment_status": "pending",
            "booked_at": "2026-04-02T10:30:00",
            "booking_items": [
                {
                    "listing_id": str(booking_seed["listing"].id),
                    "variant_id": str(booking_seed["variant"].id),
                    "travel_date": "2026-04-15",
                    "quantity": 2,
                    "unit_price": 175.0,
                    "total_price": 350.0,
                    "travelers": [
                        {
                            "first_name": "Asha",
                            "last_name": "Perera",
                            "age": 32,
                            "nationality": "Sri Lankan",
                            "passport_no": "N1234567",
                        }
                    ],
                }
            ],
        },
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["booking_reference"] == "BK-1001"
    assert payload["booking_items"][0]["listing_id"] == str(booking_seed["listing"].id)
    assert payload["booking_items"][0]["travelers"][0]["first_name"] == "Asha"


def test_booking_stats_uses_model_first_aggregate_field_names(client, booking_seed):
    create_response = client.post(
        "/bookings/",
        json={
            "booking_reference": "BK-1002",
            "user_id": str(booking_seed["user"].id),
            "status": "confirmed",
            "total_amount": "500.00",
            "currency": "LKR",
            "payment_status": "succeeded",
            "booked_at": "2026-04-04T10:30:00",
            "booking_items": [
                {
                    "listing_id": str(booking_seed["listing"].id),
                    "variant_id": str(booking_seed["variant"].id),
                    "travel_date": "2026-04-20",
                    "quantity": 1,
                    "unit_price": 500.0,
                    "total_price": 500.0,
                    "travelers": [],
                }
            ],
        },
    )
    assert create_response.status_code == 201

    summary_response = client.get("/bookings/stats/summary")
    revenue_response = client.get("/bookings/stats/revenue")

    assert summary_response.status_code == 200
    assert revenue_response.status_code == 200
    assert "pending" in summary_response.json()
    assert "total_revenue" in summary_response.json()
    assert "total_revenue" in revenue_response.json()
    assert "total_revenue_minor" not in revenue_response.json()
