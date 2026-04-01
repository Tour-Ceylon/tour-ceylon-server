from typing import Optional
from uuid import UUID

from sqlalchemy import and_, func
from sqlalchemy.orm import Session, joinedload

from app.models.destination import Destination
from app.models.enum import CurrencyCode, ListingType
from app.models.listing import Listing
from app.schemas.listing_schema import ListingCreate, ListingSearchParams, ListingUpdate


class ListingRepository:
    """Repository class for Listing model database operations"""

    def __init__(self, db: Session):
        self.db = db

    def _base_query(self):
        return self.db.query(Listing).options(joinedload(Listing.destination))

    def create(self, listing_data: ListingCreate) -> Listing:
        db_listing = Listing(**listing_data.model_dump())
        self.db.add(db_listing)
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
        for field, value in update_data.items():
            setattr(db_listing, field, value)

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
        return {listing_type.value if hasattr(listing_type, "value") else listing_type: count for listing_type, count in results}

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
        return {currency.value if hasattr(currency, "value") else currency: count for currency, count in results}

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


def get_listing_repository(db: Session = None) -> ListingRepository:
    if db is None:
        from app.config.database import SessionLocal

        db = SessionLocal()
    return ListingRepository(db)
