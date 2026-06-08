import base64
import binascii
import re
from uuid import UUID

from sqlalchemy.orm import Session, joinedload

from app.integrations.cloudinary import upload_image
from app.models.stay import (
    StayProperty,
    StayPropertyAmenity,
    StayPropertyAmenityMap,
    StayRoomType,
    StayRoomUnit,
)
from app.models.listing import Listing
from app.models.destination import Destination
from app.models.enum import ListingType, ListingStatus, CurrencyCode, DestinationType, StayStatus
from app.repositories.listing_repo import ListingRepository
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
        try:
            # Step 1: Create StayProperty (Listing is only created when approved by admin)
            data = payload.model_dump(by_alias=False)
            property_data = {
                key: value
                for key, value in data.items()
                if key not in {"amenities", "room_types", "metadata"}
            }
            property_data["vendor_id"] = vendor_id
            property_data["listing_id"] = None  # Decoupled on vendor create
            property_data["metadata_json"] = data.get("metadata") or {}

            property_data["media"] = self._normalize_media_payload(
                property_data.get("media") or [],
                vendor_id=vendor_id,
            )

            # Ensure proper status handling and validation for StayProperty
            status_input = property_data.get("status", "SUBMITTED")
            if isinstance(status_input, str):
                status_upper = status_input.upper()
                if status_upper == "DRAFT":
                    property_data["status"] = StayStatus.DRAFT
                elif status_upper == "SUBMITTED":
                    property_data["status"] = StayStatus.SUBMITTED
                elif status_upper in ["APPROVED", "REJECTED", "ARCHIVED"]:
                    raise ValueError(f"Vendors are not allowed to set status to {status_upper}")
                else:
                    raise ValueError(f"Invalid status: {status_input}")
            elif isinstance(status_input, StayStatus):
                if status_input in [StayStatus.APPROVED, StayStatus.REJECTED, StayStatus.ARCHIVED]:
                    raise ValueError(f"Vendors are not allowed to set status to {status_input.value}")
                property_data["status"] = status_input
            else:
                raise ValueError(f"Invalid status type")

            db_property = StayProperty(**property_data)
            self.db.add(db_property)
            self.db.flush()

            # Step 2: Create amenity mappings
            for amenity_data in data.get("amenities", []):
                amenity = self._get_or_create_amenity(amenity_data)
                self.db.add(
                    StayPropertyAmenityMap(
                        property_id=db_property.id,
                        amenity_id=amenity.id,
                        value=self._wrap_amenity_value(amenity_data.get("value")),
                    )
                )

            # Step 3: Create room types and units
            for room_type_data in data.get("room_types", []):
                count = room_type_data.pop("count", 1)
                room_units = room_type_data.pop("room_units", None)
                unit_prefix = room_type_data.pop("unit_prefix", None)
                floor = room_type_data.pop("floor", None)
                metadata = room_type_data.pop("metadata", {}) or {}
                for metadata_field in ("smoking", "guest_access"):
                    value = room_type_data.pop(metadata_field, None)
                    if value is not None:
                        metadata[metadata_field] = value
                if room_type_data.get("max_guests") is not None:
                    room_type_data["max_guests"] = str(room_type_data["max_guests"])
                room_type_data["property_id"] = db_property.id
                room_type_data["metadata_json"] = metadata

                room_type = StayRoomType(**room_type_data)
                self.db.add(room_type)
                self.db.flush()

                unit_numbers = room_units or self._generate_room_numbers(room_type.name, unit_prefix, count)
                for unit_number in unit_numbers:
                    self.db.add(
                        StayRoomUnit(
                            property_id=db_property.id,
                            room_type_id=room_type.id,
                            room_number=unit_number,
                            floor=floor,
                            status="available",
                        )
                    )

            # Commit all changes
            self.db.commit()
            return self.get_for_vendor(vendor_id, db_property.id)
        
        except Exception as e:
            # Transaction safety: rollback everything
            self.db.rollback()
            raise e

    def update_for_vendor(self, vendor_id: UUID, property_id: UUID, payload: StayPropertyCreate) -> StayProperty | None:
        """Update an existing stay property for a vendor"""
        # First verify ownership and get existing property
        existing_property = self.get_for_vendor(vendor_id, property_id)
        if not existing_property:
            return None

        data = payload.model_dump(by_alias=False)
        
        # Update main property fields
        property_data = {
            key: value
            for key, value in data.items()
            if key not in {"amenities", "room_types", "metadata"}
        }
        property_data["metadata_json"] = data.get("metadata") or {}
        property_data["media"] = self._normalize_media_payload(
            property_data.get("media") or [],
            vendor_id=vendor_id,
        )

        # Validate and normalize status
        status_input = property_data.get("status", "SUBMITTED")
        if isinstance(status_input, str):
            status_upper = status_input.upper()
            if status_upper == "DRAFT":
                normalized_status = StayStatus.DRAFT
            elif status_upper == "SUBMITTED":
                normalized_status = StayStatus.SUBMITTED
            elif status_upper in ["APPROVED", "REJECTED", "ARCHIVED"]:
                raise ValueError(f"Vendors are not allowed to set status to {status_upper}")
            else:
                raise ValueError(f"Invalid status: {status_input}")
        elif isinstance(status_input, StayStatus):
            if status_input in [StayStatus.APPROVED, StayStatus.REJECTED, StayStatus.ARCHIVED]:
                raise ValueError(f"Vendors are not allowed to set status to {status_input.value}")
            normalized_status = status_input
        else:
            raise ValueError(f"Invalid status type")

        if existing_property.status in [StayStatus.APPROVED, StayStatus.REJECTED, StayStatus.ARCHIVED]:
            if normalized_status != existing_property.status:
                raise ValueError(f"Cannot change status of a stay that is already {existing_property.status.value}")

        property_data["status"] = normalized_status
        # Ensure we do not overwrite listing_id from payload (keep existing listing_id)
        if "listing_id" in property_data:
            del property_data["listing_id"]

        # Update the main property record
        for key, value in property_data.items():
            if hasattr(existing_property, key):
                setattr(existing_property, key, value)

        # Replace amenity mappings - delete old ones first
        self.db.query(StayPropertyAmenityMap).filter(
            StayPropertyAmenityMap.property_id == property_id
        ).delete()
        self.db.flush()

        # Add new amenity mappings
        for amenity_data in data.get("amenities", []):
            amenity = self._get_or_create_amenity(amenity_data)
            self.db.add(
                StayPropertyAmenityMap(
                    property_id=property_id,
                    amenity_id=amenity.id,
                    value=self._wrap_amenity_value(amenity_data.get("value")),
                )
            )

        # Check if Stay is linked to marketplace before allowing destructive room updates
        if existing_property.listing_id is not None:
            # Property is linked to marketplace - block destructive room updates
            new_room_types = data.get("room_types", [])
            if new_room_types:
                raise ValueError(
                    "Room configuration cannot be replaced after listing is linked/published. "
                    "Use room inventory management instead."
                )
        else:
            # Safe to replace room types and room units for unlinked draft stays
            self.db.query(StayRoomUnit).filter(StayRoomUnit.property_id == property_id).delete()
            self.db.query(StayRoomType).filter(StayRoomType.property_id == property_id).delete()
            self.db.flush()

        # Add new room types and room units (only for unlinked stays)
        for room_type_data in data.get("room_types", []):
            count = room_type_data.pop("count", 1)
            room_units = room_type_data.pop("room_units", None)
            unit_prefix = room_type_data.pop("unit_prefix", None)
            floor = room_type_data.pop("floor", None)
            metadata = room_type_data.pop("metadata", {}) or {}
            for metadata_field in ("smoking", "guest_access"):
                value = room_type_data.pop(metadata_field, None)
                if value is not None:
                    metadata[metadata_field] = value
            if room_type_data.get("max_guests") is not None:
                room_type_data["max_guests"] = str(room_type_data["max_guests"])
            room_type_data["property_id"] = property_id
            room_type_data["metadata_json"] = metadata

            room_type = StayRoomType(**room_type_data)
            self.db.add(room_type)
            self.db.flush()

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

        self.db.commit()
        return self.get_for_vendor(vendor_id, property_id)

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

    def _create_listing_for_stay(self, vendor_id: UUID, payload: StayPropertyCreate) -> Listing:
        """Create a Listing record for the Stay property"""
        # Resolve or create destination
        destination = self._get_or_create_destination(payload)

        # Determine currency (use LKR as default for stays)
        currency = CurrencyCode.LKR
        if hasattr(payload, 'room_types') and payload.room_types:
            first_room = payload.room_types[0]
            if hasattr(first_room, 'currency') and first_room.currency:
                try:
                    currency = CurrencyCode(first_room.currency.upper())
                except ValueError:
                    currency = CurrencyCode.LKR

        # Use ORM to create the listing so SQLAlchemy handles enum serialisation
        listing = Listing(
            destination_id=destination.id,
            vendor_id=vendor_id,
            listing_type=ListingType.HOTEL,
            title=payload.name,
            description=payload.description,
            latitude=float(payload.latitude) if payload.latitude else None,
            longitude=float(payload.longitude) if payload.longitude else None,
            # ListingStatus.SUBMITTED maps to 'SUBMITTED' in the DB enum
            status=ListingStatus.SUBMITTED,
            base_currency=currency,
            is_active=True,
        )
        self.db.add(listing)
        self.db.flush()  # Assigns listing.id without committing
        return listing

    def archive_for_vendor(self, vendor_id: UUID, property_id: UUID, reason: str = None) -> StayProperty | None:
        """Archive (soft delete) a stay property for a vendor"""
        # First verify ownership and get existing property
        existing_property = self.get_for_vendor(vendor_id, property_id)
        if not existing_property:
            return None
        
        # Check if property can be archived
        if existing_property.status == StayStatus.ARCHIVED:
            raise ValueError("Stay property is already archived")
        
        # Perform soft delete
        existing_property.status = StayStatus.ARCHIVED
        existing_property.is_active = False
        existing_property.archived_at = self.db.execute("SELECT NOW()").scalar()
        existing_property.archived_by_id = vendor_id
        if reason:
            # Store archive reason in metadata if column doesn't exist
            metadata = existing_property.metadata_json or {}
            metadata['archive_reason'] = reason
            existing_property.metadata_json = metadata
        
        self.db.commit()
        return existing_property

    def delete_for_vendor(self, vendor_id: UUID, property_id: UUID) -> StayProperty | None:
        """Delete a stay property for a vendor (hard delete - use with caution)"""
        # First verify ownership and get existing property
        existing_property = self.get_for_vendor(vendor_id, property_id)
        if not existing_property:
            return None
        
        # Only allow hard delete for DRAFT status
        if existing_property.status != StayStatus.DRAFT:
            raise ValueError("Only DRAFT stay properties can be permanently deleted")
        
        try:
            # Delete related records first
            self.db.query(StayRoomUnit).filter(StayRoomUnit.property_id == property_id).delete()
            self.db.query(StayRoomType).filter(StayRoomType.property_id == property_id).delete()
            self.db.query(StayPropertyAmenityMap).filter(StayPropertyAmenityMap.property_id == property_id).delete()
            
            # Delete the main property
            self.db.delete(existing_property)
            self.db.commit()
            return existing_property
        except Exception as e:
            self.db.rollback()
            raise e

    def _get_or_create_destination(self, payload: StayPropertyCreate) -> Destination:
        """Get or create destination from stay payload"""
        # Use city as destination name, fallback to district or address
        destination_name = payload.city or payload.district or payload.address
        
        if not destination_name:
            # Default destination if none provided
            destination_name = "Sri Lanka"
        
        # Try to find existing destination
        destination = (
            self.db.query(Destination)
            .filter(Destination.name == destination_name)
            .first()
        )
        
        if not destination:
            # Create new destination
            destination = Destination(
                name=destination_name,
                destination_type=DestinationType.CITY,  # Default type
            )
            self.db.add(destination)
            self.db.flush()  # Get destination ID
        
        return destination
