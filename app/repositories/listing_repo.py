from typing import Optional, List
from uuid import UUID
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, func

from app.models.listing import Listing
from app.models.enum import ListingType, CurrencyType, ListingStatus
from app.schemas.listing_schema import ListingCreate, ListingUpdate, ListingSearchParams


class ListingRepository:
    """Repository class for Listing model database operations"""
    
    def __init__(self, db: Session):
        self.db = db
    
    def create(self, listing_data: ListingCreate) -> Listing:
        """Create a new listing"""
        requested_status = getattr(listing_data, "status", None)
        is_active = requested_status == ListingStatus.PUBLISHED if requested_status else True
        db_listing = Listing(
            type=listing_data.type,
            title=listing_data.title,
            slug=listing_data.slug,
            description=listing_data.description,
            location_city=listing_data.location_city,
            location_district=listing_data.location_district,
            latitude=listing_data.latitude,
            longitude=listing_data.longitude,
            base_currency=listing_data.base_currency,
            is_active=is_active,
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
        status: Optional[ListingStatus] = None
    ) -> List[Listing]:
        """Get all listings with optional filtering"""
        query = self.db.query(Listing)
        
        if status is not None:
            if status == ListingStatus.PUBLISHED:
                query = query.filter(Listing.is_active.is_(True))
            else:
                query = query.filter(Listing.is_active.is_(False))
            
        return query.offset(skip).limit(limit).all()
    
    def search(self, search_params: ListingSearchParams) -> tuple[List[Listing], int]:
        """Search listings with filters and pagination"""
        query = self.db.query(Listing)
        
        # Apply filters
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
        
        if search_params.status:
            if search_params.status == ListingStatus.PUBLISHED:
                filters.append(Listing.is_active.is_(True))
            else:
                filters.append(Listing.is_active.is_(False))
        
        if filters:
            query = query.filter(and_(*filters))
        
        # Get total count before pagination
        total_count = query.count()
        
        # Apply pagination
        skip = (search_params.page - 1) * search_params.per_page
        listings = query.offset(skip).limit(search_params.per_page).all()
        
        return listings, total_count
    
    def update(self, listing_id: UUID, listing_data: ListingUpdate) -> Optional[Listing]:
        """Update listing by ID"""
        db_listing = self.get_by_id(listing_id)
        if not db_listing:
            return None
        
        # Update only provided fields
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
    
    def soft_delete(self, listing_id: UUID) -> Optional[Listing]:
        """Soft delete listing by setting status to ARCHIVED"""
        db_listing = self.get_by_id(listing_id)
        if not db_listing:
            return None
        
        db_listing.is_active = False
        self.db.commit()
        self.db.refresh(db_listing)
        return db_listing
    
    def publish(self, listing_id: UUID) -> Optional[Listing]:
        """Publish listing by setting status to PUBLISHED"""
        db_listing = self.get_by_id(listing_id)
        if not db_listing:
            return None
        
        db_listing.is_active = True
        self.db.commit()
        self.db.refresh(db_listing)
        return db_listing
    
    def draft(self, listing_id: UUID) -> Optional[Listing]:
        """Set listing to draft by setting status to DRAFT"""
        db_listing = self.get_by_id(listing_id)
        if not db_listing:
            return None
        
        db_listing.is_active = False
        self.db.commit()
        self.db.refresh(db_listing)
        return db_listing
    
    def get_by_type(self, listing_type: ListingType) -> List[Listing]:
        """Get all listings by type"""
        return self.db.query(Listing).filter(Listing.type == listing_type).all()
    
    def get_by_status(self, status: ListingStatus) -> List[Listing]:
        """Get all listings by status"""
        if status == ListingStatus.PUBLISHED:
            return self.db.query(Listing).filter(Listing.is_active.is_(True)).all()
        return self.db.query(Listing).filter(Listing.is_active.is_(False)).all()
    
    def get_by_location_city(self, city: str) -> List[Listing]:
        """Get all listings by city"""
        return self.db.query(Listing).filter(Listing.location_city.ilike(f"%{city}%")).all()
    
    def get_by_location_district(self, district: str) -> List[Listing]:
        """Get all listings by district"""
        return self.db.query(Listing).filter(Listing.location_district.ilike(f"%{district}%")).all()
    
    def get_by_currency(self, currency: CurrencyType) -> List[Listing]:
        """Get all listings by base currency"""
        return self.db.query(Listing).filter(Listing.base_currency == currency).all()
    
    def get_published(self) -> List[Listing]:
        """Get all published listings"""
        return self.db.query(Listing).filter(Listing.is_active.is_(True)).all()
    
    def get_drafts(self) -> List[Listing]:
        """Get all draft listings"""
        return self.db.query(Listing).filter(Listing.is_active.is_(False)).all()
    
    def get_archived(self) -> List[Listing]:
        """Get all archived listings"""
        return self.db.query(Listing).filter(Listing.is_active.is_(False)).all()
    
    def count_by_type(self) -> dict:
        """Get listing count grouped by type"""
        results = (
            self.db.query(Listing.type, func.count(Listing.id))
            .group_by(Listing.type)
            .all()
        )
        return {listing_type: count for listing_type, count in results}
    
    def count_by_status(self) -> dict:
        """Get listing count grouped by status"""
        return {
            ListingStatus.PUBLISHED: self.count_published_listings(),
            ListingStatus.DRAFT: self.count_draft_listings(),
            ListingStatus.ARCHIVED: 0,
        }
    
    def count_by_currency(self) -> dict:
        """Get listing count grouped by currency"""
        results = (
            self.db.query(Listing.base_currency, func.count(Listing.id))
            .group_by(Listing.base_currency)
            .all()
        )
        return {currency: count for currency, count in results}
    
    def count_published_listings(self) -> int:
        """Get count of published listings"""
        return self.db.query(Listing).filter(Listing.is_active.is_(True)).count()
    
    def count_draft_listings(self) -> int:
        """Get count of draft listings"""
        return self.db.query(Listing).filter(Listing.is_active.is_(False)).count()
    
    def count_archived_listings(self) -> int:
        """Get count of archived listings"""
        return 0
    
    def exists_by_slug(self, slug: str, exclude_listing_id: Optional[UUID] = None) -> bool:
        """Check if listing exists by slug, optionally excluding a specific listing ID"""
        query = self.db.query(Listing).filter(Listing.slug == slug)
        
        if exclude_listing_id:
            query = query.filter(Listing.id != exclude_listing_id)
        
        return query.first() is not None
    
    def search_by_location(self, latitude: float, longitude: float, radius_km: float = 10.0) -> List[Listing]:
        """Search listings by geographic proximity (simplified distance calculation)"""
        # Simple distance calculation using lat/lng differences
        # For production, consider using PostGIS or more accurate distance calculations
        lat_diff = radius_km / 111.0  # Rough conversion: 1 degree ≈ 111 km
        lng_diff = radius_km / 111.0
        
        return self.db.query(Listing).filter(
            and_(
                Listing.latitude.between(latitude - lat_diff, latitude + lat_diff),
                Listing.longitude.between(longitude - lng_diff, longitude + lng_diff),
                Listing.latitude.is_not(None),
                Listing.longitude.is_not(None)
            )
        ).all()


# Dependency function to get listing repository
def get_listing_repository(db: Session = None) -> ListingRepository:
    """Get listing repository instance"""
    if db is None:
        from app.config.database import SessionLocal
        db = SessionLocal()
    return ListingRepository(db)