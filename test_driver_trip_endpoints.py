from datetime import date, datetime, time, timezone
from decimal import Decimal
from uuid import uuid4
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.deps import get_current_user
from app.api.v1 import driver_trips
from app.api.v1.driver_trips import get_driver_trip_service
from app.config.database import get_db
from app.models.driver import Driver
from app.models.enum import AssignmentStatus, DriverStatus, UserRole
from app.models.transportBooking import TransportBooking
from app.models.vehicleCategory import VehicleCategory
from app.models.user import User
from app.services.driver_trip_service import DriverTripService


class StubDriverTripRepo:
    def __init__(self, driver, trips=None):
        self.driver = driver
        self.trips = trips or []
        self.declines = []

    def get_driver_by_user_id(self, user_id):
        if self.driver and self.driver.user_id == user_id:
            return self.driver
        return None

    def update_driver_availability(self, driver, is_online):
        driver.is_online = is_online
        if is_online:
            driver.last_online_at = datetime.now(timezone.utc)
        return driver

    def get_driver_trips(self, driver_id, status_bucket):
        if status_bucket == "assigned":
            return [t for t in self.trips if t.driver_id == driver_id and t.assignment_status == "assigned"]
        elif status_bucket == "upcoming":
            return [t for t in self.trips if t.driver_id == driver_id and t.assignment_status in ("acknowledged", "en_route", "arrived", "in_progress")]
        elif status_bucket == "history":
            return [t for t in self.trips if t.driver_id == driver_id and t.assignment_status == "completed"]
        return [t for t in self.trips if t.driver_id == driver_id]

    def get_driver_trip_by_id(self, driver_id, booking_id):
        for t in self.trips:
            if t.id == booking_id and t.driver_id == driver_id:
                return t
        return None

    def update_assignment_status(self, booking, new_status, responded_at=None):
        booking.assignment_status = new_status
        if responded_at:
            booking.driver_responded_at = responded_at
        if new_status == "completed":
            booking.booking_status = "completed"
        return booking

    def record_decline_and_unassign(self, booking, driver_id, reason, note=None):
        decline_stub = type("Decline", (), {
            "id": uuid4(),
            "transport_booking_id": booking.id,
            "driver_id": driver_id,
            "reason": reason,
            "note": note,
            "created_at": datetime.now(timezone.utc),
        })()
        self.declines.append(decline_stub)
        booking.driver_id = None
        booking.assignment_status = "unassigned"
        booking.driver_responded_at = datetime.now(timezone.utc)
        return decline_stub

    def get_completed_trips_in_date_range(self, driver_id, start_date=None, end_date=None):
        return [
            t for t in self.trips
            if t.driver_id == driver_id
            and t.assignment_status == "completed"
            and (start_date is None or start_date <= t.travel_date)
            and (end_date is None or t.travel_date <= end_date)
        ]


def create_test_driver_user():
    user_id = uuid4()
    driver_id = uuid4()
    user = User(
        id=user_id,
        email="driver@tourceylon.com",
        full_name="Sunil Perera",
        role=UserRole.DRIVER,
        is_active=True,
    )
    driver = Driver(
        id=driver_id,
        user_id=user_id,
        nic_number="198512345678",
        vehicle_make="Toyota",
        vehicle_model="Prius",
        vehicle_plate_number="WP-CAB-1234",
        seats=4,
        status=DriverStatus.APPROVED.value,
        is_online=False,
        last_online_at=None,
        is_active=True,
    )
    return user, driver


def create_test_booking(driver_id, assignment_status="assigned"):
    booking_id = uuid4()
    cat = VehicleCategory(
        id=uuid4(),
        name="Sedan",
        slug="sedan",
        passenger_capacity=4,
        luggage_capacity=2,
        base_fare=Decimal("20.00"),
        price_per_km=Decimal("0.50"),
        minimum_fare=Decimal("15.00"),
        airport_surcharge=Decimal("5.00"),
        night_surcharge=Decimal("0.00"),
        currency="USD",
        is_active=True,
    )
    booking = TransportBooking(
        id=booking_id,
        booking_reference="TB-20260828-001",
        vehicle_category_id=cat.id,
        customer_name="John Doe",
        customer_email="john@example.com",
        customer_phone="+94771234567",
        customer_country="UK",
        pickup_location="Bandaranaike International Airport",
        pickup_lat=Decimal("7.1808"),
        pickup_lng=Decimal("79.8841"),
        destination_location="Galle Fort Hotel",
        destination_lat=Decimal("6.0329"),
        destination_lng=Decimal("80.2168"),
        distance_km=Decimal("128.5"),
        estimated_duration_minutes=150,
        travel_date=date.today(),
        pickup_time=time(14, 30),
        passengers_count=2,
        luggage_count=2,
        special_requests="Bottled water please",
        base_fare=Decimal("20.00"),
        price_per_km=Decimal("0.50"),
        route_price=Decimal("64.25"),
        extra_charges=Decimal("0.00"),
        total_price=Decimal("84.25"),
        currency="USD",
        booking_status="confirmed",
        payment_status="paid",
        driver_id=driver_id,
        assignment_status=assignment_status,
        assigned_at=datetime.now(timezone.utc),
        created_at=datetime.now(timezone.utc),
    )
    booking.vehicle_category = cat
    return booking


@pytest.fixture
def test_setup():
    user, driver = create_test_driver_user()
    booking = create_test_booking(driver.id, assignment_status="assigned")
    repo = StubDriverTripRepo(driver, trips=[booking])

    app = FastAPI()
    app.include_router(driver_trips.router)

    app.dependency_overrides[get_current_user] = lambda: user

    def override_service():
        svc = DriverTripService(db=None)
        svc.repo = repo
        return svc

    app.dependency_overrides[get_driver_trip_service] = override_service

    client = TestClient(app)
    return client, user, driver, booking, repo


def test_get_and_patch_availability(test_setup):
    client, user, driver, booking, repo = test_setup

    res = client.get("/drivers/me/availability")
    assert res.status_code == 200
    assert res.json()["is_online"] is False

    res = client.patch("/drivers/me/availability", json={"is_online": True})
    assert res.status_code == 200
    assert res.json()["is_online"] is True
    assert res.json()["last_online_at"] is not None


def test_list_trips_inbox(test_setup):
    client, user, driver, booking, repo = test_setup

    res = client.get("/drivers/me/trips?status=assigned")
    assert res.status_code == 200
    data = res.json()
    assert len(data) == 1
    assert data[0]["id"] == str(booking.id)
    assert data[0]["customer_name"] == "John Doe"
    assert data[0]["assignment_status"] == "assigned"


def test_trip_detail(test_setup):
    client, user, driver, booking, repo = test_setup

    res = client.get(f"/drivers/me/trips/{booking.id}")
    assert res.status_code == 200
    data = res.json()
    assert data["customer"]["name"] == "John Doe"
    assert data["pickup_location"] == "Bandaranaike International Airport"
    assert float(data["total_price"]) == 84.25


def test_acknowledge_and_status_progression(test_setup):
    client, user, driver, booking, repo = test_setup

    # 1. Acknowledge
    res = client.post(f"/drivers/me/trips/{booking.id}/acknowledge")
    assert res.status_code == 200
    assert res.json()["assignment_status"] == "acknowledged"

    # 2. Invalid jump (e.g. acknowledged -> completed) should fail with 400
    res = client.patch(f"/drivers/me/trips/{booking.id}/status", json={"status": "completed"})
    assert res.status_code == 400

    # 3. Step: acknowledged -> en_route
    res = client.patch(f"/drivers/me/trips/{booking.id}/status", json={"status": "en_route"})
    assert res.status_code == 200
    assert res.json()["assignment_status"] == "en_route"

    # 4. Step: en_route -> arrived
    res = client.patch(f"/drivers/me/trips/{booking.id}/status", json={"status": "arrived"})
    assert res.status_code == 200
    assert res.json()["assignment_status"] == "arrived"

    # 5. Step: arrived -> in_progress
    res = client.patch(f"/drivers/me/trips/{booking.id}/status", json={"status": "in_progress"})
    assert res.status_code == 200
    assert res.json()["assignment_status"] == "in_progress"

    # 6. Step: in_progress -> completed
    res = client.patch(f"/drivers/me/trips/{booking.id}/status", json={"status": "completed"})
    assert res.status_code == 200
    assert res.json()["assignment_status"] == "completed"

    # 7. Check Earnings
    res = client.get("/drivers/me/earnings?period=today")
    assert res.status_code == 200
    earnings_data = res.json()
    assert float(earnings_data["total_earnings"]) == 84.25
    assert earnings_data["trip_count"] == 1


def test_decline_assigned_trip(test_setup):
    client, user, driver, booking, repo = test_setup

    res = client.post(
        f"/drivers/me/trips/{booking.id}/decline",
        json={"reason": "Vehicle mechanical issue", "note": "Flat tyre"},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["reason"] == "Vehicle mechanical issue"
    assert booking.driver_id is None
    assert booking.assignment_status == "unassigned"


def test_cannot_decline_after_acknowledging(test_setup):
    client, user, driver, booking, repo = test_setup

    client.post(f"/drivers/me/trips/{booking.id}/acknowledge")
    res = client.post(
        f"/drivers/me/trips/{booking.id}/decline",
        json={"reason": "Changed mind"},
    )
    assert res.status_code == 400


# --- Admin Assign Tests ---

def test_admin_list_and_assign_driver():
    admin_user = User(
        id=uuid4(),
        email="admin@tourceylon.com",
        full_name="Admin User",
        role=UserRole.ADMIN,
        is_active=True,
    )
    user, driver = create_test_driver_user()
    driver.user = user
    booking = create_test_booking(driver_id=None, assignment_status="unassigned")
    booking.driver = None

    class MockSession:
        def __init__(self):
            self.bookings = [booking]
            self.drivers = [driver]

        def query(self, model):
            sess = self
            class QueryMock:
                def __init__(self, target_model):
                    self.target = target_model
                    self._filters = []

                def options(self, *args):
                    return self

                def filter(self, *args):
                    return self

                def order_by(self, *args):
                    return self

                def offset(self, n):
                    return self

                def limit(self, n):
                    return self

                def count(self):
                    if self.target == TransportBooking:
                        return len(sess.bookings)
                    return len(sess.drivers)

                def all(self):
                    if self.target == TransportBooking:
                        return sess.bookings
                    return sess.drivers

                def first(self):
                    if self.target == TransportBooking:
                        return sess.bookings[0] if sess.bookings else None
                    return sess.drivers[0] if sess.drivers else None

                def scalar(self):
                    return 1

            return QueryMock(model)

        def commit(self):
            pass

        def refresh(self, obj):
            pass

    from app.api.v1.admin import transport_bookings

    app = FastAPI()
    app.include_router(transport_bookings.router)

    app.dependency_overrides[get_current_user] = lambda: admin_user
    app.dependency_overrides[get_db] = lambda: MockSession()

    client = TestClient(app)

    # 1. Admin list transport bookings
    res = client.get("/transport-bookings?assignment_status=unassigned")
    assert res.status_code == 200
    data = res.json()
    assert data["total"] == 1
    assert data["bookings"][0]["assignment_status"] == "unassigned"

    # 2. Admin assign driver
    res = client.patch(f"/transport-bookings/{booking.id}/assign", json={"driver_id": str(driver.id)})
    assert res.status_code == 200
    assigned_data = res.json()
    assert assigned_data["assignment_status"] == "assigned"
    assert assigned_data["driver"]["id"] == str(driver.id)
    assert assigned_data["driver"]["full_name"] == "Sunil Perera"
