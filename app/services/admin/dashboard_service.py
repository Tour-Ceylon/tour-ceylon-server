from uuid import UUID, uuid4

from fastapi import status
from sqlalchemy.orm import Session

from app.api.errors import AdminAPIError
from app.models.enum import CurrencyType, ListingStatus, ListingType
from app.repositories.admin.addon_repo import AdminAddonRepository
from app.repositories.admin.listing_repo import AdminDashboardListingRepository
from app.repositories.admin.package_repo import AdminPackageRepository
from app.repositories.admin.settings_repo import AdminSettingsRepository


class AdminDashboardService:
    VALID_LISTING_CATEGORIES = {"stay", "tour", "activity", "transfer"}
    LISTING_TYPE_MAP = {
        "stay": ListingType.HOTEL,
        "tour": ListingType.TOUR,
        "activity": ListingType.GUIDE,
        "transfer": ListingType.VEHICLE,
    }

    def __init__(self, db: Session):
        self.db = db
        self.addons = AdminAddonRepository(db)
        self.packages = AdminPackageRepository(db)
        self.settings = AdminSettingsRepository(db)
        self.listings = AdminDashboardListingRepository(db)

    def get_snapshot(self) -> dict:
        listing_groups = {"stay": [], "tour": [], "activity": [], "transfer": []}
        for detail in self.listings.get_all_details():
            listing = self.listings.get_listing(detail.listing_id)
            if listing is None:
                continue
            listing_groups[detail.category].append(self._build_listing_response(listing, detail))

        return {
            "packages": [self._build_package_response(package) for package in self.packages.get_all()],
            "addOns": [self._build_addon_response(addon) for addon in self.addons.get_all()],
            "settings": self.get_settings(),
            "listings": listing_groups,
        }

    def create_package(self, payload: dict) -> dict:
        self._validate_addon_ids(payload.get("addOns", []))
        package = self.packages.create(self._package_model_data(payload))
        return self._build_package_response(package)

    def update_package(self, package_id: UUID, payload: dict) -> dict:
        package = self.packages.get(package_id)
        if package is None:
            raise self._not_found("Package not found")

        if "addOns" in payload and payload["addOns"] is not None:
            self._validate_addon_ids(payload["addOns"])

        updates = self._package_model_data(payload, partial=True)
        package = self.packages.update(package, updates)
        return self._build_package_response(package)

    def delete_package(self, package_id: UUID) -> None:
        if not self.packages.delete(package_id):
            raise self._not_found("Package not found")

    def toggle_package(self, package_id: UUID) -> dict:
        package = self.packages.get(package_id)
        if package is None:
            raise self._not_found("Package not found")

        package = self.packages.update(package, {"is_active": not package.is_active})
        return self._build_package_response(package)

    def create_addon(self, payload: dict) -> dict:
        addon = self.addons.create(**payload)
        return self._build_addon_response(addon)

    def delete_addon(self, addon_id: UUID) -> None:
        if not self.addons.delete(addon_id):
            raise self._not_found("Add-on not found")

    def create_listing(self, category: str, payload: dict) -> dict:
        category = self._validate_category(category)
        listing = self.listings.create_listing(self._listing_model_data(category, payload))
        self.listings.create_details(listing.id, category, self._listing_payload(category, payload))
        return self._build_listing_response(listing, self.listings.get_detail(listing.id))

    def update_listing(self, category: str, listing_id: UUID, payload: dict) -> dict:
        category = self._validate_category(category)
        detail = self.listings.get_detail_by_category(category, listing_id)
        listing = self.listings.get_listing(listing_id)
        if detail is None or listing is None:
            raise self._not_found("Listing not found")

        listing_updates = self._listing_model_data(category, payload, partial=True)
        if listing_updates:
            self.listings.update_listing(listing, listing_updates)

        merged_payload = dict(detail.payload)
        for key, value in payload.items():
            if value is not None:
                merged_payload[key] = value
        detail = self.listings.update_detail(detail, merged_payload)
        self.listings.commit()
        self.listings.refresh(listing)
        return self._build_listing_response(listing, detail)

    def delete_listing(self, category: str, listing_id: UUID) -> None:
        category = self._validate_category(category)
        detail = self.listings.get_detail_by_category(category, listing_id)
        if detail is None or not self.listings.delete_listing(listing_id):
            raise self._not_found("Listing not found")

    def get_settings(self) -> dict:
        settings = self.settings.get_or_create()
        return {
            "siteName": settings.site_name,
            "contactEmail": settings.contact_email,
            "defaultCurrency": settings.default_currency,
        }

    def update_settings(self, payload: dict) -> dict:
        settings = self.settings.get_or_create()
        updated = self.settings.update(
            settings,
            {
                "site_name": payload["siteName"],
                "contact_email": payload["contactEmail"],
                "default_currency": payload["defaultCurrency"],
            },
        )
        return {
            "siteName": updated.site_name,
            "contactEmail": updated.contact_email,
            "defaultCurrency": updated.default_currency,
        }

    def reset(self) -> dict:
        self.listings.delete_all()
        self.packages.delete_all()
        self.addons.delete_all()
        return self.get_snapshot()

    def _validate_addon_ids(self, addon_ids: list[str]) -> None:
        missing_ids = []
        for addon_id in addon_ids:
            try:
                parsed_id = UUID(addon_id)
            except ValueError:
                missing_ids.append(addon_id)
                continue

            if self.addons.get(parsed_id) is None:
                missing_ids.append(addon_id)

        if missing_ids:
            raise AdminAPIError(
                status_code=status.HTTP_400_BAD_REQUEST,
                message=f"Unknown add-on IDs: {', '.join(missing_ids)}",
            )

    def _validate_category(self, category: str) -> str:
        if category not in self.VALID_LISTING_CATEGORIES:
            raise AdminAPIError(
                status_code=status.HTTP_400_BAD_REQUEST,
                message=f"Unsupported listing category: {category}",
            )
        return category

    def _package_model_data(self, payload: dict, partial: bool = False) -> dict:
        field_map = {
            "name": "name",
            "description": "description",
            "duration": "duration",
            "route": "route",
            "basePrice": "base_price",
            "image": "image",
            "category": "category",
            "includes": "includes",
            "itinerary": "itinerary",
            "addOns": "add_ons",
            "isActive": "is_active",
        }
        data = {}
        for source_key, target_key in field_map.items():
            if partial and source_key not in payload:
                continue
            value = payload.get(source_key)
            if value is None and partial:
                continue
            data[target_key] = value
        return data

    def _listing_model_data(self, category: str, payload: dict, partial: bool = False) -> dict:
        location = payload.get("location")
        city, district = self._split_location(location) if location else (None, None)
        status_value = None
        if "isActive" in payload or not partial:
            status_value = ListingStatus.PUBLISHED if payload.get("isActive", True) else ListingStatus.ARCHIVED

        model_data = {
            "type": self.LISTING_TYPE_MAP[category],
            "title": payload.get("title"),
            "slug": self._slugify(payload.get("title")) if payload.get("title") else None,
            "description": payload.get("description"),
            "location_city": city,
            "location_district": district,
            "image": payload.get("image"),
            "rating": payload.get("rating"),
            "cancellation_policy": payload.get("cancellationPolicy"),
            "recommendation": payload.get("recommendation"),
            "base_currency": CurrencyType.LKR,
            "status": status_value,
        }
        if partial:
            return {key: value for key, value in model_data.items() if value is not None}
        return model_data

    def _listing_payload(self, category: str, payload: dict) -> dict:
        payload_copy = dict(payload)
        payload_copy["category"] = category
        return payload_copy

    def _build_package_response(self, package) -> dict:
        return {
            "id": package.id,
            "name": package.name,
            "description": package.description,
            "duration": package.duration,
            "route": package.route,
            "basePrice": package.base_price,
            "image": package.image,
            "category": package.category,
            "includes": package.includes or [],
            "itinerary": package.itinerary or [],
            "addOns": package.add_ons or [],
            "isActive": package.is_active,
        }

    def _build_addon_response(self, addon) -> dict:
        return {
            "id": addon.id,
            "name": addon.name,
            "description": addon.description,
            "price": addon.price,
            "category": addon.category,
        }

    def _build_listing_response(self, listing, detail) -> dict:
        payload = dict(detail.payload)
        payload["id"] = listing.id
        payload["category"] = detail.category
        payload["title"] = listing.title
        payload["description"] = listing.description
        payload["image"] = listing.image
        payload["rating"] = listing.rating
        payload["cancellationPolicy"] = listing.cancellation_policy
        payload["recommendation"] = listing.recommendation
        payload["isActive"] = listing.status == ListingStatus.PUBLISHED
        payload["location"] = ", ".join(
            [part for part in [listing.location_city, listing.location_district] if part]
        )
        return payload

    def _split_location(self, location: str | None) -> tuple[str | None, str | None]:
        if not location:
            return None, None
        parts = [part.strip() for part in location.split(",", 1)]
        if len(parts) == 1:
            return parts[0], None
        return parts[0], parts[1]

    def _slugify(self, value: str | None) -> str | None:
        if not value:
            return None
        return f"{'-'.join(value.lower().split())}-{str(uuid4())[:8]}"

    def _not_found(self, message: str) -> AdminAPIError:
        return AdminAPIError(status_code=status.HTTP_404_NOT_FOUND, message=message)
