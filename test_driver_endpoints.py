from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import uuid4
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.deps import get_current_user
from app.api.v1 import auth, drivers
from app.api.v1.admin import drivers as admin_drivers
from app.config.database import get_db
from app.models.enum import DriverStatus, UserRole
from app.models.user import User
from app.schemas.driver_schema import (
    DriverListResponse,
    DriverLuggageCapacityResponseItem,
    DriverProfileUpdate,
    DriverResponse,
    DriverSignupRequest,
    LuggageSizeTypeResponse,
    VehicleModelPresetResponse,
)
from app.services.driver_service import DriverService


class StubDriverService:
    def __init__(self):
        self.drivers_db = {}
        self.presets = [
            VehicleModelPresetResponse(
                id=uuid4(),
                make="Toyota",
                model="Prius",
                vehicle_category_id=None,
                default_seats=4,
                default_luggage_capacity={"Small": 2, "Medium": 2, "Large": 1, "Extra Large": 0},
                is_active=True,
            )
        ]
        self.luggage_types = [
            LuggageSizeTypeResponse(
                id=uuid4(),
                name="Small",
                dimensions_display="55 x 35 x 20 cm",
                description="Cabin bag",
                sort_order=1,
            ),
            LuggageSizeTypeResponse(
                id=uuid4(),
                name="Medium",
                dimensions_display="65 x 45 x 25 cm",
                description="Medium suitcase",
                sort_order=2,
            ),
            LuggageSizeTypeResponse(
                id=uuid4(),
                name="Large",
                dimensions_display="75 x 50 x 30 cm",
                description="Large suitcase",
                sort_order=3,
            ),
            LuggageSizeTypeResponse(
                id=uuid4(),
                name="Extra Large",
                dimensions_display="85 x 60 x 35 cm",
                description="Oversized",
                sort_order=4,
            ),
        ]

    def get_luggage_size_types(self):
        return self.luggage_types

    def get_vehicle_model_presets(self):
        return self.presets

    def signup_driver(self, data: DriverSignupRequest):
        driver_id = uuid4()
        user_id = uuid4()
        resp = DriverResponse(
            id=driver_id,
            user_id=user_id,
            full_name=data.full_name,
            email=data.email,
            phone=data.phone,
            nic_number=data.nic_number,
            license_number=data.license_number,
            license_photo_url=data.license_photo_url,
            nic_photo_url=data.nic_photo_url,
            vehicle_registration_doc_url=data.vehicle_registration_doc_url,
            insurance_doc_url=data.insurance_doc_url,
            police_clearance_doc_url=data.police_clearance_doc_url,
            vehicle_model_preset_id=data.vehicle_model_preset_id,
            vehicle_make=data.vehicle_make,
            vehicle_model=data.vehicle_model,
            vehicle_plate_number=data.vehicle_plate_number,
            seats=data.seats,
            status="pending_review",
            is_active=True,
            luggage_capacities=[
                DriverLuggageCapacityResponseItem(
                    luggage_size_type_id=item.luggage_size_type_id,
                    name="Tier",
                    quantity=item.quantity,
                )
                for item in data.luggage_capacities
            ],
        )
        self.drivers_db[driver_id] = resp
        return resp

    def get_driver_by_user_id(self, user_id):
        for d in self.drivers_db.values():
            if d.user_id == user_id:
                return d
        # Return a mock driver
        return DriverResponse(
            id=uuid4(),
            user_id=user_id,
            full_name="Test Driver",
            email="driver@example.com",
            nic_number="199012345678",
            vehicle_make="Toyota",
            vehicle_model="Prius",
            vehicle_plate_number="WP CAB-1234",
            seats=4,
            status="pending_review",
            is_active=True,
        )

    def get_driver_by_id(self, driver_id):
        if driver_id in self.drivers_db:
            return self.drivers_db[driver_id]
        return DriverResponse(
            id=driver_id,
            user_id=uuid4(),
            full_name="Test Driver",
            email="driver@example.com",
            nic_number="199012345678",
            vehicle_make="Toyota",
            vehicle_model="Prius",
            vehicle_plate_number="WP CAB-1234",
            seats=4,
            status="pending_review",
            is_active=True,
        )

    def update_driver_profile(self, user_id, data: DriverProfileUpdate):
        driver = self.get_driver_by_user_id(user_id)
        if data.base_location is not None:
            driver.base_location = data.base_location
        if data.years_experience is not None:
            driver.years_experience = data.years_experience
        if data.languages_spoken is not None:
            driver.languages_spoken = data.languages_spoken
        return driver

    def update_driver_status(self, driver_id, status):
        driver = self.get_driver_by_id(driver_id)
        driver.status = status
        return driver

    def list_drivers(self, status=None, search=None, page=1, per_page=20):
        items = list(self.drivers_db.values())
        if not items:
            items = [self.get_driver_by_id(uuid4())]
        return DriverListResponse(
            drivers=items,
            total=len(items),
            page=page,
            per_page=per_page,
            total_pages=1,
        )


@pytest.fixture
def stub_service():
    return StubDriverService()


@pytest.fixture
def client(stub_service):
    app = FastAPI()
    app.include_router(auth.router, prefix="/auth")
    app.include_router(drivers.router)
    app.include_router(admin_drivers.router, prefix="/admin")

    admin_user = User(
        clerk_user_id="clerk_admin_123",
        email="admin@tourceylon.com",
        full_name="Admin User",
        role=UserRole.ADMIN,
        is_active=True,
    )
    admin_user.id = uuid4()

    app.dependency_overrides[get_current_user] = lambda: admin_user
    app.dependency_overrides[drivers.get_driver_service] = lambda: stub_service
    app.dependency_overrides[admin_drivers.get_driver_service] = lambda: stub_service
    app.dependency_overrides[auth.get_db] = lambda: object()

    # Monkeypatch auth driver_service
    import app.api.v1.auth as auth_mod
    orig_service_cls = auth_mod.DriverService
    auth_mod.DriverService = lambda db: stub_service

    yield TestClient(app)

    auth_mod.DriverService = orig_service_cls


def test_get_luggage_size_types(client):
    res = client.get("/luggage-size-types")
    assert res.status_code == 200
    data = res.json()
    assert len(data) == 4
    assert data[0]["name"] == "Small"


def test_get_vehicle_model_presets(client):
    res = client.get("/vehicle-model-presets")
    assert res.status_code == 200
    data = res.json()
    assert len(data) == 1
    assert data[0]["make"] == "Toyota"
    assert data[0]["model"] == "Prius"


def test_driver_signup(client, stub_service):
    luggage_id = stub_service.luggage_types[0].id
    payload = {
        "full_name": "Kamal Perera",
        "nic_number": "198812345678",
        "email": "kamal@example.com",
        "phone": "+94771234567",
        "vehicle_make": "Toyota",
        "vehicle_model": "Prius",
        "vehicle_plate_number": "WP CAB-5678",
        "seats": 4,
        "luggage_capacities": [{"luggage_size_type_id": str(luggage_id), "quantity": 2}],
        "license_number": "B1234567",
        "license_photo_url": "https://example.com/license.jpg",
        "nic_photo_url": "https://example.com/nic.jpg",
        "vehicle_registration_doc_url": "https://example.com/reg.jpg",
        "insurance_doc_url": "https://example.com/ins.jpg",
        "police_clearance_doc_url": "https://example.com/pc.jpg",
    }
    res = client.post("/auth/driver/signup", json=payload)
    assert res.status_code == 201
    data = res.json()
    assert data["full_name"] == "Kamal Perera"
    assert data["status"] == "pending_review"
    assert data["vehicle_plate_number"] == "WP CAB-5678"
    assert len(data["luggage_capacities"]) == 1


def test_admin_list_drivers(client):
    res = client.get("/admin/drivers")
    assert res.status_code == 200
    data = res.json()
    assert "drivers" in data
    assert data["total"] >= 1


def test_admin_approve_and_reject_driver(client):
    driver_id = str(uuid4())
    res_approve = client.post(f"/admin/drivers/{driver_id}/approve")
    assert res_approve.status_code == 200
    assert res_approve.json()["status"] == "approved"

    res_reject = client.post(f"/admin/drivers/{driver_id}/reject")
    assert res_reject.status_code == 200
    assert res_reject.json()["status"] == "rejected"


def test_update_driver_me_profile(client):
    res = client.patch("/drivers/me", json={"base_location": "Colombo", "years_experience": 5})
    assert res.status_code == 200
    data = res.json()
    assert data["base_location"] == "Colombo"
    assert data["years_experience"] == 5
