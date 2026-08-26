import base64
import binascii
import re
from uuid import UUID

from sqlalchemy import func, or_
from sqlalchemy.orm import Session, joinedload

from app.integrations.cloudinary import upload_image
from app.models.destination import Destination
from app.models.enum import (
    BookingUnit,
    CurrencyCode,
    DestinationType,
    ListingStatus,
    ListingType,
    MediaAssetStatus,
    MediaOwnerType,
    PricingRuleType,
    PropertyType,
)
from app.models.hotelDetail import HotelDetail
from app.models.listing import Listing
from app.models.listingVariant import ListingVariant
from app.models.media import MediaAsset
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
        data = payload.model_dump(by_alias=False)
        property_data = self._property_model_data(data, vendor_id)

        try:
            temp_property = StayProperty(**property_data)
            destination = self._get_or_create_destination(temp_property)

            listing = Listing(
                destination_id=destination.id,
                listing_type=ListingType.HOTEL,
                title=temp_property.name,
                vendor_id=vendor_id,
                status=ListingStatus.SUBMITTED
            )
            self.db.add(listing)
            self.db.flush()

            property_data["listing_id"] = listing.id
            db_property = StayProperty(**property_data)
            self.db.add(db_property)
            self.db.flush()

            self._replace_children(db_property, data)

            self._ensure_listing_projection(db_property)
            assert db_property.listing_id is not None, "stay_property.listing_id should not be None"
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise
        return self.get_for_vendor(vendor_id, db_property.id)

    def update_property(
        self, property_id: UUID, payload: StayPropertyCreate, user_id: UUID, is_admin: bool = False
    ) -> StayProperty | None:
        if is_admin:
            db_property = self.get_by_id(property_id)
            if db_property is None:
                from app.models.listing import Listing
                listing = self.db.query(Listing).filter(Listing.id == property_id).first()
                if listing:
                    db_property = self.create_from_listing(listing.vendor_id, property_id)
        else:
            db_property = self.get_for_vendor(user_id, property_id)
            if db_property is None:
                db_property = self.create_from_listing(user_id, property_id)

        if db_property is None:
            return None

        try:
            data = payload.model_dump(by_alias=False)
            target_vendor_id = db_property.vendor_id

            previous_status = str(db_property.status or "").lower()
            incoming_status = str(data.get("status") or "").lower()

            # Status preservation rule:
            # If the property was already approved/published, keep it approved/published unless explicitly set to 'draft'.
            # Admin updates for active listings also ensure approved status.
            if previous_status in {"approved", "published"} and incoming_status != "draft":
                data["status"] = previous_status
            elif is_admin and incoming_status in {"submitted", "approved", "published"}:
                data["status"] = "approved"

            for key, value in self._property_model_data(data, target_vendor_id).items():
                if key == "vendor_id":
                    continue
                setattr(db_property, key, value)

            self._replace_children(db_property, data)
            self._ensure_listing_projection(db_property)
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise
        return self.get_by_id(db_property.id)

    def update_for_vendor(self, vendor_id: UUID, property_id: UUID, payload: StayPropertyCreate) -> StayProperty | None:
        return self.update_property(property_id, payload, user_id=vendor_id, is_admin=False)

    def list_for_vendor(self, vendor_id: UUID) -> list[StayProperty]:
        properties = (
            self._base_query()
            .filter(StayProperty.vendor_id == vendor_id)
            .order_by(StayProperty.created_at.desc())
            .all()
        )
        self._ensure_listing_projection_for_many(properties)
        return properties

    def list_all(self) -> list[StayProperty]:
        properties = self._base_query().order_by(StayProperty.created_at.desc()).all()
        self._ensure_listing_projection_for_many(properties)
        return properties

    def get_for_vendor(self, vendor_id: UUID, property_id: UUID) -> StayProperty | None:
        property_record = (
            self._base_query()
            .filter(
                StayProperty.vendor_id == vendor_id,
                or_(StayProperty.id == property_id, StayProperty.listing_id == property_id),
            )
            .first()
        )
        if property_record is not None:
            self._ensure_listing_projection(property_record)
            self.db.commit()
        return property_record

    def get_by_id(self, property_id: UUID) -> StayProperty | None:
        property_record = (
            self._base_query()
            .filter(or_(StayProperty.id == property_id, StayProperty.listing_id == property_id))
            .first()
        )
        if property_record is None:
            from app.models.listing import Listing
            listing = self.db.query(Listing).filter(Listing.id == property_id).first()
            if listing:
                property_record = self.create_from_listing(listing.vendor_id, property_id)
        if property_record is not None:
            self._ensure_listing_projection(property_record)
            self.db.commit()
        return property_record

    def create_from_listing(self, vendor_id: UUID, listing_id: UUID) -> StayProperty | None:
        existing = self.get_by_id(listing_id)
        if existing is not None:
            return existing

        listing = (
            self.db.query(Listing)
            .options(
                joinedload(Listing.hotel_detail),
                joinedload(Listing.destination),
                joinedload(Listing.variants).joinedload(ListingVariant.pricing_rules),
                joinedload(Listing.media_assets),
            )
            .filter(
                Listing.id == listing_id,
                Listing.listing_type == ListingType.HOTEL,
                Listing.vendor_id == vendor_id,
            )
            .first()
        )
        if listing is None:
            return None

        detail = listing.hotel_detail
        property_record = StayProperty(
            vendor_id=vendor_id,
            listing_id=listing.id,
            name=detail.property_name if detail and detail.property_name else listing.title,
            property_type=self._property_type_value(detail.property_type if detail else None),
            description=listing.description,
            address=detail.address_line_1 if detail else None,
            city=(detail.city if detail else None) or (listing.destination.name if listing.destination else None),
            district=detail.district if detail else None,
            latitude=listing.latitude,
            longitude=listing.longitude,
            status="published" if listing.is_active else "draft",
            contact={
                "phone": detail.contact_phone if detail else None,
                "email": detail.contact_email if detail else None,
                "languages": self._normalize_list(detail.languages_spoken if detail else []),
            },
            policies={
                "checkInTime": detail.check_in_time.isoformat() if detail and detail.check_in_time else None,
                "checkOutTime": detail.check_out_time.isoformat() if detail and detail.check_out_time else None,
                "breakfastIncluded": bool(self._normalize_list(detail.meal_plans if detail else [])),
                "parking": bool(detail.parking_available) if detail else False,
                "ratePlans": {
                    "standardCancellationPolicy": detail.cancellation_policy if detail else None,
                    "childPolicy": detail.child_policy if detail else None,
                },
            },
            media=[
                {
                    "url": media.secure_url,
                    "role": "cover" if media.is_primary else "gallery",
                    "sortOrder": media.sort_order,
                }
                for media in (listing.media_assets or [])
            ],
            metadata_json={"source": "listing_backfill", "enhancedData": None},
        )
        self.db.add(property_record)
        self.db.flush()

        for amenity_name in self._normalize_list(detail.amenities if detail else []):
            amenity = self._get_or_create_amenity(
                {"name": amenity_name, "value": True, "category": "property", "value_type": "boolean"}
            )
            self.db.add(
                StayPropertyAmenityMap(
                    property_id=property_record.id,
                    amenity_id=amenity.id,
                    value={"value": True},
                )
            )

        variants = list(listing.variants or [])
        if not variants:
            variants = [None]
        for index, variant in enumerate(variants):
            pricing = variant.pricing if variant is not None else None
            room_type = StayRoomType(
                property_id=property_record.id,
                name=variant.name if variant is not None else "Standard Room",
                max_guests=str(variant.capacity_max) if variant is not None and variant.capacity_max else None,
                base_price=pricing["amount"] if pricing else None,
                currency=self._currency_value(pricing["currency"] if pricing else listing.base_currency),
                bed_configuration={"hasBeds": False, "beds": 0, "cribs": 0, "breakdown": {}},
                bathroom={},
                discounts=[],
                metadata_json={"sourceVariantId": str(variant.id)} if variant is not None else {},
            )
            self.db.add(room_type)
            self.db.flush()
            self.db.add(
                StayRoomUnit(
                    property_id=property_record.id,
                    room_type_id=room_type.id,
                    room_number=f"RM-{index + 1:03d}",
                    status="available",
                )
            )

        self.db.commit()
        return self.get_by_id(property_record.id)

    def _ensure_listing_projection_for_many(self, properties: list[StayProperty]) -> None:
        changed = False
        for property_record in properties:
            changed = self._ensure_listing_projection(property_record) or changed
        if changed:
            self.db.commit()

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
    def _generate_room_numbers(name: str, prefix: str | None, count: int, used_numbers: set[str]) -> list[str]:
        safe_prefix = prefix or "".join(part[:1] for part in name.split() if part).upper() or "RM"
        generated: list[str] = []
        index = 1
        while len(generated) < count:
            candidate = f"{safe_prefix}-{index:03d}"
            if candidate not in used_numbers:
                used_numbers.add(candidate)
                generated.append(candidate)
            index += 1
        return generated

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

    def _ensure_listing_projection(self, property_record: StayProperty) -> bool:
        destination = self._get_or_create_destination(property_record)
        first_room = self._first_room_type(property_record)
        base_currency = self._currency_from_room(first_room)
        listing = self.db.get(Listing, property_record.listing_id) if property_record.listing_id else None

        status_map = {
            "submitted": ListingStatus.SUBMITTED,
            "approved": ListingStatus.PUBLISHED,
            "published": ListingStatus.PUBLISHED,
            "rejected": ListingStatus.REJECTED,
            "archived": ListingStatus.ARCHIVED,
            "draft": ListingStatus.DRAFT,
        }
        mapped_status = status_map.get(property_record.status, ListingStatus.DRAFT)

        listing_payload = {
            "destination_id": destination.id,
            "listing_type": ListingType.HOTEL,
            "vendor_id": property_record.vendor_id,
            "title": property_record.name,
            "description": property_record.description,
            "latitude": float(property_record.latitude) if property_record.latitude is not None else None,
            "longitude": float(property_record.longitude) if property_record.longitude is not None else None,
            "status": mapped_status,
            "base_currency": base_currency,
            "is_active": mapped_status == ListingStatus.PUBLISHED,
        }
        if listing is None:
            listing = Listing(**listing_payload)
            self.db.add(listing)
            self.db.flush()
            property_record.listing_id = listing.id
        else:
            for key, value in listing_payload.items():
                setattr(listing, key, value)

        hotel_payload = self._hotel_detail_payload(property_record)
        if listing.hotel_detail is None:
            self.db.add(HotelDetail(listing_id=listing.id, **hotel_payload))
        else:
            for key, value in hotel_payload.items():
                setattr(listing.hotel_detail, key, value)
        self._create_listing_variants(listing, property_record)
        self._create_listing_media_assets(listing, property_record)
        return True

    def _property_model_data(self, data: dict, vendor_id: UUID) -> dict:
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
        return property_data

    def _replace_children(self, db_property: StayProperty, data: dict) -> None:
        # 1. Replace Amenities
        for amenity_map in list(db_property.amenities or []):
            self.db.delete(amenity_map)
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

        # 2. Upsert Room Types & Units (preserving IDs to protect room blocks and booking FK constraints)
        from collections import defaultdict
        existing_types_by_id = {rt.id: rt for rt in (db_property.room_types or [])}
        existing_types_by_name = {rt.name.strip().lower(): rt for rt in (db_property.room_types or [])}
        existing_units_by_type: dict[UUID, list[StayRoomUnit]] = defaultdict(list)
        for u in (db_property.room_units or []):
            existing_units_by_type[u.room_type_id].append(u)

        used_room_numbers: set[str] = {u.room_number for u in (db_property.room_units or [])}
        seen_room_names: dict[str, int] = {}
        processed_type_ids: set[UUID] = set()

        for raw_room_type_data in data.get("room_types", []):
            room_type_data = dict(raw_room_type_data)
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
            base_name = str(room_type_data.get("name") or "Room").strip() or "Room"
            room_type_data["name"] = base_name
            room_type_data["property_id"] = db_property.id
            room_type_data["metadata_json"] = metadata

            # Match existing room type by ID or Name
            raw_id = raw_room_type_data.get("id")
            room_type: StayRoomType | None = None
            if raw_id:
                try:
                    target_uuid = UUID(str(raw_id))
                    if target_uuid in existing_types_by_id:
                        room_type = existing_types_by_id[target_uuid]
                except (ValueError, TypeError):
                    pass

            if room_type is None and room_type_data["name"].strip().lower() in existing_types_by_name:
                room_type = existing_types_by_name[room_type_data["name"].strip().lower()]

            if room_type is not None:
                for k, v in room_type_data.items():
                    if k not in {"id", "property_id"}:
                        setattr(room_type, k, v)
                self.db.add(room_type)
            else:
                room_type = StayRoomType(**room_type_data)
                self.db.add(room_type)
                self.db.flush()

            processed_type_ids.add(room_type.id)

            # Manage Units for this Room Type
            current_units = existing_units_by_type.get(room_type.id, [])
            target_count = max(int(count or 1), 1)
            if len(current_units) < target_count:
                needed = target_count - len(current_units)
                if room_units and len(room_units) >= len(current_units) + needed:
                    unit_numbers = [u for u in room_units if u not in used_room_numbers][:needed]
                else:
                    unit_numbers = self._generate_room_numbers(room_type.name, unit_prefix, needed, used_room_numbers)

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
                    used_room_numbers.add(unit_number)
            elif len(current_units) > target_count:
                excess_count = len(current_units) - target_count
                units_to_remove = current_units[-excess_count:]
                for unit in units_to_remove:
                    used_room_numbers.discard(unit.room_number)
                    for block in list(unit.room_blocks or []):
                        self.db.delete(block)
                    self.db.delete(unit)

        # Delete room types removed by vendor
        for old_rt in list(db_property.room_types or []):
            if old_rt.id not in processed_type_ids:
                for unit in list(old_rt.room_units or []):
                    for block in list(unit.room_blocks or []):
                        self.db.delete(block)
                    self.db.delete(unit)
                self.db.delete(old_rt)
        self.db.flush()

    def _get_or_create_destination(self, property_record: StayProperty) -> Destination:
        destination_name = (
            property_record.city
            or property_record.district
            or property_record.address
            or "Sri Lanka"
        ).strip()
        existing = (
            self.db.query(Destination)
            .filter(func.lower(Destination.name) == destination_name.lower())
            .first()
        )
        if existing is not None:
            return existing

        destination = Destination(
            name=destination_name,
            destination_type=DestinationType.CITY,
            latitude=float(property_record.latitude) if property_record.latitude is not None else None,
            longitude=float(property_record.longitude) if property_record.longitude is not None else None,
        )
        self.db.add(destination)
        self.db.flush()
        return destination

    def _hotel_detail_payload(self, property_record: StayProperty) -> dict:
        policies = property_record.policies or {}
        amenities = [mapping.name for mapping in property_record.amenities or [] if mapping.name]
        room_types = list(property_record.room_types or [])
        room_count = sum(len(room_type.room_units or []) for room_type in room_types) or len(room_types) or 1
        max_guest_capacity = sum(self._safe_int(room_type.max_guests) or 0 for room_type in room_types) or None

        return {
            "property_type": self._map_property_type(property_record.property_type),
            "star_rating": self._safe_int((property_record.metadata_json or {}).get("starRating")) or 3,
            "check_in_time": self._parse_time_or_default(policies.get("checkInTime"), "14:00"),
            "check_out_time": self._parse_time_or_default(policies.get("checkOutTime"), "11:00"),
            "property_name": property_record.name,
            "short_location": property_record.city or property_record.district,
            "address_line_1": property_record.address,
            "city": property_record.city,
            "district": property_record.district,
            "contact_phone": (property_record.contact or {}).get("phone"),
            "contact_email": (property_record.contact or {}).get("email"),
            "amenities": amenities,
            "languages_spoken": (property_record.contact or {}).get("languages") or [],
            "room_count": room_count,
            "max_guest_capacity": max_guest_capacity,
            "meal_plans": ["breakfast"] if policies.get("breakfastIncluded") else [],
            "parking_available": bool(policies.get("parking")),
            "wifi_available": "WiFi" in amenities or "Wifi" in amenities or "Wi-Fi" in amenities,
            "child_policy": (policies.get("ratePlans") or {}).get("childPolicy"),
            "cancellation_policy": (policies.get("ratePlans") or {}).get("standardCancellationPolicy"),
            "smoking_policy": "See room details",
            "extra_bed_policy": None,
            "check_in_notes": None,
            "check_out_notes": None,
        }

    def _create_listing_variants(self, listing: Listing, property_record: StayProperty) -> None:
        for existing_variant in list(listing.variants or []):
            self.db.delete(existing_variant)
        self.db.flush()

        room_types = list(property_record.room_types or [])
        if not room_types:
            room_types = [
                StayRoomType(
                    name="Standard Room",
                    max_guests="2",
                    base_price=0,
                    currency=CurrencyCode.LKR.value,
                )
            ]

        for index, room_type in enumerate(room_types):
            amount = float(room_type.base_price or 0)
            currency = self._currency_from_room(room_type)
            capacity_max = self._safe_int(room_type.max_guests) or 2
            variant = ListingVariant(
                listing_id=listing.id,
                name=room_type.name,
                booking_unit=BookingUnit.PER_ROOM,
                capacity_min=1,
                capacity_max=capacity_max,
                is_default=index == 0,
            )
            self.db.add(variant)
            self.db.flush()
            variant.pricing_rules.append(
                PricingRule(
                    amount=amount,
                    currency=currency,
                    priority=index,
                    pricing_rule_type=PricingRuleType.FIXED,
                    min_guest=1,
                    max_guest=capacity_max,
                )
            )

    def _create_listing_media_assets(self, listing: Listing, property_record: StayProperty) -> None:
        projected_prefix = f"listing-projection/{listing.id}/"
        listing.cover_media_id = None
        for media in list(listing.media_assets or []):
            if (media.cloudinary_public_id or "").startswith(projected_prefix):
                self.db.delete(media)
        self.db.flush()

        for index, item in enumerate(property_record.media or []):
            public_id = item.get("cloudinaryPublicId") or item.get("cloudinary_public_id")
            url = item.get("url")
            if not public_id or not url:
                continue
            is_primary = item.get("role") == "cover" or index == 0
            media = MediaAsset(
                owner_type=MediaOwnerType.LISTING,
                owner_id=listing.id,
                cloudinary_public_id=f"listing-projection/{listing.id}/{public_id}",
                secure_url=url,
                resource_type=item.get("resourceType") or "image",
                format=item.get("format"),
                width=item.get("width"),
                height=item.get("height"),
                bytes=item.get("bytes"),
                alt_text=property_record.name,
                sort_order=int(item.get("sortOrder") or index),
                is_primary=is_primary,
                status=MediaAssetStatus.ACTIVE,
            )
            self.db.add(media)
            self.db.flush()
            if is_primary and listing.cover_media_id is None:
                listing.cover_media_id = media.id

    @staticmethod
    def _first_room_type(property_record: StayProperty) -> StayRoomType | None:
        room_types = list(property_record.room_types or [])
        return room_types[0] if room_types else None

    @staticmethod
    def _currency_from_room(room_type: StayRoomType | None) -> CurrencyCode:
        raw_currency = getattr(room_type, "currency", None) or CurrencyCode.LKR.value
        try:
            return CurrencyCode(raw_currency)
        except ValueError:
            return CurrencyCode.LKR

    @staticmethod
    def _map_property_type(raw_value: str | None) -> PropertyType:
        normalized = (raw_value or "hotel").strip().lower().replace("-", "_")
        aliases = {
            "bed_breakfast": PropertyType.GUEST_HOUSE,
            "bed_and_breakfast": PropertyType.GUEST_HOUSE,
            "guest_house": PropertyType.GUEST_HOUSE,
            "farm_stay": PropertyType.HOMESTAY,
            "glamping": PropertyType.RESORT,
            "campsite": PropertyType.HOSTEL,
        }
        if normalized in aliases:
            return aliases[normalized]
        try:
            return PropertyType(normalized)
        except ValueError:
            return PropertyType.HOTEL

    @staticmethod
    def _parse_time_or_default(raw_value, default_value: str):
        from datetime import time

        if isinstance(raw_value, time):
            return raw_value
        if isinstance(raw_value, str) and raw_value.strip():
            try:
                return time.fromisoformat(raw_value.strip())
            except ValueError:
                pass
        return time.fromisoformat(default_value)

    @staticmethod
    def _safe_int(raw_value) -> int | None:
        if raw_value is None:
            return None
        try:
            return int(raw_value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _property_type_value(raw_value) -> str:
        if raw_value is None:
            return PropertyType.HOTEL.value
        return raw_value.value if hasattr(raw_value, "value") else str(raw_value)

    @staticmethod
    def _currency_value(raw_value) -> str:
        if raw_value is None:
            return CurrencyCode.LKR.value
        return raw_value.value if hasattr(raw_value, "value") else str(raw_value)

    @staticmethod
    def _normalize_list(raw_value) -> list:
        if raw_value is None:
            return []
        if isinstance(raw_value, list):
            return raw_value
        if isinstance(raw_value, str):
            return [item.strip() for item in re.split(r"[,;\n]+", raw_value) if item.strip()]
        return [raw_value]
