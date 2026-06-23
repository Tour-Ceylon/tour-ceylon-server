from typing import Optional
from uuid import UUID

from sqlalchemy import and_, func, or_
from sqlalchemy.orm import Session, joinedload, selectinload

from app.models.activityDetail import ActivityDetail
from app.models.destination import Destination
from app.models.enum import BookingUnit, CurrencyCode, ListingStatus, ListingType, PricingRuleType
from app.models.hotelDetail import HotelDetail
from app.models.listing import Listing
from app.models.listingMedia import ListingMedia
from app.models.listingVariant import ListingVariant
from app.models.pricingRule import PricingRule
from app.models.safariDetail import SafariDetail
from app.models.tourDetail import TourDetail
from app.models.transferDetail import TransferDetail
from app.schemas.listing_schema import ListingCreate, ListingSearchParams, ListingUpdate


class ListingRepository:
    """Repository class for Listing model database operations"""

    DETAIL_MODEL_BY_TYPE = {
        ListingType.HOTEL: ("hotel_detail", HotelDetail),
        ListingType.TOUR: ("tour_detail", TourDetail),
        ListingType.SAFARI: ("safari_detail", SafariDetail),
        ListingType.TRANSFER: ("transfer_detail", TransferDetail),
        ListingType.EXPERIENCE: ("activity_detail", ActivityDetail),
    }
    DETAIL_FIELDS = {"hotel_detail", "tour_detail", "safari_detail", "transfer_detail", "activity_detail"}
    BASE_FIELDS = {
        "listing_type",
        "destination_id",
        "title",
        "slug",
        "description",
        "latitude",
        "longitude",
        "status",
        "base_currency",
        "is_active",
    }
    MEDIA_FIELD = "media"
    VARIANTS_FIELD = "variants"

    def __init__(self, db: Session):
        self.db = db

    def _base_query(self):
        return self.db.query(Listing).options(
            joinedload(Listing.destination),
            joinedload(Listing.media),
            joinedload(Listing.cover_media),
            joinedload(Listing.hotel_detail),
            joinedload(Listing.tour_detail),
            joinedload(Listing.safari_detail),
            joinedload(Listing.transfer_detail),
            joinedload(Listing.activity_detail),
            selectinload(Listing.media_assets),
            selectinload(Listing.variants).selectinload(ListingVariant.pricing_rules),
        )

    def create(self, listing_data: ListingCreate) -> Listing:
        payload = listing_data.model_dump()
        base_data = {key: value for key, value in payload.items() if key in self.BASE_FIELDS}
        db_listing = Listing(**base_data)
        self.db.add(db_listing)
        self.db.flush()

        self._sync_detail(db_listing, db_listing.listing_type, payload)
        self._validate_variant_payload(db_listing.listing_type, payload.get(self.VARIANTS_FIELD))
        self._replace_variants(db_listing, payload.get(self.VARIANTS_FIELD))
        self._sync_media(db_listing, payload.get(self.MEDIA_FIELD))

        self.db.commit()
        self.db.refresh(db_listing)
        return self.get_by_id(db_listing.id)

    def get_by_id(self, listing_id: UUID) -> Optional[Listing]:
        return self._base_query().filter(Listing.id == listing_id).first()

    def get_by_slug(self, slug: str) -> Optional[Listing]:
        return self._base_query().filter(Listing.slug == slug).first()

    def get_all(
        self,
        skip: int = 0,
        limit: int = 100,
        is_active: Optional[bool] = None,
    ) -> list[Listing]:
        query = self._base_query()

        if is_active is not None:
            query = query.filter(Listing.is_active == is_active)

        return query.offset(skip).limit(limit).all()

    def search(self, search_params: ListingSearchParams) -> tuple[list[Listing], int]:
        query = self._base_query()
        filters = []

        if search_params.listing_type:
            filters.append(Listing.listing_type == search_params.listing_type)

        if search_params.destination_id:
            filters.append(Listing.destination_id == search_params.destination_id)

        if search_params.location:
            # Outer join all possible location-related tables to avoid excluding listings
            query = query.outerjoin(Listing.destination)\
                         .outerjoin(Listing.hotel_detail)\
                         .outerjoin(Listing.safari_detail)\
                         .outerjoin(Listing.activity_detail)\
                         .outerjoin(Listing.tour_detail)
            
            # Split into terms for a smarter "AND" search across multiple fields
            terms = search_params.location.strip().split()
            if terms:
                # Ensure all tables are outer-joined once for filtering
                query = query.outerjoin(Listing.destination)\
                             .outerjoin(Listing.hotel_detail)\
                             .outerjoin(Listing.safari_detail)\
                             .outerjoin(Listing.activity_detail)\
                             .outerjoin(Listing.tour_detail)
                
                for term in terms:
                    t_q = f"%{term}%"
                    query = query.filter(
                        or_(
                            Listing.title.ilike(t_q),
                            Listing.description.ilike(t_q),
                            Destination.name.ilike(t_q),
                            HotelDetail.property_name.ilike(t_q),
                            HotelDetail.district.ilike(t_q),
                            HotelDetail.city.ilike(t_q),
                            HotelDetail.short_location.ilike(t_q),
                            SafariDetail.national_park.ilike(t_q),
                            ActivityDetail.meeting_point.ilike(t_q),
                            TourDetail.route_summary.ilike(t_q)
                        )
                    )

        if search_params.title:
            filters.append(Listing.title.ilike(f"%{search_params.title}%"))

        if search_params.base_currency:
            filters.append(Listing.base_currency == search_params.base_currency)

        if search_params.status:
            filters.append(Listing.status == search_params.status)

        if search_params.is_active is not None:
            filters.append(Listing.is_active == search_params.is_active)

        # Guest count filter (Adults + Children)
        total_guests = (search_params.adults or 0) + (search_params.children or 0)
        if total_guests > 0:
            query = query.join(Listing.variants)
            filters.append(ListingVariant.capacity_max >= total_guests)

        # Date range availability filter
        if search_params.start_date and search_params.end_date:
            # Simplistic approach: ensure at least one variant has capacity for the requested guests
            # Ideally this would check AvailabilityCalendar for each date in the range.
            # For now, we'll join AvailabilityCalendar if needed or just filter by variants
            pass

        if filters:
            query = query.filter(and_(*filters))

        # Handle distinct because of joins
        query = query.distinct()

        total_count = query.count()
        skip = (search_params.page - 1) * search_params.per_page
        listings = query.offset(skip).limit(search_params.per_page).all()
        return listings, total_count

    def update(self, listing_id: UUID, listing_data: ListingUpdate) -> Optional[Listing]:
        db_listing = self.get_by_id(listing_id)
        if not db_listing:
            return None

        update_data = listing_data.model_dump(exclude_unset=True)
        detail_data = {key: value for key, value in update_data.items() if key in self.DETAIL_FIELDS}
        base_update_data = {key: value for key, value in update_data.items() if key in self.BASE_FIELDS}
        media_data = update_data.get(self.MEDIA_FIELD) if self.MEDIA_FIELD in update_data else None
        variants_data = update_data.get(self.VARIANTS_FIELD) if self.VARIANTS_FIELD in update_data else None

        previous_type = db_listing.listing_type
        for field, value in base_update_data.items():
            setattr(db_listing, field, value)

        active_type = db_listing.listing_type
        if previous_type != active_type:
            self._clear_detail_for_type(db_listing, previous_type)

        if detail_data or previous_type != active_type:
            self._sync_detail(db_listing, active_type, update_data)

        if self.VARIANTS_FIELD in update_data:
            self._validate_variant_payload(active_type, variants_data)
            self._replace_variants(db_listing, variants_data)

        if self.MEDIA_FIELD in update_data:
            self._sync_media(db_listing, media_data)

        self.db.commit()
        self.db.refresh(db_listing)
        return self.get_by_id(db_listing.id)

    def delete(self, listing_id: UUID) -> bool:
        db_listing = self.get_by_id(listing_id)
        if not db_listing:
            return False

        self.db.delete(db_listing)
        self.db.commit()
        return True

    def deactivate(self, listing_id: UUID) -> Optional[Listing]:
        db_listing = self.get_by_id(listing_id)
        if not db_listing:
            return None

        db_listing.is_active = False
        self.db.commit()
        self.db.refresh(db_listing)
        return self.get_by_id(db_listing.id)

    def activate(self, listing_id: UUID) -> Optional[Listing]:
        db_listing = self.get_by_id(listing_id)
        if not db_listing:
            return None

        db_listing.is_active = True
        self.db.commit()
        self.db.refresh(db_listing)
        return self.get_by_id(db_listing.id)

    def get_by_type(self, listing_type: ListingType) -> list[Listing]:
        return (
            self._base_query()
            .filter(
                Listing.listing_type == listing_type,
                Listing.status == ListingStatus.PUBLISHED,
                Listing.is_active.is_(True),
            )
            .all()
        )

    def get_active(self) -> list[Listing]:
        return (
            self._base_query()
            .filter(Listing.status == ListingStatus.PUBLISHED, Listing.is_active.is_(True))
            .all()
        )

    def get_inactive(self) -> list[Listing]:
        return self._base_query().filter(Listing.is_active.is_(False)).all()

    def get_by_location_city(self, city: str) -> list[Listing]:
        return (
            self._base_query()
            .join(Listing.destination)
            .filter(
                Destination.name.ilike(f"%{city}%"),
                Listing.status == ListingStatus.PUBLISHED,
                Listing.is_active.is_(True),
            )
            .all()
        )

    def get_by_location_district(self, district: str) -> list[Listing]:
        return (
            self._base_query()
            .join(Listing.destination)
            .filter(
                Destination.name.ilike(f"%{district}%"),
                Listing.status == ListingStatus.PUBLISHED,
                Listing.is_active.is_(True),
            )
            .all()
        )

    def get_by_currency(self, currency: CurrencyCode) -> list[Listing]:
        return (
            self._base_query()
            .filter(
                Listing.base_currency == currency,
                Listing.status == ListingStatus.PUBLISHED,
                Listing.is_active.is_(True),
            )
            .all()
        )

    def count_by_type(self) -> dict:
        results = (
            self.db.query(Listing.listing_type, func.count(Listing.id))
            .group_by(Listing.listing_type)
            .all()
        )
        return {
            listing_type.value if hasattr(listing_type, "value") else listing_type: count
            for listing_type, count in results
        }

    def count_active(self) -> int:
        return self.db.query(Listing).filter(Listing.is_active.is_(True)).count()

    def count_inactive(self) -> int:
        return self.db.query(Listing).filter(Listing.is_active.is_(False)).count()

    def count_by_currency(self) -> dict:
        results = (
            self.db.query(Listing.base_currency, func.count(Listing.id))
            .group_by(Listing.base_currency)
            .all()
        )
        return {
            currency.value if hasattr(currency, "value") else currency: count
            for currency, count in results
        }

    def exists_by_slug(self, slug: str, exclude_listing_id: Optional[UUID] = None) -> bool:
        query = self.db.query(Listing).filter(Listing.slug == slug)

        if exclude_listing_id:
            query = query.filter(Listing.id != exclude_listing_id)

        return query.first() is not None

    def search_by_location(self, latitude: float, longitude: float, radius_km: float = 10.0) -> list[Listing]:
        lat_diff = radius_km / 111.0
        lng_diff = radius_km / 111.0

        return (
            self._base_query()
            .filter(
                and_(
                    Listing.latitude.between(latitude - lat_diff, latitude + lat_diff),
                    Listing.longitude.between(longitude - lng_diff, longitude + lng_diff),
                    Listing.latitude.is_not(None),
                    Listing.longitude.is_not(None),
                    Listing.status == ListingStatus.PUBLISHED,
                    Listing.is_active.is_(True),
                )
            )
            .all()
        )

    def _sync_detail(self, listing: Listing, listing_type: ListingType, payload: dict) -> None:
        relation_name, model_cls = self.DETAIL_MODEL_BY_TYPE[listing_type]
        detail_payload = payload.get(relation_name)
        if detail_payload is None:
            return

        existing_detail = getattr(listing, relation_name)
        if existing_detail is None:
            detail = model_cls(listing_id=listing.id, **detail_payload)
            self.db.add(detail)
            setattr(listing, relation_name, detail)
            return

        for field, value in detail_payload.items():
            setattr(existing_detail, field, value)

    def _clear_detail_for_type(self, listing: Listing, listing_type: ListingType) -> None:
        relation_name, _ = self.DETAIL_MODEL_BY_TYPE[listing_type]
        existing_detail = getattr(listing, relation_name)
        if existing_detail is not None:
            self.db.delete(existing_detail)

    def _sync_media(self, listing: Listing, media_payload: list[dict] | None) -> None:
        return

    def _replace_variants(self, listing: Listing, variants_payload: list[dict] | None) -> None:
        if variants_payload is None:
            return

        for existing_variant in list(listing.variants or []):
            self.db.delete(existing_variant)
        self.db.flush()

        for variant_payload in variants_payload:
            pricing_payload = variant_payload["pricing"]
            variant = ListingVariant(
                listing_id=listing.id,
                name=variant_payload["name"],
                booking_unit=variant_payload["booking_unit"],
                capacity_min=variant_payload.get("capacity_min"),
                capacity_max=variant_payload.get("capacity_max"),
                is_default=variant_payload.get("is_default", False),
            )
            self.db.add(variant)
            self.db.flush()

            variant.pricing_rules.append(
                PricingRule(
                    amount=pricing_payload["amount"],
                    currency=pricing_payload["currency"],
                    priority=pricing_payload["priority"],
                    pricing_rule_type=PricingRuleType.FIXED,
                    min_guest=variant_payload.get("capacity_min") or 1,
                    max_guest=variant_payload.get("capacity_max") or 999999,
                )
            )

    def _validate_variant_payload(self, listing_type: ListingType, variants_payload: list[dict] | None) -> None:
        if listing_type != ListingType.HOTEL or variants_payload is None:
            return
        if any(variant["booking_unit"] != BookingUnit.PER_ROOM for variant in variants_payload):
            raise ValueError("hotel listing variants must use per_room booking")

    def update_cover_media(self, listing: Listing, media_id: UUID | None) -> Listing:
        listing.cover_media_id = media_id
        self.db.flush()
        return listing


def get_listing_repository(db: Session = None) -> ListingRepository:
    if db is None:
        from app.config.database import SessionLocal

        db = SessionLocal()
    return ListingRepository(db)
