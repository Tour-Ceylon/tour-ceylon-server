from datetime import date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, EmailStr, field_validator

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

    @field_validator("travel_date", mode="before")
    @classmethod
    def parse_travel_date(cls, value: Any) -> datetime:
        if isinstance(value, datetime):
            return value
        if isinstance(value, date):
            return datetime.combine(value, datetime.min.time())
        if isinstance(value, str):
            val = value.strip()
            if " to " in val:
                val = val.split(" to ")[0].strip()
            try:
                return datetime.fromisoformat(val.replace("Z", "+00:00"))
            except ValueError:
                pass
            try:
                return datetime.strptime(val[:10], "%Y-%m-%d")
            except ValueError:
                pass
        return datetime.utcnow()


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