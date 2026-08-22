import logging
import time as perf_time
from datetime import time
from uuid import UUID

from fastapi import status
from sqlalchemy.orm import Session

from app.api.errors import AdminAPIError
from app.models.destination import Destination
from app.models.enum import BookingUnit, CurrencyCode, ListingStatus, ListingType
from app.models.listing import Listing
from app.models.stay import StayProperty
from app.repositories.admin.addon_repo import AdminAddonRepository
from app.repositories.admin.destination_repo import AdminDestinationRepository
from app.repositories.admin.listing_repo import AdminDashboardListingRepository
from app.repositories.admin.package_repo import AdminPackageRepository
from app.repositories.admin.settings_repo import AdminSettingsRepository
from app.services.package_service import build_package_response


class AdminDashboardService:
    VALID_LISTING_CATEGORIES = {"stay", "tour", "safari", "experience", "transfer"}
    LISTING_TYPE_MAP = {
        "stay": ListingType.HOTEL,
        "tour": ListingType.TOUR,
        "safari": ListingType.SAFARI,
        "experience": ListingType.EXPERIENCE,
        "transfer": ListingType.TRANSFER,
    }
    CATEGORY_BY_LISTING_TYPE = {value: key for key, value in LISTING_TYPE_MAP.items()}
    logger = logging.getLogger("app.admin.dashboard")

    def __init__(self, db: Session):
        self.db = db
        self.addons = AdminAddonRepository(db)
        self.destinations = AdminDestinationRepository(db)
        self.packages = AdminPackageRepository(db)
        self.settings = AdminSettingsRepository(db)
        self.listings = AdminDashboardListingRepository(db)

    def get_snapshot(self, current_user) -> dict:
        started_at = perf_time.perf_counter()
        listing_groups = {"stay": [], "tour": [], "safari": [], "experience": [], "transfer": []}
        for listing in self.listings.get_all_listings(current_user):
            category = self.CATEGORY_BY_LISTING_TYPE.get(listing.listing_type)
            if category in listing_groups:
                listing_groups[category].append(self._build_listing_response(listing))

        snapshot = {
            "packages": [self._build_package_response(package) for package in self.packages.get_all()],
            "addOns": [self._build_addon_response(addon) for addon in self.addons.get_all()],
            "settings": self.get_settings(),
            "listings": listing_groups,
        }
        listing_count = sum(len(items) for items in listing_groups.values())
        self.logger.info(
            "admin_dashboard.get_snapshot_timing scope=%s listing_count=%s elapsed_ms=%.2f",
            getattr(current_user, "id", None),
            listing_count,
            (perf_time.perf_counter() - started_at) * 1000,
        )
        return snapshot

    def get_listings(self, category: str, current_user) -> list[dict]:
        started_at = perf_time.perf_counter()
        category = self._validate_category(category)
        listing_type = self.LISTING_TYPE_MAP[category]
        listings = self.listings.get_listings_by_type(listing_type, current_user)
        response = [self._build_listing_response(listing) for listing in listings]
        self.logger.info(
            "admin_dashboard.get_listings_timing category=%s scope=%s result_count=%s elapsed_ms=%.2f",
            category,
            getattr(current_user, "id", None),
            len(response),
            (perf_time.perf_counter() - started_at) * 1000,
        )
        return response

    def get_destinations(self) -> list[dict]:
        return [
            {
                "id": destination.id,
                "name": destination.name,
                "destination_type": destination.destination_type,
                "latitude": destination.latitude,
                "longitude": destination.longitude,
                "city": None,
                "district": None,
            }
            for destination in self.destinations.get_all_active()
        ]

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

    def update_listing_status(self, category: str, listing_id: UUID, listing_status: ListingStatus) -> dict:
        category = self._validate_category(category)
        listing = self.listings.get_listing(listing_id)
        if listing is None or listing.listing_type != self.LISTING_TYPE_MAP[category]:
            raise self._not_found("Listing not found")

        listing.status = listing_status
        listing.is_active = listing_status == ListingStatus.PUBLISHED

        if listing.listing_type == ListingType.HOTEL:
            stay_status = {
                ListingStatus.DRAFT: "DRAFT",
                ListingStatus.SUBMITTED: "SUBMITTED",
                ListingStatus.PUBLISHED: "APPROVED",
                ListingStatus.REJECTED: "REJECTED",
                ListingStatus.ARCHIVED: "ARCHIVED",
            }[listing_status]
            (
                self.db.query(StayProperty)
                .filter(StayProperty.listing_id == listing.id)
                .update({"status": stay_status}, synchronize_session=False)
            )

        self.db.commit()
        return self._build_listing_response(self.listings.get_listing(listing.id))

    def delete_listing(self, category: str, listing_id: UUID) -> None:
        category = self._validate_category(category)
        listing = self.listings.get_listing(listing_id)
        if listing is None or listing.listing_type != self.LISTING_TYPE_MAP[category]:
            raise self._not_found("Listing not found")

        if listing.listing_type == ListingType.HOTEL:
            (
                self.db.query(StayProperty)
                .filter(StayProperty.listing_id == listing.id)
                .update({"listing_id": None}, synchronize_session=False)
            )
            self.db.flush()

        if not self.listings.delete_listing(listing_id):
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
            "summary": "summary",
            "description": "description",
            "duration": "duration",
            "nights": "nights",
            "route": "route",
            "startLocation": "start_location",
            "endLocation": "end_location",
            "tripStyle": "trip_style",
            "basePrice": "base_price",
            "image": "image",
            "category": "category",
            "includes": "includes",
            "exclusions": "exclusions",
            "highlights": "highlights",
            "quickFacts": "quick_facts",
            "destinations": "destinations",
            "itinerary": "itinerary",
            "structuredItinerary": "structured_itinerary",
            "listingRefs": "listing_refs",
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

        # Auto-generate simple itinerary if structured exists but simple doesn't
        if data.get("structured_itinerary"):
            if not data.get("itinerary"):
                data["itinerary"] = self._derive_simple_itinerary(data["structured_itinerary"])

        return data

    def _derive_simple_itinerary(self, structured_items: list[dict]) -> list[dict]:
        results = []
        for day in structured_items or []:
            overview = (day.get("overview") or "").strip()
            if overview:
                description = overview
            else:
                parts = []
                for block in day.get("blocks", []) or []:
                    title = (block.get("title") or "").strip()
                    desc = (block.get("description") or "").strip()
                    if title and desc:
                        parts.append(f"{title}: {desc}")
                    elif title:
                        parts.append(title)
                description = " ".join(parts).strip()
            results.append({
                "day": int(day.get("day") or 0),
                "title": day.get("title") or f"Day {day.get('day')}",
                "description": description,
            })
        return [item for item in results if item["day"] > 0]

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
        }

        detail_key = self._detail_key_for_category(category)
        if detail_key in payload and payload[detail_key] is not None:
            model_data[detail_key] = self._normalize_detail_payload(detail_key, payload[detail_key])
        if "variants" in payload and payload["variants"] is not None:
            model_data["variants"] = [
                self._normalize_variant_payload(category, variant, model_data["base_currency"])
                for variant in payload["variants"]
            ]

        if partial:
            return {key: value for key, value in model_data.items() if value is not None}
        return model_data

    def _normalize_variant_payload(self, category: str, variant_payload: dict, base_currency: CurrencyCode) -> dict:
        pricing_payload = variant_payload["pricing"]
        booking_unit = variant_payload["booking_unit"]
        if category == "stay" and booking_unit != BookingUnit.PER_ROOM:
            raise AdminAPIError(
                status_code=status.HTTP_400_BAD_REQUEST,
                message="Hotel variants must use per_room booking_unit",
            )
        return {
            "name": variant_payload["name"].strip(),
            "booking_unit": booking_unit,
            "capacity_min": variant_payload.get("capacity_min"),
            "capacity_max": variant_payload.get("capacity_max"),
            "is_default": variant_payload.get("is_default", False),
            "pricing": {
                "amount": pricing_payload["amount"],
                "currency": pricing_payload.get("currency", base_currency),
                "priority": pricing_payload["priority"],
            },
        }

    def _normalize_detail_payload(self, detail_key: str, detail_payload: dict) -> dict:
        normalized = dict(detail_payload)
        if detail_key == "hotel_detail":
            normalized["check_in_time"] = self._parse_time(normalized["check_in_time"])
            normalized["check_out_time"] = self._parse_time(normalized["check_out_time"])
            normalized["amenities"] = list(normalized.get("amenities") or [])
            normalized["languages_spoken"] = list(normalized.get("languages_spoken") or [])
            normalized["meal_plans"] = list(normalized.get("meal_plans") or [])
        elif detail_key == "tour_detail":
            normalized["itinerary_highlights"] = list(normalized.get("itinerary_highlights") or [])
            normalized["included_items"] = list(normalized.get("included_items") or [])
            normalized["excluded_items"] = list(normalized.get("excluded_items") or [])
            normalized["languages"] = list(normalized.get("languages") or [])
            normalized["what_to_bring"] = list(normalized.get("what_to_bring") or [])
            if normalized.get("start_time") is not None:
                normalized["start_time"] = self._parse_time(normalized["start_time"])
            if normalized.get("end_time") is not None:
                normalized["end_time"] = self._parse_time(normalized["end_time"])
        elif detail_key == "safari_detail":
            normalized["included_items"] = list(normalized.get("included_items") or [])
            normalized["excluded_items"] = list(normalized.get("excluded_items") or [])
            normalized["languages"] = list(normalized.get("languages") or [])
            normalized["what_to_bring"] = list(normalized.get("what_to_bring") or [])
            normalized["wildlife_highlights"] = list(normalized.get("wildlife_highlights") or [])
            if normalized.get("start_time") is not None:
                normalized["start_time"] = self._parse_time(normalized["start_time"])
            if normalized.get("end_time") is not None:
                normalized["end_time"] = self._parse_time(normalized["end_time"])
        elif detail_key == "activity_detail":
            normalized["included_items"] = list(normalized.get("included_items") or [])
            normalized["excluded_items"] = list(normalized.get("excluded_items") or [])
            normalized["languages"] = list(normalized.get("languages") or [])
            normalized["what_to_bring"] = list(normalized.get("what_to_bring") or [])
            normalized["highlights"] = list(normalized.get("highlights") or [])
            if normalized.get("start_time") is not None:
                normalized["start_time"] = self._parse_time(normalized["start_time"])
            if normalized.get("end_time") is not None:
                normalized["end_time"] = self._parse_time(normalized["end_time"])
        elif detail_key == "transfer_detail":
            normalized["vehicle_types"] = list(normalized.get("vehicle_types") or [])
            normalized["included_items"] = list(normalized.get("included_items") or [])
            normalized["excluded_items"] = list(normalized.get("excluded_items") or [])
            if normalized.get("operating_start_time") is not None:
                normalized["operating_start_time"] = self._parse_time(normalized["operating_start_time"])
            if normalized.get("operating_end_time") is not None:
                normalized["operating_end_time"] = self._parse_time(normalized["operating_end_time"])
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
            "safari": "safari_detail",
            "experience": "activity_detail",
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
            "status": getattr(listing.status, "value", listing.status),
            "created_at": listing.created_at.isoformat() if listing.created_at else None,
            "updated_at": listing.updated_at.isoformat() if listing.updated_at else None,
            "latitude": listing.latitude,
            "longitude": listing.longitude,
            "from_price": listing.from_price,
            "cover_image": listing.cover_image,
            "gallery": listing.gallery,
            "variants": [self._build_listing_variant_response(variant) for variant in getattr(listing, "variants", []) or []],
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
            "activity_detail": self._build_activity_detail(listing),
            "transfer_detail": self._build_transfer_detail(listing),
        }
        return {key: value for key, value in payload.items() if value is not None}

    def _build_listing_variant_response(self, variant) -> dict:
        pricing_rules = list(getattr(variant, "pricing_rules", []) or [])
        pricing_rule = (
            sorted(pricing_rules, key=lambda rule: (rule.priority, rule.created_at, rule.id))[0]
            if pricing_rules
            else None
        )
        return {
            "id": variant.id,
            "name": variant.name,
            "booking_unit": getattr(variant.booking_unit, "value", variant.booking_unit),
            "capacity_min": variant.capacity_min,
            "capacity_max": variant.capacity_max,
            "is_default": variant.is_default,
            "pricing": (
                {
                    "amount": pricing_rule.amount,
                    "currency": getattr(pricing_rule.currency, "value", pricing_rule.currency),
                    "priority": pricing_rule.priority,
                }
                if pricing_rule is not None
                else None
            ),
        }

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
            "property_name": detail.property_name,
            "short_location": detail.short_location,
            "address_line_1": detail.address_line_1,
            "address_line_2": detail.address_line_2,
            "city": detail.city,
            "district": detail.district,
            "postal_code": detail.postal_code,
            "contact_phone": detail.contact_phone,
            "contact_email": detail.contact_email,
            "website": detail.website,
            "google_map_url": detail.google_map_url,
            "amenities": detail.amenities or [],
            "languages_spoken": detail.languages_spoken or [],
            "room_count": detail.room_count,
            "max_guest_capacity": detail.max_guest_capacity,
            "meal_plans": detail.meal_plans or [],
            "parking_available": detail.parking_available,
            "wifi_available": detail.wifi_available,
            "pets_allowed": detail.pets_allowed,
            "smoking_policy": detail.smoking_policy,
            "cancellation_policy": detail.cancellation_policy,
            "extra_bed_policy": detail.extra_bed_policy,
            "check_in_notes": detail.check_in_notes,
            "check_out_notes": detail.check_out_notes,
        }

    def _build_tour_detail(self, listing: Listing) -> dict | None:
        detail = listing.tour_detail
        if detail is None:
            return None
        return {
            "duration_days": detail.duration_days,
            "route_summary": detail.route_summary,
            "meeting_point": detail.meeting_point,
            "itinerary_highlights": detail.itinerary_highlights or [],
            "included_items": detail.included_items or [],
            "excluded_items": detail.excluded_items or [],
            "languages": detail.languages or [],
            "difficulty_level": detail.difficulty_level,
            "group_size_min": detail.group_size_min,
            "group_size_max": detail.group_size_max,
            "private_available": detail.private_available,
            "pickup_available": detail.pickup_available,
            "dropoff_available": detail.dropoff_available,
            "pickup_notes": detail.pickup_notes,
            "dropoff_notes": detail.dropoff_notes,
            "start_time": detail.start_time.isoformat() if detail.start_time else None,
            "end_time": detail.end_time.isoformat() if detail.end_time else None,
            "cancellation_policy": detail.cancellation_policy,
            "what_to_bring": detail.what_to_bring or [],
            "child_policy": detail.child_policy,
            "accessibility_info": detail.accessibility_info,
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
            "start_time": detail.start_time.isoformat() if detail.start_time else None,
            "end_time": detail.end_time.isoformat() if detail.end_time else None,
            "included_items": detail.included_items or [],
            "excluded_items": detail.excluded_items or [],
            "languages": detail.languages or [],
            "difficulty_level": detail.difficulty_level,
            "age_restriction": detail.age_restriction,
            "private_available": detail.private_available,
            "group_size_min": detail.group_size_min,
            "group_size_max": detail.group_size_max,
            "pickup_notes": detail.pickup_notes,
            "what_to_bring": detail.what_to_bring or [],
            "cancellation_policy": detail.cancellation_policy,
            "accessibility_info": detail.accessibility_info,
            "best_season": detail.best_season,
            "wildlife_highlights": detail.wildlife_highlights or [],
        }

    def _build_transfer_detail(self, listing: Listing) -> dict | None:
        detail = listing.transfer_detail
        if detail is None:
            return None
        return {
            "origin_type": detail.origin_type,
            "destination_type": detail.destination_type,
            "vehicle_policy": detail.vehicle_policy,
            "vehicle_types": detail.vehicle_types or [],
            "max_passengers": detail.max_passengers,
            "max_luggage": detail.max_luggage,
            "air_conditioned": detail.air_conditioned,
            "meet_and_greet_included": detail.meet_and_greet_included,
            "child_seats_available": detail.child_seats_available,
            "pickup_instructions": detail.pickup_instructions,
            "dropoff_instructions": detail.dropoff_instructions,
            "operating_start_time": detail.operating_start_time.isoformat() if detail.operating_start_time else None,
            "operating_end_time": detail.operating_end_time.isoformat() if detail.operating_end_time else None,
            "estimated_duration_minutes": detail.estimated_duration_minutes,
            "route_notes": detail.route_notes,
            "included_items": detail.included_items or [],
            "excluded_items": detail.excluded_items or [],
            "cancellation_policy": detail.cancellation_policy,
            "waiting_time_policy": detail.waiting_time_policy,
        }

    def _build_activity_detail(self, listing: Listing) -> dict | None:
        detail = listing.activity_detail
        if detail is None:
            return None
        return {
            "activity_type": detail.activity_type,
            "duration_minutes": detail.duration_minutes,
            "meeting_point": detail.meeting_point,
            "start_time": detail.start_time.isoformat() if detail.start_time else None,
            "end_time": detail.end_time.isoformat() if detail.end_time else None,
            "included_items": detail.included_items or [],
            "excluded_items": detail.excluded_items or [],
            "languages": detail.languages or [],
            "difficulty_level": detail.difficulty_level,
            "age_restriction": detail.age_restriction,
            "private_available": detail.private_available,
            "group_size_min": detail.group_size_min,
            "group_size_max": detail.group_size_max,
            "pickup_supported": detail.pickup_supported,
            "pickup_notes": detail.pickup_notes,
            "what_to_bring": detail.what_to_bring or [],
            "cancellation_policy": detail.cancellation_policy,
            "accessibility_info": detail.accessibility_info,
            "highlights": detail.highlights or [],
            "availability_notes": detail.availability_notes,
        }

    def _not_found(self, message: str) -> AdminAPIError:
        return AdminAPIError(status_code=status.HTTP_404_NOT_FOUND, message=message)
