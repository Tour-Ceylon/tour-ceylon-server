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
        data = payload.model_dump(by_alias=False)
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

        db_property = StayProperty(**property_data)
        self.db.add(db_property)
        self.db.flush()

        for amenity_data in data.get("amenities", []):
            amenity = self._get_or_create_amenity(amenity_data)
            self.db.add(
                StayPropertyAmenityMap(
                    property_id=db_property.id,
                    amenity_id=amenity.id,
                    value=self._wrap_amenity_value(amenity_data.get("value")),
                )
            )

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

        self.db.commit()
        return self.get_for_vendor(vendor_id, db_property.id)

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
