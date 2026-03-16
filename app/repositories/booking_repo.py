from typing import Optional, List
from uuid import UUID
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, func

from app.models.booking import Bookings
from app.models.enum import BookingStatus
from app.schemas.booking_schema import BookingCreate, BookingUpdate, BookingSearchParams


class BookingRepository:
    """Repository class for Booking model database operations"""
    
    def __init__(self, db: Session):
        self.db = db
    
    def create(self, booking_data: BookingCreate) -> Bookings:
        """Create a new booking"""
        db_booking = Bookings(
            user_id=booking_data.user_id,
            listing_id=booking_data.listing_id,
            travel_date=booking_data.travel_date,
            travel_count=booking_data.travel_count,
            unit_price_minor=booking_data.unit_price_minor,
            total_price_minor=booking_data.total_price_minor,
            status=booking_data.status
        )
        self.db.add(db_booking)
        self.db.commit()
        self.db.refresh(db_booking)
        return db_booking
    
    def get_by_id(self, booking_id: UUID) -> Optional[Bookings]:
        """Get booking by ID"""
        return self.db.query(Bookings).filter(Bookings.id == booking_id).first()
    
    def get_by_user_id(self, user_id: UUID) -> List[Bookings]:
        """Get all bookings for a specific user"""
        return self.db.query(Bookings).filter(Bookings.user_id == user_id).all()
    
    def get_by_listing_id(self, listing_id: UUID) -> List[Bookings]:
        """Get all bookings for a specific listing"""
        return self.db.query(Bookings).filter(Bookings.listing_id == listing_id).all()
    
    def get_all(
        self, 
        skip: int = 0, 
        limit: int = 100,
        status: Optional[BookingStatus] = None
    ) -> List[Bookings]:
        """Get all bookings with optional filtering"""
        query = self.db.query(Bookings)
        
        if status is not None:
            query = query.filter(Bookings.status == status)
            
        return query.offset(skip).limit(limit).all()
    
    def search(self, search_params: BookingSearchParams) -> tuple[List[Bookings], int]:
        """Search bookings with filters and pagination"""
        query = self.db.query(Bookings)
        
        # Apply filters
        filters = []
        
        if search_params.user_id:
            filters.append(Bookings.user_id == search_params.user_id)
        
        if search_params.listing_id:
            filters.append(Bookings.listing_id == search_params.listing_id)
        
        if search_params.status:
            filters.append(Bookings.status == search_params.status)
        
        if search_params.travel_date_from:
            filters.append(Bookings.travel_date >= search_params.travel_date_from)
        
        if search_params.travel_date_to:
            filters.append(Bookings.travel_date <= search_params.travel_date_to)
        
        if search_params.min_price:
            filters.append(Bookings.total_price_minor >= search_params.min_price)
        
        if search_params.max_price:
            filters.append(Bookings.total_price_minor <= search_params.max_price)
        
        if filters:
            query = query.filter(and_(*filters))
        
        # Get total count before pagination
        total_count = query.count()
        
        # Apply pagination
        skip = (search_params.page - 1) * search_params.per_page
        bookings = query.offset(skip).limit(search_params.per_page).all()
        
        return bookings, total_count
    
    def update(self, booking_id: UUID, booking_data: BookingUpdate) -> Optional[Bookings]:
        """Update booking by ID"""
        db_booking = self.get_by_id(booking_id)
        if not db_booking:
            return None
        
        # Update only provided fields
        update_data = booking_data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(db_booking, field, value)
        
        self.db.commit()
        self.db.refresh(db_booking)
        return db_booking
    
    def delete(self, booking_id: UUID) -> bool:
        """Delete booking by ID"""
        db_booking = self.get_by_id(booking_id)
        if not db_booking:
            return False
        
        self.db.delete(db_booking)
        self.db.commit()
        return True
    
    def update_status(self, booking_id: UUID, status: BookingStatus) -> Optional[Bookings]:
        """Update booking status"""
        db_booking = self.get_by_id(booking_id)
        if not db_booking:
            return None
        
        db_booking.status = status
        self.db.commit()
        self.db.refresh(db_booking)
        return db_booking
    
    def get_by_status(self, status: BookingStatus) -> List[Bookings]:
        """Get all bookings by status"""
        return self.db.query(Bookings).filter(Bookings.status == status).all()
    
    def get_user_bookings_by_status(self, user_id: UUID, status: BookingStatus) -> List[Bookings]:
        """Get user bookings by status"""
        return (
            self.db.query(Bookings)
            .filter(Bookings.user_id == user_id, Bookings.status == status)
            .all()
        )
    
    def get_listing_bookings_by_status(self, listing_id: UUID, status: BookingStatus) -> List[Bookings]:
        """Get listing bookings by status"""
        return (
            self.db.query(Bookings)
            .filter(Bookings.listing_id == listing_id, Bookings.status == status)
            .all()
        )
    
    def get_bookings_by_date_range(
        self, 
        start_date: datetime, 
        end_date: datetime
    ) -> List[Bookings]:
        """Get bookings within a date range"""
        return (
            self.db.query(Bookings)
            .filter(Bookings.travel_date >= start_date, Bookings.travel_date <= end_date)
            .all()
        )
    
    def count_by_status(self) -> dict:
        """Get booking count grouped by status"""
        results = (
            self.db.query(Bookings.status, func.count(Bookings.id))
            .group_by(Bookings.status)
            .all()
        )
        return {status: count for status, count in results}
    
    def count_by_user(self, user_id: UUID) -> int:
        """Get booking count for a specific user"""
        return self.db.query(Bookings).filter(Bookings.user_id == user_id).count()
    
    def count_by_listing(self, listing_id: UUID) -> int:
        """Get booking count for a specific listing"""
        return self.db.query(Bookings).filter(Bookings.listing_id == listing_id).count()
    
    def get_total_revenue(self, status: Optional[BookingStatus] = None) -> int:
        """Get total revenue from bookings, optionally filtered by status"""
        query = self.db.query(func.sum(Bookings.total_price_minor))
        
        if status:
            query = query.filter(Bookings.status == status)
        
        result = query.scalar()
        return result or 0
    
    def get_user_total_spent(self, user_id: UUID, status: Optional[BookingStatus] = None) -> int:
        """Get total amount spent by a specific user"""
        query = (
            self.db.query(func.sum(Bookings.total_price_minor))
            .filter(Bookings.user_id == user_id)
        )
        
        if status:
            query = query.filter(Bookings.status == status)
        
        result = query.scalar()
        return result or 0
    
    def get_listing_total_revenue(self, listing_id: UUID, status: Optional[BookingStatus] = None) -> int:
        """Get total revenue for a specific listing"""
        query = (
            self.db.query(func.sum(Bookings.total_price_minor))
            .filter(Bookings.listing_id == listing_id)
        )
        
        if status:
            query = query.filter(Bookings.status == status)
        
        result = query.scalar()
        return result or 0
    
    def get_monthly_revenue(self, year: int, month: int) -> int:
        """Get total revenue for a specific month"""
        start_date = datetime(year, month, 1)
        if month == 12:
            end_date = datetime(year + 1, 1, 1)
        else:
            end_date = datetime(year, month + 1, 1)
        
        result = (
            self.db.query(func.sum(Bookings.total_price_minor))
            .filter(
                Bookings.created_at >= start_date,
                Bookings.created_at < end_date,
                Bookings.status.in_([BookingStatus.CONFIRMED, BookingStatus.COMPLETED])
            )
            .scalar()
        )
        return result or 0
    
    def exists_booking(self, user_id: UUID, listing_id: UUID, travel_date: datetime) -> bool:
        """Check if a booking exists for user, listing and travel date"""
        return (
            self.db.query(Bookings)
            .filter(
                Bookings.user_id == user_id,
                Bookings.listing_id == listing_id,
                Bookings.travel_date == travel_date
            )
            .first() is not None
        )


# Dependency function to get booking repository
def get_booking_repository(db: Session = None) -> BookingRepository:
    """Get booking repository instance"""
    if db is None:
        from app.config.database import SessionLocal
        db = SessionLocal()
    return BookingRepository(db)