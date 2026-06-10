import base64
import binascii
import re
import logging
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy.orm import Session, joinedload

logger = logging.getLogger(__name__)

from app.integrations.cloudinary import upload_image
from app.models.destination import Destination
from app.models.enum import (
    BookingUnit,
    CurrencyCode,
    DestinationType,
    ListingStatus,
    ListingType,
    PricingRuleType,
    StayStatus,
)
from app.models.listing import Listing
from app.models.listingVariant import ListingVariant
from app.models.pricingRule import PricingRule
from app.models.stay import (
    StayProperty,
    StayPropertyAmenity,
    StayPropertyAmenityMap,
    StayRoomType,
    StayRoomUnit,
)
from app.schemas.stay_schema import StayPropertyCreate


class StayRepository:
    DATA_URL_PATTERN = re.compile(r"^data:(image/(?:jpeg|png|webp|gif));base64,(.+)$", re.IGNORECASE | re.DOTALL)
    MAX_IMAGE_BYTES = 10 * 1024 * 1024

    def __init__(self, db: Session):
        self.db = db

    def _base_query(self):
        return self.db.query(StayProperty).options(
            joinedload(StayProperty.amenities).joinedload(StayPropertyAmenityMap.amenity),
            joinedload(StayProperty.room_types).joinedload(StayRoomType.room_units),
        )

    def create_for_vendor(self, vendor_id: UUID, payload: StayPropertyCreate) -> StayProperty:
        """Create a submitted stay, linked parent listing, room variants, and inventory."""
        try:
            data = payload.model_dump(by_alias=False)
            self._normalize_room_type_names(data.get("room_types") or [])

            # STEP 1: Create listing first - this MUST succeed and have an ID
            listing = self._create_listing_parent(vendor_id, data)
            
            # CRITICAL VALIDATION: listing must have ID after flush
            if not listing or not listing.id:
                raise RuntimeError("CRITICAL ERROR: Listing creation failed - no listing ID obtained")
            
            logger.info(f"✓ Created parent listing.id={listing.id}")

            # STEP 2: Build property data with MANDATORY listing_id assignment
            property_data = self._build_property_data(data, vendor_id)
            property_data["listing_id"] = listing.id
            
            # DOUBLE CHECK: Ensure listing_id is assigned in property_data
            if property_data.get("listing_id") is None:
                raise RuntimeError("CRITICAL ERROR: Failed to assign listing_id to property_data")
            
            # STEP 3: Create StayProperty with listing_id
            db_property = StayProperty(**property_data)
            self.db.add(db_property)
            self.db.flush()

            # TRIPLE CHECK: Verify listing_id was set on the StayProperty object
            if db_property.listing_id is None:
                raise RuntimeError("CRITICAL ERROR: StayProperty.listing_id is NULL after creation")
            
            if db_property.listing_id != listing.id:
                raise RuntimeError(f"CRITICAL ERROR: StayProperty.listing_id ({db_property.listing_id}) does not match created listing.id ({listing.id})")
            
            logger.info(f"✓ Created stay_property.id={db_property.id} with listing_id={db_property.listing_id}")

            # STEP 4: Create related data
            self._replace_amenities(db_property.id, data.get("amenities") or [])
            self._create_room_types_and_units(db_property.id, listing.id, data.get("room_types") or [])

            # FINAL VALIDATION: listing_id must still be set before commit
            self.db.refresh(db_property)
            if db_property.listing_id is None:
                raise RuntimeError("CRITICAL ERROR: StayProperty.listing_id became NULL before commit")
            
            # ATOMIC COMMIT: All or nothing
            self.db.commit()
            logger.info(f"✓ Successfully committed stay creation: stay.id={db_property.id}, listing.id={listing.id}")
            
            return self.get_for_vendor(vendor_id, db_property.id)
        except Exception as e:
            self.db.rollback()
            logger.error(f"✗ Stay creation failed for vendor={vendor_id}: {str(e)}")
            raise

    def update_for_vendor(self, vendor_id: UUID, property_id: UUID, payload: StayPropertyCreate) -> StayProperty | None:
        existing_property = self.get_for_vendor(vendor_id, property_id)
        if not existing_property:
            return None

        data = payload.model_dump(by_alias=False)
        self._normalize_room_type_names(data.get("room_types") or [])

        try:
            property_data = self._build_property_data(data, vendor_id)
            property_data.pop("vendor_id", None)
            property_data.pop("listing_id", None)

            if existing_property.status in {StayStatus.APPROVED, StayStatus.REJECTED, StayStatus.ARCHIVED}:
                new_status = property_data.get("status")
                if new_status != existing_property.status:
                    raise ValueError(f"Cannot change status of a stay that is already {existing_property.status.value}")

            for key, value in property_data.items():
                if hasattr(existing_property, key):
                    setattr(existing_property, key, value)

            self._replace_amenities(property_id, data.get("amenities") or [])

            if existing_property.listing_id is not None and data.get("room_types"):
                raise ValueError(
                    "Room configuration cannot be replaced after listing is linked. "
                    "Use room inventory management instead."
                )

            if existing_property.listing_id is None:
                self.db.query(StayRoomUnit).filter(StayRoomUnit.property_id == property_id).delete()
                self.db.query(StayRoomType).filter(StayRoomType.property_id == property_id).delete()
                self.db.flush()
                self._create_room_types_and_units(property_id, None, data.get("room_types") or [])

            self.db.commit()
            return self.get_for_vendor(vendor_id, property_id)
        except Exception:
            self.db.rollback()
            raise

    def list_for_vendor(self, vendor_id: UUID) -> list[StayProperty]:
        return (
            self._base_query()
            .filter(StayProperty.vendor_id == vendor_id)
            .order_by(StayProperty.created_at.desc())
            .all()
        )

    def list_all(self) -> list[StayProperty]:
        return self._base_query().order_by(StayProperty.created_at.desc()).all()

    def get_for_vendor(self, vendor_id: UUID, property_id: UUID) -> StayProperty | None:
        return (
            self._base_query()
            .filter(StayProperty.vendor_id == vendor_id, StayProperty.id == property_id)
            .first()
        )

    def get_by_id(self, property_id: UUID) -> StayProperty | None:
        return self._base_query().filter(StayProperty.id == property_id).first()

    def archive_for_vendor(self, vendor_id: UUID, property_id: UUID, reason: str = None) -> StayProperty | None:
        existing_property = self.get_for_vendor(vendor_id, property_id)
        if not existing_property:
            return None
        if existing_property.status == StayStatus.ARCHIVED:
            raise ValueError("Stay property is already archived")

        existing_property.status = StayStatus.ARCHIVED
        existing_property.is_active = False
        existing_property.archived_at = datetime.now(timezone.utc)
        existing_property.archived_by_id = vendor_id
        existing_property.archive_reason = reason

        if existing_property.listing_id and existing_property.listing:
            existing_property.listing.status = ListingStatus.ARCHIVED
            existing_property.listing.is_active = False

        self.db.commit()
        return existing_property

    def delete_for_vendor(self, vendor_id: UUID, property_id: UUID) -> StayProperty | None:
        existing_property = self.get_for_vendor(vendor_id, property_id)
        if not existing_property:
            return None
        if existing_property.status != StayStatus.DRAFT:
            raise ValueError("Only DRAFT stay properties can be permanently deleted")

        try:
            self.db.delete(existing_property)
            self.db.commit()
            return existing_property
        except Exception:
            self.db.rollback()
            raise

    def _build_property_data(self, data: dict, vendor_id: UUID) -> dict:
        property_data = {
            key: value
            for key, value in data.items()
            if key not in {"amenities", "room_types", "metadata"}
        }
        property_data["vendor_id"] = vendor_id
        property_data["metadata_json"] = data.get("metadata") or {}
        property_data["media"] = self._normalize_media_payload(
            property_data.get("media") or [],
            vendor_id=vendor_id,
        )
        property_data["status"] = self._normalize_vendor_status(property_data.get("status", "SUBMITTED"))
        return property_data

    @staticmethod
    def _normalize_vendor_status(status_input) -> StayStatus:
        if isinstance(status_input, StayStatus):
            status = status_input
        elif isinstance(status_input, str):
            try:
                status = StayStatus(status_input.upper())
            except ValueError as exc:
                raise ValueError(f"Invalid status: {status_input}") from exc
        else:
            raise ValueError("Invalid status type")

        if status in {StayStatus.APPROVED, StayStatus.REJECTED, StayStatus.ARCHIVED}:
            raise ValueError(f"Vendors are not allowed to set status to {status.value}")
        return status

    def _replace_amenities(self, property_id: UUID, amenities: list[dict]) -> None:
        self.db.query(StayPropertyAmenityMap).filter(
            StayPropertyAmenityMap.property_id == property_id
        ).delete()
        self.db.flush()

        for amenity_data in amenities:
            amenity = self._get_or_create_amenity(amenity_data)
            self.db.add(
                StayPropertyAmenityMap(
                    property_id=property_id,
                    amenity_id=amenity.id,
                    value=self._wrap_amenity_value(amenity_data.get("value")),
                )
            )

    def _create_room_types_and_units(
        self,
        property_id: UUID,
        listing_id: UUID | None,
        room_types: list[dict],
    ) -> None:
        for room_type_data in room_types:
            room_data = dict(room_type_data)
            count = room_data.pop("count", 1)
            room_units = room_data.pop("room_units", None)
            unit_prefix = room_data.pop("unit_prefix", None)
            floor = room_data.pop("floor", None)
            metadata = room_data.pop("metadata", {}) or {}
            for metadata_field in ("smoking", "guest_access"):
                value = room_data.pop(metadata_field, None)
                if value is not None:
                    metadata[metadata_field] = value
            if room_data.get("max_guests") is not None:
                room_data["max_guests"] = str(room_data["max_guests"])
            room_data["property_id"] = property_id
            room_data["metadata_json"] = metadata

            room_type = StayRoomType(**room_data)
            self.db.add(room_type)
            self.db.flush()

            if listing_id is not None:
                self._create_listing_variant_for_room(listing_id, room_type)

            unit_numbers = room_units or self._generate_room_numbers(room_type.name, unit_prefix, count)
            for unit_number in unit_numbers:
                self.db.add(
                    StayRoomUnit(
                        property_id=property_id,
                        room_type_id=room_type.id,
                        room_number=unit_number,
                        floor=floor,
                        status="available",
                    )
                )

    def _create_listing_parent(self, vendor_id: UUID, data: dict) -> Listing:
        destination = self._get_or_create_destination(data)
        listing = Listing(
            vendor_id=vendor_id,
            destination_id=destination.id,
            listing_type=ListingType.HOTEL,
            title=data["name"],
            description=data.get("description"),
            latitude=float(data["latitude"]) if data.get("latitude") is not None else None,
            longitude=float(data["longitude"]) if data.get("longitude") is not None else None,
            status=ListingStatus.SUBMITTED,
            base_currency=self._coerce_currency(self._first_room_currency(data.get("room_types") or [])),
            is_active=True,
        )
        try:
            self.db.add(listing)
            self.db.flush()
            
            if not listing.id:
                raise RuntimeError("Listing was created but has no ID")
            
            logger.info(f"Successfully created parent listing.id={listing.id} for vendor={vendor_id}")
            return listing
        except Exception as e:
            logger.error(f"Failed to create parent listing for vendor={vendor_id}: {str(e)}")
            raise RuntimeError(f"Failed to create parent listing: {str(e)}") from e

    def _get_or_create_destination(self, data: dict) -> Destination:
        name = (data.get("city") or data.get("district") or data.get("address") or "Sri Lanka").strip()
        destination = self.db.query(Destination).filter(Destination.name == name).first()
        if destination:
            return destination

        destination = Destination(
            name=name,
            destination_type=DestinationType.CITY,
            latitude=float(data["latitude"]) if data.get("latitude") is not None else None,
            longitude=float(data["longitude"]) if data.get("longitude") is not None else None,
            is_active=True,
        )
        self.db.add(destination)
        self.db.flush()
        return destination

    def _create_listing_variant_for_room(self, listing_id: UUID, room_type: StayRoomType) -> None:
        variant = ListingVariant(
            listing_id=listing_id,
            name=room_type.name,
            booking_unit=BookingUnit.PER_ROOM,
            capacity_min=1,
            capacity_max=int(room_type.max_guests) if room_type.max_guests else None,
            is_default=self.db.query(ListingVariant).filter(ListingVariant.listing_id == listing_id).count() == 0,
        )
        self.db.add(variant)
        self.db.flush()

        if room_type.base_price is None:
            return

        variant.pricing_rules.append(
            PricingRule(
                pricing_rule_type=PricingRuleType.FIXED,
                min_guest=1,
                max_guest=int(room_type.max_guests) if room_type.max_guests else 999999,
                amount=float(room_type.base_price),
                currency=self._coerce_currency(room_type.currency),
                priority=0,
            )
        )

    def _get_or_create_amenity(self, amenity_data: dict) -> StayPropertyAmenity:
        name = amenity_data["name"].strip()
        amenity = (
            self.db.query(StayPropertyAmenity)
            .filter(StayPropertyAmenity.name == name)
            .first()
        )
        if amenity:
            return amenity

        amenity = StayPropertyAmenity(
            name=name,
            description=amenity_data.get("description"),
            value_type=amenity_data.get("value_type") or "boolean",
            category=amenity_data.get("category"),
        )
        self.db.add(amenity)
        self.db.flush()
        return amenity

    @staticmethod
    def _wrap_amenity_value(value):
        if isinstance(value, dict):
            return value
        return {"value": value}

    @classmethod
    def _normalize_room_type_names(cls, room_types: list[dict]) -> None:
        for room_type_data in room_types:
            if room_type_data.get("name"):
                room_type_data["name"] = cls._normalize_room_type_name(room_type_data["name"])

    @staticmethod
    def _normalize_room_type_name(name: str) -> str:
        name = name.strip()
        room_type_mapping = {
            "bedroom": "Bedroom",
            "bed room": "Bedroom",
            "bedrooms": "Bedroom",
            "bed rooms": "Bedroom",
            "living room": "Living Room",
            "livingroom": "Living Room",
            "living rooms": "Living Room",
            "livingrooms": "Living Room",
            "bathroom": "Bathroom",
            "bath room": "Bathroom",
            "bathrooms": "Bathroom",
            "bath rooms": "Bathroom",
            "kitchen": "Kitchen",
            "kitchens": "Kitchen",
            "dining room": "Dining Room",
            "diningroom": "Dining Room",
            "dining rooms": "Dining Room",
            "diningrooms": "Dining Room",
            "office": "Office",
            "offices": "Office",
            "study": "Study",
            "studio": "Studio",
            "suite": "Suite",
            "suites": "Suite",
            "deluxe room": "Deluxe Room",
            "deluxe": "Deluxe Room",
            "standard room": "Standard Room",
            "standard": "Standard Room",
            "single room": "Single Room",
            "single": "Single Room",
            "double room": "Double Room",
            "double": "Double Room",
            "twin room": "Twin Room",
            "twin": "Twin Room",
            "master bedroom": "Master Bedroom",
            "master bed room": "Master Bedroom",
        }
        return room_type_mapping.get(name.lower(), name.title())

    @staticmethod
    def _generate_room_numbers(name: str, prefix: str | None, count: int) -> list[str]:
        safe_prefix = prefix or "".join(part[:1] for part in name.split() if part).upper() or "RM"
        return [f"{safe_prefix}-{index:03d}" for index in range(1, count + 1)]

    def _normalize_media_payload(self, media_items: list[dict], vendor_id: UUID) -> list[dict]:
        normalized: list[dict] = []
        folder = f"tour-ceylon/vendor-stays/{vendor_id}"

        for index, item in enumerate(media_items):
            url = item.get("url")
            if not isinstance(url, str) or not url:
                continue

            if not url.startswith("data:"):
                normalized.append(item)
                continue

            match = self.DATA_URL_PATTERN.match(url)
            if not match:
                raise ValueError("Unsupported image data URL format")

            content_type, encoded = match.groups()
            try:
                file_bytes = base64.b64decode(encoded, validate=True)
            except (binascii.Error, ValueError) as exc:
                raise ValueError("Invalid image data URL") from exc

            if not file_bytes:
                raise ValueError("Uploaded image is empty")
            if len(file_bytes) > self.MAX_IMAGE_BYTES:
                raise ValueError("Uploaded image exceeds size limit")

            upload_result = upload_image(file_bytes, folder=folder)
            normalized.append(
                {
                    **{key: value for key, value in item.items() if key != "url"},
                    "url": upload_result["secure_url"],
                    "cloudinaryPublicId": upload_result["public_id"],
                    "resourceType": upload_result.get("resource_type", "image"),
                    "format": upload_result.get("format"),
                    "width": upload_result.get("width"),
                    "height": upload_result.get("height"),
                    "bytes": upload_result.get("bytes", len(file_bytes)),
                    "contentType": content_type,
                    "sortOrder": item.get("sortOrder", index),
                }
            )

        return normalized

    @staticmethod
    def _first_room_currency(room_types: list[dict]) -> str:
        for room_type in room_types:
            currency = room_type.get("currency")
            if currency:
                return currency
        return CurrencyCode.LKR.value

    @staticmethod
    def _coerce_currency(value: str | CurrencyCode | None) -> CurrencyCode:
        if isinstance(value, CurrencyCode):
            return value
        try:
            return CurrencyCode(value or CurrencyCode.LKR.value)
        except ValueError:
            return CurrencyCode.LKR
