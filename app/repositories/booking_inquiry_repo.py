import random
import string
from datetime import datetime
from typing import Optional
from uuid import UUID

from sqlalchemy import and_, func
from sqlalchemy.orm import Session

from app.models.bookingInquiry import BookingInquiry
from app.models.enum import InquiryStatus
from app.schemas.booking_inquiry_schema import BookingInquiryCreate, BookingInquirySearchParams, BookingInquiryUpdate


class BookingInquiryRepository:
    """Repository class for BookingInquiry model database operations"""

    def __init__(self, db: Session):
        self.db = db

    def _base_query(self):
        """Base query for booking inquiries"""
        return self.db.query(BookingInquiry)
    
    def _serialize_cart_items(self, cart_items: list) -> list:
        """
        Serialize cart items for JSON storage, handling datetime and Decimal objects properly
        """
        from decimal import Decimal
        
        serialized_items = []
        for item in cart_items:
            # Convert Pydantic model to dict if needed
            if hasattr(item, 'model_dump'):
                item_dict = item.model_dump()
            else:
                item_dict = item if isinstance(item, dict) else dict(item)
            
            # Convert datetime and Decimal objects for JSON compatibility
            for key, value in item_dict.items():
                if isinstance(value, datetime):
                    # Convert datetime to ISO format string
                    item_dict[key] = value.isoformat()
                elif isinstance(value, Decimal):
                    # Convert Decimal to float for JSON serialization
                    item_dict[key] = float(value)
            
            serialized_items.append(item_dict)
        
        return serialized_items

    def generate_inquiry_reference(self) -> str:
        """Generate unique inquiry reference in format INQ-XXXXXXXX"""
        while True:
            # Generate 8 random alphanumeric characters
            suffix = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
            reference = f"INQ-{suffix}"
            
            # Check if reference already exists
            existing = self._base_query().filter(BookingInquiry.reference == reference).first()
            if not existing:
                return reference

    def create(self, inquiry_data: BookingInquiryCreate) -> BookingInquiry:
        """Create a new booking inquiry"""
        inquiry_dict = inquiry_data.model_dump()
        
        # Properly serialize cart_items with datetime handling for JSON storage
        inquiry_dict['cart_items'] = self._serialize_cart_items(inquiry_dict['cart_items'])
        
        # Generate unique reference
        inquiry_dict['reference'] = self.generate_inquiry_reference()
        
        # Set default status
        inquiry_dict['status'] = InquiryStatus.PENDING_CONTACT
        
        db_inquiry = BookingInquiry(**inquiry_dict)
        self.db.add(db_inquiry)
        self.db.commit()
        self.db.refresh(db_inquiry)
        return db_inquiry

    def get_by_id(self, inquiry_id: UUID) -> Optional[BookingInquiry]:
        """Get booking inquiry by ID"""
        return self._base_query().filter(BookingInquiry.id == inquiry_id).first()

    def get_by_reference(self, reference: str) -> Optional[BookingInquiry]:
        """Get booking inquiry by reference"""
        return self._base_query().filter(BookingInquiry.reference == reference).first()

    def get_by_email(self, email: str) -> list[BookingInquiry]:
        """Get all booking inquiries by email"""
        return self._base_query().filter(BookingInquiry.email == email).order_by(BookingInquiry.created_at.desc()).all()

    def get_all(
        self,
        skip: int = 0,
        limit: int = 100,
        status: Optional[InquiryStatus] = None,
    ) -> list[BookingInquiry]:
        """Get all booking inquiries with optional status filter"""
        query = self._base_query()
        
        if status is not None:
            query = query.filter(BookingInquiry.status == status)
        
        return query.order_by(BookingInquiry.created_at.desc()).offset(skip).limit(limit).all()

    def search(self, search_params: BookingInquirySearchParams) -> tuple[list[BookingInquiry], int]:
        """Search booking inquiries with filters and pagination"""
        query = self._base_query()
        count_query = self.db.query(func.count(BookingInquiry.id))

        filters = []

        if search_params.email:
            filters.append(BookingInquiry.email.ilike(f"%{search_params.email}%"))

        if search_params.status:
            filters.append(BookingInquiry.status == search_params.status)

        if search_params.created_from:
            filters.append(BookingInquiry.created_at >= search_params.created_from)

        if search_params.created_to:
            filters.append(BookingInquiry.created_at <= search_params.created_to)

        if search_params.nationality:
            filters.append(BookingInquiry.nationality.ilike(f"%{search_params.nationality}%"))

        if filters:
            criteria = and_(*filters)
            query = query.filter(criteria)
            count_query = count_query.filter(criteria)

        total_count = count_query.scalar() or 0
        skip = (search_params.page - 1) * search_params.per_page
        inquiries = (
            query.order_by(BookingInquiry.created_at.desc())
            .offset(skip)
            .limit(search_params.per_page)
            .all()
        )

        return inquiries, total_count

    def update(self, inquiry_id: UUID, inquiry_data: BookingInquiryUpdate) -> Optional[BookingInquiry]:
        """Update a booking inquiry"""
        db_inquiry = self.get_by_id(inquiry_id)
        if not db_inquiry:
            return None

        update_data = inquiry_data.model_dump(exclude_unset=True)

        for field, value in update_data.items():
            setattr(db_inquiry, field, value)

        self.db.commit()
        self.db.refresh(db_inquiry)
        return db_inquiry

    def update_status(self, inquiry_id: UUID, status: InquiryStatus) -> Optional[BookingInquiry]:
        """Update inquiry status"""
        db_inquiry = self.get_by_id(inquiry_id)
        if not db_inquiry:
            return None

        db_inquiry.status = status
        self.db.commit()
        self.db.refresh(db_inquiry)
        return db_inquiry

    def delete(self, inquiry_id: UUID) -> bool:
        """Delete a booking inquiry"""
        db_inquiry = self.get_by_id(inquiry_id)
        if not db_inquiry:
            return False

        self.db.delete(db_inquiry)
        self.db.commit()
        return True

    def get_by_status(self, status: InquiryStatus) -> list[BookingInquiry]:
        """Get all inquiries by status"""
        return self._base_query().filter(BookingInquiry.status == status).order_by(BookingInquiry.created_at.desc()).all()

    def count_by_status(self) -> dict:
        """Count inquiries by status"""
        results = (
            self.db.query(BookingInquiry.status, func.count(BookingInquiry.id))
            .group_by(BookingInquiry.status)
            .all()
        )
        return {status: count for status, count in results}

    def count_total(self) -> int:
        """Count total number of inquiries"""
        return self.db.query(BookingInquiry).count()

    def get_recent_inquiries(self, limit: int = 10) -> list[BookingInquiry]:
        """Get most recent inquiries"""
        return (
            self._base_query()
            .order_by(BookingInquiry.created_at.desc())
            .limit(limit)
            .all()
        )


def get_booking_inquiry_repository(db: Session = None) -> BookingInquiryRepository:
    """Get booking inquiry repository instance"""
    if db is None:
        from app.config.database import SessionLocal
        db = SessionLocal()
    return BookingInquiryRepository(db)