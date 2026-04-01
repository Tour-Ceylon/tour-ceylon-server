from uuid import UUID, uuid4

from fastapi import status
from sqlalchemy.orm import Session, joinedload

from app.api.errors import AdminAPIError
from app.models.destination import Destination
from app.models.enum import CurrencyCode, ListingType
from app.models.listing import Listing
from app.repositories.admin.addon_repo import AdminAddonRepository
from app.repositories.admin.listing_repo import AdminDashboardListingRepository
from app.repositories.admin.package_repo import AdminPackageRepository
from app.repositories.admin.settings_repo import AdminSettingsRepository
from app.services.package_service import build_package_response


class AdminDashboardService:
    VALID_LISTING_CATEGORIES = {"stay", "tour", "activity", "transfer"}
    LISTING_TYPE_MAP = {
        "stay": ListingType.HOTEL,
        "tour": ListingType.TOUR,
        "activity": ListingType.SAFARI,
        "transfer": ListingType.TRANSFER,
    }
    CATEGORY_BY_LISTING_TYPE = {value: key for key, value in LISTING_TYPE_MAP.items()}

    def __init__(self, db: Session):
        self.db = db
        self.addons = AdminAddonRepository(db)
        self.packages = AdminPackageRepository(db)
        self.settings = AdminSettingsRepository(db)
        self.listings = AdminDashboardListingRepository(db)

    def get_snapshot(self) -> dict:
        listing_groups = {"stay": [], "tour": [], "activity": [], "transfer": []}
        listings = (
            self.db.query(Listing)
            .options(joinedload(Listing.destination))
            .order_by(Listing.created_at.desc())
            .all()
        )
        for listing in listings:
            category = self.CATEGORY_BY_LISTING_TYPE.get(listing.listing_type)
            if category in listing_groups:
                listing_groups[category].append(self._build_listing_response(listing))

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
        normalized_payload = {
            **payload,
            "category": self._normalize_addon_category(payload["category"]),
        }
        addon = self.addons.create(**normalized_payload)
        return self._build_addon_response(addon)

    def delete_addon(self, addon_id: UUID) -> None:
        if not self.addons.delete(addon_id):
            raise self._not_found("Add-on not found")

    def create_listing(self, category: str, payload: dict) -> dict:
        category = self._validate_category(category)
        listing = self.listings.create_listing(self._listing_model_data(category, payload))
        listing = self._get_listing_with_destination(listing.id)
        return self._build_listing_response(listing)

    def update_listing(self, category: str, listing_id: UUID, payload: dict) -> dict:
        category = self._validate_category(category)
        listing = self._get_listing_with_destination(listing_id)
        if listing is None or listing.listing_type != self.LISTING_TYPE_MAP[category]:
            raise self._not_found("Listing not found")

        listing_updates = self._listing_model_data(category, payload, partial=True)
        if listing_updates:
            self.listings.update_listing(listing, listing_updates)

        listing = self._get_listing_with_destination(listing_id)
        return self._build_listing_response(listing)

    def delete_listing(self, category: str, listing_id: UUID) -> None:
        category = self._validate_category(category)
        listing = self._get_listing_with_destination(listing_id)
        if listing is None or listing.listing_type != self.LISTING_TYPE_MAP[category]:
            raise self._not_found("Listing not found")

        self.listings.delete_listing(listing_id)

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

    def _get_listing_with_destination(self, listing_id: UUID) -> Listing | None:
        return (
            self.db.query(Listing)
            .options(joinedload(Listing.destination))
            .filter(Listing.id == listing_id)
            .first()
        )

    def _validate_destination_id(self, destination_id: UUID) -> None:
        if self.db.get(Destination, destination_id) is None:
            raise AdminAPIError(
                status_code=status.HTTP_400_BAD_REQUEST,
                message="Destination not found",
            )

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
            if source_key == "category" and value is not None:
                value = self._normalize_package_category(value)
            data[target_key] = value
        return data

    def _normalize_package_category(self, category: str) -> str:
        return category.strip().replace("-", "_").upper()

    def _normalize_addon_category(self, category: str) -> str:
        normalized = category.strip().replace("-", "_").upper()
        aliases = {
            "ACCOMMODATION": "COMFORT",
        }
        return aliases.get(normalized, normalized)

    def _listing_model_data(self, category: str, payload: dict, partial: bool = False) -> dict:
        destination_id = payload.get("destinationId")
        if destination_id is not None:
            self._validate_destination_id(destination_id)
        elif not partial:
            raise AdminAPIError(
                status_code=status.HTTP_400_BAD_REQUEST,
                message="destinationId is required",
            )

        is_active = payload.get("isActive", True) if not partial or "isActive" in payload else None

        model_data = {
            "listing_type": self.LISTING_TYPE_MAP[category],
            "destination_id": destination_id,
            "title": payload.get("title"),
            "slug": self._slugify(payload.get("title")) if payload.get("title") else None,
            "description": payload.get("description"),
            "latitude": payload.get("latitude"),
            "longitude": payload.get("longitude"),
            "is_active": is_active,
            "base_currency": CurrencyCode.LKR,
        }

        if partial:
            return {key: value for key, value in model_data.items() if value is not None}
        return model_data

    def _build_package_response(self, package) -> dict:
        return build_package_response(package)

    def _build_addon_response(self, addon) -> dict:
        category = getattr(addon.category, "value", addon.category)
        if isinstance(category, str):
            category = category.lower().replace("_", "-")
        return {
            "id": addon.id,
            "name": addon.name,
            "description": addon.description,
            "price": addon.price,
            "category": category,
        }

    def _build_listing_response(self, listing) -> dict:
        category = self.CATEGORY_BY_LISTING_TYPE.get(listing.listing_type, listing.listing_type.value)
        payload = {
            "id": listing.id,
            "category": category,
            "destinationId": listing.destination_id,
            "title": listing.title,
            "description": listing.description,
            "location": listing.destination.name if listing.destination else None,
            "isActive": listing.is_active,
            "latitude": listing.latitude,
            "longitude": listing.longitude,
            "destination": {
                "id": listing.destination.id,
                "name": listing.destination.name,
                "latitude": listing.destination.latitude,
                "longitude": listing.destination.longitude,
            } if listing.destination else None,
            "rooms": [],
            "reviewMetrics": [],
            "guestReviews": [],
            "highlights": [],
            "serviceHighlights": [],
        }
        return {k: v for k, v in payload.items() if v is not None}

    def _slugify(self, value: str | None) -> str | None:
        if not value:
            return None
        return f"{'-'.join(value.lower().split())}-{str(uuid4())[:8]}"

    def _not_found(self, message: str) -> AdminAPIError:
        return AdminAPIError(status_code=status.HTTP_404_NOT_FOUND, message=message)
