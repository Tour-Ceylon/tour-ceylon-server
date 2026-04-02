from datetime import datetime
from typing import Optional
from uuid import UUID
from pydantic import BaseModel, ConfigDict

from app.models.enum import BookingStatus


class BookingBase(BaseModel):
    """Base booking schema with common fields"""
    user_id: UUID
    listing_id: UUID
    travel_date: datetime
    travel_count: int = 1
    unit_price_minor: int
    total_price_minor: int
    status: BookingStatus = BookingStatus.PENDING_PAYMENT


class BookingCreate(BookingBase):
    """Schema for creating a new booking"""
    pass


class BookingCreateRequest(BaseModel):
    """Client request schema for creating a booking.

    user_id is optional and ignored server-side when authenticated context is available.
    """

    user_id: Optional[UUID] = None
    listing_id: UUID
    travel_date: datetime
    travel_count: int = 1
    unit_price_minor: int
    total_price_minor: int
    status: BookingStatus = BookingStatus.PENDING_PAYMENT


class BookingUpdate(BaseModel):
    """Schema for updating booking information"""
    travel_date: Optional[datetime] = None
    travel_count: Optional[int] = None
    unit_price_minor: Optional[int] = None
    total_price_minor: Optional[int] = None
    status: Optional[BookingStatus] = None


class BookingResponse(BookingBase):
    """Schema for booking API responses"""
    id: UUID
    created_at: datetime
    
    model_config = ConfigDict(from_attributes=True)


class BookingInDB(BookingResponse):
    """Schema for booking stored in database (includes all fields)"""
    pass


class BookingListResponse(BaseModel):
    """Schema for paginated booking list responses"""
    bookings: list[BookingResponse]
    total: int
    page: int
    per_page: int
    total_pages: int


class BookingSearchParams(BaseModel):
    """Schema for booking search parameters"""
    user_id: Optional[UUID] = None
    listing_id: Optional[UUID] = None
    status: Optional[BookingStatus] = None
    travel_date_from: Optional[datetime] = None
    travel_date_to: Optional[datetime] = None
    min_price: Optional[int] = None
    max_price: Optional[int] = None
    page: int = 1
    per_page: int = 20


class BookingStatusUpdate(BaseModel):
    """Schema for updating booking status"""
    status: BookingStatus


class BookingSummary(BaseModel):
    """Schema for booking summary statistics"""
    total_bookings: int
    pending_payment: int
    confirmed: int
    cancelled: int
    completed: int
    total_revenue_minor: int