from datetime import date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, EmailStr, field_validator, model_validator

from app.models.enum import CurrencyCode, InquiryStatus, PaymentMethod


class CartItemSchema(BaseModel):
    """Cart item schema for booking inquiries"""
    model_config = ConfigDict(populate_by_name=True, extra="allow")
    
    listing_id: str = Field(..., alias="listingId")
    title: str
    travel_date: datetime = Field(..., alias="travelDate")
    travel_date_end: datetime | None = Field(None, alias="travelDateEnd")
    travel_date_raw: str | None = Field(None, alias="travelDateRaw")
    travel_count: int = Field(ge=1, alias="travelCount")
    price: Decimal = Field(ge=0)
    base_currency: CurrencyCode = Field(default=CurrencyCode.USD, alias="baseCurrency")
    selected_rooms: list[Any] | None = Field(None, alias="selectedRooms")
    vendor_id: str | None = Field(None, alias="vendorId")
    vendor_name: str | None = Field(None, alias="vendorName")
    vendor_email: str | None = Field(None, alias="vendorEmail")
    vendor_role: str | None = Field(None, alias="vendorRole")

    @model_validator(mode="before")
    @classmethod
    def extract_travel_date_range(cls, data: Any) -> Any:
        if isinstance(data, dict):
            raw = (
                data.get("travelDateRaw")
                or data.get("travel_date_raw")
                or data.get("travelDate")
                or data.get("travel_date")
            )
            if isinstance(raw, str):
                val = raw.strip()
                if " to " in val:
                    parts = val.split(" to ")
                    start_str = parts[0].strip()
                    end_str = parts[1].strip()
                    data["travel_date_raw"] = val
                    data["travelDateRaw"] = val
                    data["travel_date"] = start_str
                    data["travelDate"] = start_str
                    if not data.get("travel_date_end") and not data.get("travelDateEnd"):
                        data["travel_date_end"] = end_str
                        data["travelDateEnd"] = end_str
                else:
                    if not data.get("travel_date_raw"):
                        data["travel_date_raw"] = val
            elif hasattr(raw, "isoformat"):
                if not data.get("travel_date_raw"):
                    data["travel_date_raw"] = raw.isoformat()

            # Also check explicit checkOutDate / check_out_date if travel_date_end is missing
            if not data.get("travel_date_end") and not data.get("travelDateEnd"):
                co = data.get("checkOutDate") or data.get("check_out_date")
                if co:
                    data["travel_date_end"] = co
                    data["travelDateEnd"] = co
        return data

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

    @field_validator("travel_date_end", mode="before")
    @classmethod
    def parse_travel_date_end(cls, value: Any) -> datetime | None:
        if value is None:
            return None
        if isinstance(value, datetime):
            return value
        if isinstance(value, date):
            return datetime.combine(value, datetime.min.time())
        if isinstance(value, str):
            val = value.strip()
            if " to " in val:
                val = val.split(" to ")[1].strip()
            try:
                return datetime.fromisoformat(val.replace("Z", "+00:00"))
            except ValueError:
                pass
            try:
                return datetime.strptime(val[:10], "%Y-%m-%d")
            except ValueError:
                pass
        return None


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
    payment_method: PaymentMethod | None = Field(None, alias="paymentMethod")
    cart_items: list[CartItemSchema] = Field(..., min_length=1, alias="cartItems")
    subtotal: Decimal = Field(..., ge=0)
    total: Decimal = Field(..., ge=0)
    currency: CurrencyCode = CurrencyCode.USD


class BookingInquiryCreate(BookingInquiryBase):
    """Schema for creating a booking inquiry.

    `subtotal` and `total` are accepted for older clients but ignored: the
    server computes them from the cart (FLOW-3).
    """
    subtotal: Decimal | None = Field(None, ge=0)
    total: Decimal | None = Field(None, ge=0)


class QuoteRequestCreate(BaseModel):
    """A custom-quote request: no cart, no payment (FLOW-4)."""
    model_config = ConfigDict(populate_by_name=True)

    first_name: str = Field(..., min_length=1, max_length=100, alias="firstName")
    last_name: str = Field(..., min_length=1, max_length=100, alias="lastName")
    email: EmailStr
    phone: str = Field(..., min_length=1, max_length=20)
    nationality: str = Field("", max_length=100)
    number_of_travelers: int = Field(..., ge=1, le=50, alias="numberOfTravelers")
    listing_id: str = Field(..., min_length=1, max_length=100, alias="listingId")
    listing_title: str = Field(..., min_length=1, max_length=200, alias="listingTitle")
    preferred_date: datetime | None = Field(None, alias="preferredDate")
    message: str | None = Field(None, max_length=1000)
    currency: CurrencyCode = CurrencyCode.USD


class InquiryCancelRequest(BaseModel):
    """Guest cancellation: the reference plus the email used to book proves ownership."""
    email: EmailStr


class BookingInquiryResponse(BaseModel):
    """Schema for booking inquiry response"""
    id: UUID
    reference: str
    status: InquiryStatus
    created_at: datetime
    # Server-computed amounts (FLOW-3), so the confirmation shows the real figure.
    subtotal: Decimal | None = None
    taxes: Decimal | None = None
    total: Decimal | None = None
    currency: CurrencyCode | None = None
    payment_method: PaymentMethod | None = None
    
    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True,
        json_encoders={
            datetime: lambda v: v.isoformat(),
            Decimal: lambda v: float(v)
        }
    )


class PublicCartLine(BaseModel):
    """A cart line as shown to someone who only knows the reference (no vendor or contact data)."""
    model_config = ConfigDict(populate_by_name=True)

    listing_id: str = Field(..., alias="listingId")
    title: str
    travel_date: str | None = Field(None, alias="travelDate")
    travel_date_end: str | None = Field(None, alias="travelDateEnd")
    travel_count: int = Field(1, alias="travelCount")
    price: Decimal
    base_currency: str = Field("USD", alias="baseCurrency")
    selected_rooms: list[Any] | None = Field(None, alias="selectedRooms")


class BookingInquiryPublicView(BaseModel):
    """What the confirmation / tracking page shows for a reference: status and amounts, no phone or email."""
    model_config = ConfigDict(
        populate_by_name=True,
        json_encoders={datetime: lambda v: v.isoformat(), Decimal: lambda v: float(v)},
    )

    id: UUID
    reference: str
    status: InquiryStatus
    created_at: datetime
    first_name: str = Field(..., alias="firstName")
    number_of_travelers: int = Field(..., alias="numberOfTravelers")
    cart_items: list[PublicCartLine] = Field(..., alias="cartItems")
    subtotal: Decimal
    taxes: Decimal
    total: Decimal
    currency: CurrencyCode
    payment_method: PaymentMethod | None = Field(None, alias="paymentMethod")
    payment_status: str | None = None


class BookingInquiryDetailed(BookingInquiryBase):
    """Detailed schema for booking inquiry with all fields"""
    id: UUID
    reference: str
    status: InquiryStatus
    created_at: datetime
    updated_at: datetime
    vendor_id: str | None = Field(None, alias="vendorId")
    vendor_name: str | None = Field(None, alias="vendorName")
    vendor_email: str | None = Field(None, alias="vendorEmail")
    vendor_role: str | None = Field(None, alias="vendorRole")
    # Latest online payment status (initiated, pending, succeeded, ...), or None if never started.
    payment_status: str | None = None
    
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