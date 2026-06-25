from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, EmailStr

from app.models.enum import CurrencyCode, InquiryStatus


class CartItemSchema(BaseModel):
    """Cart item schema for booking inquiries"""
    model_config = ConfigDict(populate_by_name=True)
    
    listing_id: str = Field(..., alias="listingId")
    title: str
    travel_date: datetime = Field(..., alias="travelDate")
    travel_count: int = Field(ge=1, alias="travelCount")
    price: Decimal = Field(ge=0)
    base_currency: CurrencyCode = Field(default=CurrencyCode.USD, alias="baseCurrency")


class BookingInquiryBase(BaseModel):
    """Base schema for booking inquiry"""
    model_config = ConfigDict(populate_by_name=True)
    
    first_name: str = Field(..., min_length=1, max_length=100, alias="firstName")
    last_name: str = Field(..., min_length=1, max_length=100, alias="lastName")
    email: EmailStr
    phone: str = Field(..., min_length=1, max_length=20)
    nationality: str = Field(..., min_length=1, max_length=100)
    emergency_contact: str | None = Field(None, max_length=200, alias="emergencyContact")
    number_of_travelers: int = Field(..., ge=1, le=50, alias="numberOfTravelers")
    special_requests: str | None = Field(None, max_length=1000, alias="specialRequests")
    cart_items: list[CartItemSchema] = Field(..., min_length=1, alias="cartItems")
    subtotal: Decimal = Field(..., ge=0)
    total: Decimal = Field(..., ge=0)
    currency: CurrencyCode = CurrencyCode.USD


class BookingInquiryCreate(BookingInquiryBase):
    """Schema for creating a booking inquiry"""
    pass


class BookingInquiryResponse(BaseModel):
    """Schema for booking inquiry response"""
    id: UUID
    reference: str
    status: InquiryStatus
    created_at: datetime
    
    model_config = ConfigDict(
        from_attributes=True,
        json_encoders={
            datetime: lambda v: v.isoformat(),
            Decimal: lambda v: float(v)
        }
    )


class BookingInquiryDetailed(BookingInquiryBase):
    """Detailed schema for booking inquiry with all fields"""
    id: UUID
    reference: str
    status: InquiryStatus
    created_at: datetime
    updated_at: datetime
    
    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True,
        json_encoders={
            datetime: lambda v: v.isoformat(),
            Decimal: lambda v: float(v)
        }
    )


class BookingInquiryUpdate(BaseModel):
    """Schema for updating a booking inquiry"""
    status: InquiryStatus | None = None
    special_requests: str | None = Field(None, max_length=1000)


class BookingInquiryListResponse(BaseModel):
    """Schema for paginated booking inquiry list"""
    inquiries: list[BookingInquiryDetailed]
    total: int
    page: int
    per_page: int
    total_pages: int


class BookingInquirySearchParams(BaseModel):
    """Schema for booking inquiry search parameters"""
    email: str | None = None
    status: InquiryStatus | None = None
    created_from: datetime | None = None
    created_to: datetime | None = None
    nationality: str | None = None
    page: int = Field(1, ge=1)
    per_page: int = Field(20, ge=1, le=100)


class AdminBookingInquiryCustomer(BaseModel):
    """Customer schema inside AdminBookingInquiryItem"""
    name: str
    email: EmailStr
    phone: str
    nationality: str
    emergency_contact: str | None = Field(None, alias="emergencyContact")

    model_config = ConfigDict(
        populate_by_name=True,
        from_attributes=True
    )


class AdminBookingInquiryItem(BaseModel):
    """Admin/vendor friendly booking inquiry response item"""
    id: UUID
    reference: str
    status: InquiryStatus
    customer: AdminBookingInquiryCustomer
    listing_summary: str = Field(..., alias="listingSummary")
    listings: list[CartItemSchema]
    listing_ids: list[str] = Field(..., alias="listingIds")
    type: str  # derived from listing/listing_type when possible, e.g. "Stay", "Tour", etc.
    vendor_ids: list[UUID] = Field(..., alias="vendorIds")
    vendor_names: list[str] = Field(..., alias="vendorNames")
    travel_date: datetime = Field(..., alias="travelDate")
    guests: int  # maps to numberOfTravelers
    number_of_travelers: int = Field(..., alias="numberOfTravelers")
    subtotal: Decimal
    total: Decimal
    currency: CurrencyCode
    special_requests: str | None = Field(None, alias="specialRequests")
    created_at: datetime = Field(..., alias="createdAt")
    updated_at: datetime = Field(..., alias="updatedAt")

    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True,
        json_encoders={
            datetime: lambda v: v.isoformat(),
            Decimal: lambda v: float(v),
            UUID: lambda v: str(v)
        }
    )


class AdminBookingInquiryStatusCounts(BaseModel):
    """Statistics count grouped by status"""
    all: int
    pending_contact: int = Field(..., alias="pending_contact")
    contacted: int
    quoted: int
    converted_to_booking: int = Field(..., alias="converted_to_booking")
    cancelled: int

    model_config = ConfigDict(populate_by_name=True)


class AdminBookingInquiryMetrics(BaseModel):
    """Metrics calculation for dashboard cards"""
    total_value: Decimal = Field(..., alias="totalValue")
    pending_value: Decimal = Field(..., alias="pendingValue")
    confirmed_or_converted_count: int = Field(..., alias="confirmedOrConvertedCount")
    cancelled_count: int = Field(..., alias="cancelledCount")

    model_config = ConfigDict(populate_by_name=True)


class AdminBookingInquiryPaginatedResponse(BaseModel):
    """Response structure for admin booking inquiry listing"""
    items: list[AdminBookingInquiryItem]
    total: int
    page: int
    per_page: int = Field(..., alias="perPage")
    total_pages: int = Field(..., alias="totalPages")
    status_counts: AdminBookingInquiryStatusCounts = Field(..., alias="statusCounts")
    metrics: AdminBookingInquiryMetrics

    model_config = ConfigDict(populate_by_name=True)


class VendorBookingInquiryPaginatedResponse(BaseModel):
    """Response structure for vendor booking inquiry listing"""
    items: list[AdminBookingInquiryItem]
    total: int
    page: int
    per_page: int = Field(..., alias="perPage")
    total_pages: int = Field(..., alias="totalPages")

    model_config = ConfigDict(populate_by_name=True)


class UpdateInquiryStatusPayload(BaseModel):
    """Payload for patching booking inquiry status"""
    status: InquiryStatus