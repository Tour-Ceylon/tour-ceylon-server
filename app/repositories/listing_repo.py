from typing import Optional, List
from uuid import UUID
from sqlalchemy.orm import Session
from sqlalchemy import and_, func

from app.models.listing import Listing
from app.models.enum import ListingType, CurrencyType
from app.schemas.listing_schema import ListingCreate, ListingUpdate, ListingSearchParams


class ListingRepository:
    """Repository class for Listing model database operations"""

    def __init__(self, db: Session):
        self.db = db

    def create(self, listing_data: ListingCreate) -> Listing:
        """Create a new listing"""
        db_listing = Listing(
            type=listing_data.type,
            title=listing_data.title,
            slug=listing_data.slug,
            description=listing_data.description,
            location=listing_data.location,
            location_city=listing_data.location_city,
            location_district=listing_data.location_district,
            latitude=listing_data.latitude,
            longitude=listing_data.longitude,
            image=listing_data.image,
            rating=listing_data.rating,
            review_count=listing_data.review_count,
            cancellation_policy=listing_data.cancellation_policy,
            includes=listing_data.includes,
            recommendation=listing_data.recommendation,
            is_active=listing_data.is_active,
            base_currency=listing_data.base_currency,
            # Subtype-specific fields
            duration=listing_data.duration,
            route=listing_data.route,
            price=listing_data.price,
            highlights=listing_data.highlights,
            activity_type=listing_data.activity_type,
            difficulty=listing_data.difficulty,
            origin=listing_data.origin,
            destination=listing_data.destination,
            vehicle_type=listing_data.vehicle_type,
            service_highlights=listing_data.service_highlights,
        )
        self.db.add(db_listing)
        self.db.commit()
        self.db.refresh(db_listing)
        return db_listing

    def get_by_id(self, listing_id: UUID) -> Optional[Listing]:
        """Get listing by ID"""
        return self.db.query(Listing).filter(Listing.id == listing_id).first()

    def get_by_slug(self, slug: str) -> Optional[Listing]:
        """Get listing by slug"""
        return self.db.query(Listing).filter(Listing.slug == slug).first()

    def get_all(
        self,
        skip: int = 0,
        limit: int = 100,
        is_active: Optional[bool] = None,
    ) -> List[Listing]:
        """Get all listings with optional filtering"""
        query = self.db.query(Listing)

        if is_active is not None:
            query = query.filter(Listing.is_active == is_active)

        return query.offset(skip).limit(limit).all()

    def search(self, search_params: ListingSearchParams) -> tuple[List[Listing], int]:
        """Search listings with filters and pagination"""
        query = self.db.query(Listing)

        filters = []

        if search_params.type:
            filters.append(Listing.type == search_params.type)

        if search_params.title:
            filters.append(Listing.title.ilike(f"%{search_params.title}%"))

        if search_params.location_city:
            filters.append(Listing.location_city.ilike(f"%{search_params.location_city}%"))

        if search_params.location_district:
            filters.append(Listing.location_district.ilike(f"%{search_params.location_district}%"))

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
        """Update listing by ID"""
        db_listing = self.get_by_id(listing_id)
        if not db_listing:
            return None

        update_data = listing_data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(db_listing, field, value)

        self.db.commit()
        self.db.refresh(db_listing)
        return db_listing

    def delete(self, listing_id: UUID) -> bool:
        """Delete listing by ID"""
        db_listing = self.get_by_id(listing_id)
        if not db_listing:
            return False

        self.db.delete(db_listing)
        self.db.commit()
        return True

    def deactivate(self, listing_id: UUID) -> Optional[Listing]:
        """Deactivate listing (soft-delete equivalent)"""
        db_listing = self.get_by_id(listing_id)
        if not db_listing:
            return None

        db_listing.is_active = False
        self.db.commit()
        self.db.refresh(db_listing)
        return db_listing

    def activate(self, listing_id: UUID) -> Optional[Listing]:
        """Activate listing"""
        db_listing = self.get_by_id(listing_id)
        if not db_listing:
            return None

        db_listing.is_active = True
        self.db.commit()
        self.db.refresh(db_listing)
        return db_listing

    def get_by_type(self, listing_type: ListingType) -> List[Listing]:
        """Get all listings by type"""
        return self.db.query(Listing).filter(Listing.type == listing_type).all()

    def get_active(self) -> List[Listing]:
        """Get all active listings"""
        return self.db.query(Listing).filter(Listing.is_active == True).all()

    def get_inactive(self) -> List[Listing]:
        """Get all inactive listings"""
        return self.db.query(Listing).filter(Listing.is_active == False).all()

    def get_by_location_city(self, city: str) -> List[Listing]:
        """Get all listings by city"""
        return self.db.query(Listing).filter(Listing.location_city.ilike(f"%{city}%")).all()

    def get_by_location_district(self, district: str) -> List[Listing]:
        """Get all listings by district"""
        return self.db.query(Listing).filter(Listing.location_district.ilike(f"%{district}%")).all()

    def get_by_currency(self, currency: CurrencyType) -> List[Listing]:
        """Get all listings by base currency"""
        return self.db.query(Listing).filter(Listing.base_currency == currency).all()

    def count_by_type(self) -> dict:
        """Get listing count grouped by type"""
        results = (
            self.db.query(Listing.type, func.count(Listing.id))
            .group_by(Listing.type)
            .all()
        )
        return {listing_type: count for listing_type, count in results}

    def count_active(self) -> int:
        """Get count of active listings"""
        return self.db.query(Listing).filter(Listing.is_active == True).count()

    def count_inactive(self) -> int:
        """Get count of inactive listings"""
        return self.db.query(Listing).filter(Listing.is_active == False).count()

    def count_by_currency(self) -> dict:
        """Get listing count grouped by currency"""
        results = (
            self.db.query(Listing.base_currency, func.count(Listing.id))
            .group_by(Listing.base_currency)
            .all()
        )
        return {currency: count for currency, count in results}

    def exists_by_slug(self, slug: str, exclude_listing_id: Optional[UUID] = None) -> bool:
        """Check if listing exists by slug, optionally excluding a specific listing ID"""
        query = self.db.query(Listing).filter(Listing.slug == slug)

        if exclude_listing_id:
            query = query.filter(Listing.id != exclude_listing_id)

        return query.first() is not None

    def search_by_location(self, latitude: float, longitude: float, radius_km: float = 10.0) -> List[Listing]:
        """Search listings by geographic proximity (simplified distance calculation)"""
        lat_diff = radius_km / 111.0
        lng_diff = radius_km / 111.0

        return self.db.query(Listing).filter(
            and_(
                Listing.latitude.between(latitude - lat_diff, latitude + lat_diff),
                Listing.longitude.between(longitude - lng_diff, longitude + lng_diff),
                Listing.latitude.is_not(None),
                Listing.longitude.is_not(None),
            )
        ).all()


# Dependency function to get listing repository
def get_listing_repository(db: Session = None) -> ListingRepository:
    """Get listing repository instance"""
    if db is None:
        from app.config.database import SessionLocal

        db = SessionLocal()
    return ListingRepository(db)