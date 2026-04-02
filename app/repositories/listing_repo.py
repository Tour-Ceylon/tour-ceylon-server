from typing import Optional
from uuid import UUID

from sqlalchemy import and_, func
from sqlalchemy.orm import Session, joinedload

from app.models.destination import Destination
from app.models.enum import CurrencyCode, ListingType
from app.models.hotelDetail import HotelDetail
from app.models.listing import Listing
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
    }
    DETAIL_FIELDS = {"hotel_detail", "tour_detail", "safari_detail", "transfer_detail"}
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

    def __init__(self, db: Session):
        self.db = db

    def _base_query(self):
        return self.db.query(Listing).options(
            joinedload(Listing.destination),
            joinedload(Listing.hotel_detail),
            joinedload(Listing.tour_detail),
            joinedload(Listing.safari_detail),
            joinedload(Listing.transfer_detail),
        )

    def create(self, listing_data: ListingCreate) -> Listing:
        payload = listing_data.model_dump()
        base_data = {key: value for key, value in payload.items() if key in self.BASE_FIELDS}
        db_listing = Listing(**base_data)
        self.db.add(db_listing)
        self.db.flush()

        self._sync_detail(db_listing, db_listing.listing_type, payload)

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

        if search_params.title:
            filters.append(Listing.title.ilike(f"%{search_params.title}%"))

        if search_params.base_currency:
            filters.append(Listing.base_currency == search_params.base_currency)

        if search_params.status:
            filters.append(Listing.status == search_params.status)

        if search_params.is_active is not None:
            filters.append(Listing.is_active == search_params.is_active)

        if filters:
            query = query.filter(and_(*filters))

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

        previous_type = db_listing.listing_type
        for field, value in base_update_data.items():
            setattr(db_listing, field, value)

        active_type = db_listing.listing_type
        if previous_type != active_type:
            self._clear_detail_for_type(db_listing, previous_type)

        if detail_data or previous_type != active_type:
            self._sync_detail(db_listing, active_type, update_data)

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
        return self._base_query().filter(Listing.listing_type == listing_type).all()

    def get_active(self) -> list[Listing]:
        return self._base_query().filter(Listing.is_active.is_(True)).all()

    def get_inactive(self) -> list[Listing]:
        return self._base_query().filter(Listing.is_active.is_(False)).all()

    def get_by_location_city(self, city: str) -> list[Listing]:
        return (
            self._base_query()
            .join(Listing.destination)
            .filter(Destination.name.ilike(f"%{city}%"))
            .all()
        )

    def get_by_location_district(self, district: str) -> list[Listing]:
        return (
            self._base_query()
            .join(Listing.destination)
            .filter(Destination.name.ilike(f"%{district}%"))
            .all()
        )

    def get_by_currency(self, currency: CurrencyCode) -> list[Listing]:
        return self._base_query().filter(Listing.base_currency == currency).all()

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


def get_listing_repository(db: Session = None) -> ListingRepository:
    if db is None:
        from app.config.database import SessionLocal

        db = SessionLocal()
    return ListingRepository(db)
