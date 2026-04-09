from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.enum import BookingStatus, CurrencyCode, PaymentTransactionStatus


class BookingTravelerBase(BaseModel):
    first_name: str
    last_name: str
    age: int
    nationality: str | None = None
    passport_no: str | None = None
    special_notes: str | None = None


class BookingTravelerCreate(BookingTravelerBase):
    pass


class BookingTravelerResponse(BookingTravelerBase):
    id: UUID

    model_config = ConfigDict(from_attributes=True)


class BookingItemBase(BaseModel):
    listing_id: UUID
    variant_id: UUID
    travel_date: date
    quantity: int = Field(ge=1)
    unit_price: float
    total_price: float
    travelers: list[BookingTravelerCreate] = []


class BookingItemCreate(BookingItemBase):
    pass


class BookingItemResponse(BookingItemBase):
    id: UUID
    travelers: list[BookingTravelerResponse] = []

    model_config = ConfigDict(from_attributes=True)


class BookingBase(BaseModel):
    booking_reference: str
    status: BookingStatus = BookingStatus.PENDING
    total_amount: Decimal
    currency: CurrencyCode = CurrencyCode.USD
    payment_status: PaymentTransactionStatus = PaymentTransactionStatus.PENDING
    booked_at: datetime


class BookingCreate(BookingBase):
    booking_items: list[BookingItemCreate] = Field(min_length=1)


class CheckoutBookingCreate(BaseModel):
    listing_id: UUID
    travel_date: datetime
    travel_count: int = Field(ge=1)
    unit_price_minor: int = Field(ge=0)
    total_price_minor: int = Field(ge=0)
    status: BookingStatus = BookingStatus.PENDING


class BookingUpdate(BaseModel):
    booking_reference: str | None = None
    status: BookingStatus | None = None
    total_amount: Decimal | None = None
    currency: CurrencyCode | None = None
    payment_status: PaymentTransactionStatus | None = None
    booked_at: datetime | None = None
    booking_items: list[BookingItemCreate] | None = None


class BookingResponse(BookingBase):
    id: UUID
    user_id: UUID
    booking_items: list[BookingItemResponse]
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class BookingInDB(BookingResponse):
    pass


class CheckoutBookingResponse(BaseModel):
    id: UUID
    user_id: UUID
    listing_id: UUID
    travel_date: datetime
    travel_count: int
    unit_price_minor: int
    total_price_minor: int
    status: BookingStatus
    created_at: datetime


class BookingListResponse(BaseModel):
    bookings: list[BookingResponse]
    total: int
    page: int
    per_page: int
    total_pages: int


class BookingSearchParams(BaseModel):
    user_id: UUID | None = None
    listing_id: UUID | None = None
    variant_id: UUID | None = None
    status: BookingStatus | None = None
    booked_at_from: datetime | None = None
    booked_at_to: datetime | None = None
    travel_date_from: date | None = None
    travel_date_to: date | None = None
    min_total_amount: Decimal | None = None
    max_total_amount: Decimal | None = None
    page: int = 1
    per_page: int = 20


class BookingStatusUpdate(BaseModel):
    status: BookingStatus


class BookingSummary(BaseModel):
    total_bookings: int
    pending: int
    confirmed: int
    cancelled: int
    completed: int
    total_revenue: Decimal
