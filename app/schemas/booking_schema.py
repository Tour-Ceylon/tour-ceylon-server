from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.enum import BookingStatus, CurrencyCode, PaymentTransactionStatus, PaymentMethod


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
    booking_reference: str | None = None
    user_id: UUID
    status: BookingStatus = BookingStatus.PENDING
    total_amount: Decimal
    currency: CurrencyCode = CurrencyCode.USD
    payment_method: PaymentMethod = PaymentMethod.PAY_AT_PROPERTY
    payment_status: PaymentTransactionStatus = PaymentTransactionStatus.PENDING
    booked_at: datetime | None = None
    guest_name: str | None = None
    guest_email: str | None = None
    guest_phone: str | None = None
    special_requests: str | None = None


class BookingCreate(BaseModel):
    user_id: UUID
    payment_method: PaymentMethod = PaymentMethod.PAY_AT_PROPERTY
    guest_name: str | None = None
    guest_email: str | None = None
    guest_phone: str | None = None
    special_requests: str | None = None
    booking_items: list[BookingItemCreate] = Field(min_length=1)
    check_in_date: date | None = None
    check_out_date: date | None = None


class BookingUpdate(BaseModel):
    booking_reference: str | None = None
    user_id: UUID | None = None
    status: BookingStatus | None = None
    total_amount: Decimal | None = None
    currency: CurrencyCode | None = None
    payment_method: PaymentMethod | None = None
    payment_status: PaymentTransactionStatus | None = None
    booked_at: datetime | None = None
    booking_items: list[BookingItemCreate] | None = None


class BookingResponse(BookingBase):
    id: UUID
    booking_items: list[BookingItemResponse]
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class BookingReceiptCreate(BaseModel):
    receipt_reference: str
    notes: str | None = None


class NightlyAvailability(BaseModel):
    date: date
    available_units: int
    total_units: int
    booked_units: int
    blocked_units: int
    price: float | None = None
    status: str = "OPEN"


class ListingAvailabilityResponse(BaseModel):
    listing_id: UUID
    start_date: date
    end_date: date
    nights: list[NightlyAvailability]


class BookingInDB(BookingResponse):
    pass


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
