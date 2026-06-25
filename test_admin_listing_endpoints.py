from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.deps import get_current_user
from app.api.v1.admin import listings, snapshot
from app.api.v1.admin.dependencies import get_admin_service
from app.api.errors import AdminAPIError
from app.models.enum import ListingType, UserRole
from app.services.admin.dashboard_service import AdminDashboardService


def _build_listing_payload(category: str) -> dict:
    return {
        "id": uuid4(),
        "category": category,
        "destination_id": uuid4(),
        "title": f"{category.title()} Listing",
        "is_active": True,
        "status": "draft",
        "variants": [],
    }


class StubAdminService:
    def __init__(self):
        self.categories_called = []

    def get_listings(self, category: str, current_user):
        self.categories_called.append((category, current_user.id))
        return [_build_listing_payload(category)]

    def get_snapshot(self, current_user):
        return {
            "packages": [],
            "addOns": [],
            "settings": {
                "siteName": "Tour Ceylon",
                "contactEmail": "admin@example.com",
                "defaultCurrency": "LKR",
            },
            "listings": {
                "stay": [],
                "tour": [],
                "experience": [],
                "safari": [],
                "transfer": [],
            },
        }


def _build_client(service: StubAdminService):
    app = FastAPI()
    app.include_router(listings.router, prefix="/admin")
    app.include_router(snapshot.router, prefix="/admin")

    test_user = SimpleNamespace(id=uuid4(), role=UserRole.ADMIN)
    app.dependency_overrides[get_admin_service] = lambda: service
    app.dependency_overrides[get_current_user] = lambda: test_user
    return TestClient(app), test_user


@pytest.mark.parametrize("category", ["stay", "tour", "experience", "safari", "transfer"])
def test_category_listing_routes_return_category_specific_payloads(category: str):
    service = StubAdminService()
    client, user = _build_client(service)

    response = client.get(f"/admin/listings/{category}")

    assert response.status_code == 200
    assert response.json()[0]["category"] == category
    assert response.json()[0]["destinationId"] is not None
    assert service.categories_called == [(category, user.id)]


def test_snapshot_route_remains_available_with_grouped_listing_shape():
    service = StubAdminService()
    client, _ = _build_client(service)

    response = client.get("/admin/snapshot")

    assert response.status_code == 200
    body = response.json()
    assert body["packages"] == []
    assert body["addOns"] == []
    assert body["listings"] == {
        "stay": [],
        "tour": [],
        "experience": [],
        "safari": [],
        "transfer": [],
    }


def test_get_listings_service_filters_by_category_and_builds_responses():
    captured = {}
    listing_record = object()
    current_user = SimpleNamespace(id=uuid4(), role=UserRole.VENDOR)

    class FakeListingsRepo:
        def get_listings_by_type(self, listing_type, user):
            captured["listing_type"] = listing_type
            captured["user"] = user
            return [listing_record]

    service = AdminDashboardService.__new__(AdminDashboardService)
    service.listings = FakeListingsRepo()
    service._build_listing_response = lambda listing: {"listing": listing}

    result = service.get_listings("stay", current_user)

    assert captured["listing_type"] == ListingType.HOTEL
    assert captured["user"] is current_user
    assert result == [{"listing": listing_record}]


def test_get_listings_service_rejects_invalid_category():
    service = AdminDashboardService.__new__(AdminDashboardService)

    with pytest.raises(AdminAPIError) as exc_info:
        service.get_listings("invalid", SimpleNamespace(id=uuid4(), role=UserRole.ADMIN))

    assert exc_info.value.status_code == 400
    assert "Unsupported listing category" in exc_info.value.message
