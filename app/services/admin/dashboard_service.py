from datetime import time
from uuid import UUID

from fastapi import status
from sqlalchemy.orm import Session

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
        for listing in self.listings.get_all_listings():
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
        return self._build_listing_response(listing)

    def update_listing(self, category: str, listing_id: UUID, payload: dict) -> dict:
        category = self._validate_category(category)
        listing = self.listings.get_listing(listing_id)
        if listing is None or listing.listing_type != self.LISTING_TYPE_MAP[category]:
            raise self._not_found("Listing not found")

        listing_updates = self._listing_model_data(category, payload, partial=True)
        updated = self.listings.update_listing(listing_id, listing_updates)
        if updated is None:
            raise self._not_found("Listing not found")
        return self._build_listing_response(updated)

    def delete_listing(self, category: str, listing_id: UUID) -> None:
        category = self._validate_category(category)
        listing = self.listings.get_listing(listing_id)
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
        destination_id = payload.get("destination_id")
        if destination_id is not None:
            self._validate_destination_id(destination_id)
        elif not partial:
            raise AdminAPIError(
                status_code=status.HTTP_400_BAD_REQUEST,
                message="destination_id is required",
            )

        model_data = {
            "listing_type": self.LISTING_TYPE_MAP[category],
            "destination_id": destination_id,
            "title": payload.get("title"),
            "slug": payload.get("slug"),
            "description": payload.get("description"),
            "latitude": payload.get("latitude"),
            "longitude": payload.get("longitude"),
            "is_active": payload.get("is_active"),
            "base_currency": payload.get("base_currency", CurrencyCode.LKR),
            "media": self._normalize_media_payload(payload.get("media")) if "media" in payload else ([] if not partial else None),
        }

        detail_key = self._detail_key_for_category(category)
        if detail_key in payload and payload[detail_key] is not None:
            model_data[detail_key] = self._normalize_detail_payload(detail_key, payload[detail_key])

        if partial:
            return {key: value for key, value in model_data.items() if value is not None}
        return model_data

    def _normalize_detail_payload(self, detail_key: str, detail_payload: dict) -> dict:
        normalized = dict(detail_payload)
        if detail_key == "hotel_detail":
            normalized["check_in_time"] = self._parse_time(normalized["check_in_time"])
            normalized["check_out_time"] = self._parse_time(normalized["check_out_time"])
        return normalized

    def _normalize_media_payload(self, media_payload: list[dict] | None) -> list[dict] | None:
        if media_payload is None:
            return None

        normalized_media = []
        for media in media_payload:
            normalized_media.append(
                {
                    "url": media["url"],
                    "alt_text": media.get("alt_text", media.get("altText")),
                    "sort_order": media.get("sort_order", media.get("sortOrder")),
                    "is_cover": media.get("is_cover", media.get("isCover", False)),
                    "media_type": media.get("media_type", media.get("mediaType")),
                }
            )
        return normalized_media

    def _parse_time(self, raw_value: str | time) -> time:
        if isinstance(raw_value, time):
            return raw_value
        try:
            return time.fromisoformat(raw_value)
        except ValueError as exc:
            raise AdminAPIError(
                status_code=status.HTTP_400_BAD_REQUEST,
                message=f"Invalid time value: {raw_value}",
            ) from exc

    def _detail_key_for_category(self, category: str) -> str:
        return {
            "stay": "hotel_detail",
            "tour": "tour_detail",
            "activity": "safari_detail",
            "transfer": "transfer_detail",
        }[category]

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

    def _build_listing_response(self, listing: Listing) -> dict:
        payload = {
            "id": listing.id,
            "category": self.CATEGORY_BY_LISTING_TYPE.get(listing.listing_type, listing.listing_type.value),
            "destination_id": listing.destination_id,
            "title": listing.title,
            "description": listing.description,
            "is_active": listing.is_active,
            "latitude": listing.latitude,
            "longitude": listing.longitude,
            "media": [
                {
                    "id": media.id,
                    "url": media.url,
                    "alt_text": media.alt_text,
                    "sort_order": media.sort_order,
                    "is_cover": media.is_cover,
                    "media_type": media.media_type,
                }
                for media in listing.media
            ],
            "destination": {
                "id": listing.destination.id,
                "name": listing.destination.name,
                "destination_type": listing.destination.destination_type,
                "latitude": listing.destination.latitude,
                "longitude": listing.destination.longitude,
            }
            if listing.destination
            else None,
            "hotel_detail": self._build_hotel_detail(listing),
            "tour_detail": self._build_tour_detail(listing),
            "safari_detail": self._build_safari_detail(listing),
            "transfer_detail": self._build_transfer_detail(listing),
        }
        return {key: value for key, value in payload.items() if value is not None}

    def _build_hotel_detail(self, listing: Listing) -> dict | None:
        detail = listing.hotel_detail
        if detail is None:
            return None
        return {
            "property_type": detail.property_type,
            "star_rating": detail.star_rating,
            "check_in_time": detail.check_in_time.isoformat(),
            "check_out_time": detail.check_out_time.isoformat(),
            "child_policy": detail.child_policy,
        }

    def _build_tour_detail(self, listing: Listing) -> dict | None:
        detail = listing.tour_detail
        if detail is None:
            return None
        return {
            "duration_days": detail.duration_days,
            "route_summary": detail.route_summary,
            "meeting_point": detail.meeting_point,
        }

    def _build_safari_detail(self, listing: Listing) -> dict | None:
        detail = listing.safari_detail
        if detail is None:
            return None
        return {
            "national_park": detail.national_park,
            "safari_type": detail.safari_type,
            "duration_minutes": detail.duration_minutes,
            "guide_included": detail.guide_included,
            "pickup_supported": detail.pickup_supported,
        }

    def _build_transfer_detail(self, listing: Listing) -> dict | None:
        detail = listing.transfer_detail
        if detail is None:
            return None
        return {
            "origin_type": detail.origin_type,
            "destination_type": detail.destination_type,
            "vehicle_policy": detail.vehicle_policy,
        }

    def _not_found(self, message: str) -> AdminAPIError:
        return AdminAPIError(status_code=status.HTTP_404_NOT_FOUND, message=message)
