from datetime import datetime
from typing import Optional
from uuid import UUID
from pydantic import BaseModel, ConfigDict

from app.models.enum import BookingStatus


class BookingBase(BaseModel):
<<<<<<< Updated upstream
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
=======
    listing_id: UUID
    travel_date: datetime
    travel_count: int = Field(ge=1)
    unit_price_minor: int = Field(ge=0)
    total_price_minor: int = Field(ge=0)
    status: BookingStatus = BookingStatus.PENDING_PAYMENT


class BookingCreateRequest(BookingBase):
    """Create booking payload for authenticated users. Ownership is derived from the bearer token."""
    pass


class BookingUpdate(BaseModel):
    listing_id: UUID | None = None
    travel_date: datetime | None = None
    travel_count: int | None = Field(default=None, ge=1)
    unit_price_minor: int | None = Field(default=None, ge=0)
    total_price_minor: int | None = Field(default=None, ge=0)
    status: BookingStatus | None = None
>>>>>>> Stashed changes


class BookingResponse(BookingBase):
    """Schema for booking API responses"""
    id: UUID
<<<<<<< Updated upstream
    created_at: datetime
    
=======
    user_id: UUID
    created_at: datetime

>>>>>>> Stashed changes
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
<<<<<<< Updated upstream
    """Schema for booking search parameters"""
    user_id: Optional[UUID] = None
    listing_id: Optional[UUID] = None
    status: Optional[BookingStatus] = None
    travel_date_from: Optional[datetime] = None
    travel_date_to: Optional[datetime] = None
    min_price: Optional[int] = None
    max_price: Optional[int] = None
=======
    user_id: UUID | None = None
    listing_id: UUID | None = None
    variant_id: UUID | None = None
    status: BookingStatus | None = None
    booked_at_from: datetime | None = None
    booked_at_to: datetime | None = None
    travel_date_from: date | None = None
    travel_date_to: date | None = None
    min_price: Decimal | None = None
    max_price: Decimal | None = None
>>>>>>> Stashed changes
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