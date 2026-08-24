from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.enum import StayBookingStatus, StayRoomBlockStatus, StayRoomBlockType


class StayAmenityInput(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    value: bool | str | int | float | list[str] | dict = True
    category: str | None = None
    description: str | None = None
    value_type: str = Field(default="boolean", alias="valueType")

    model_config = ConfigDict(populate_by_name=True, serialize_by_alias=True)


class StayRoomTypeInput(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    description: str | None = None
    count: int = Field(default=1, ge=1)
    unit_prefix: str | None = Field(default=None, alias="unitPrefix")
    floor: str | None = None
    size: str | None = None
    size_unit: str | None = Field(default=None, alias="sizeUnit")
    max_guests: int | None = Field(default=None, alias="maxGuests", ge=1)
    base_price: Decimal | None = Field(default=None, alias="basePrice", ge=0)
    currency: str = "LKR"
    smoking: bool | None = None
    guest_access: bool | None = Field(default=None, alias="guestAccess")
    bed_configuration: dict = Field(default_factory=dict, alias="bedConfiguration")
    bathroom: dict = Field(default_factory=dict)
    discounts: list[dict] = Field(default_factory=list)
    room_units: list[str] | None = Field(default=None, alias="roomUnits")
    metadata: dict = Field(default_factory=dict)

    model_config = ConfigDict(populate_by_name=True, serialize_by_alias=True)


class StayPropertyCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    property_type: str = Field(alias="propertyType", min_length=1, max_length=80)
    description: str | None = None
    address: str | None = None
    city: str | None = None
    district: str | None = None
    latitude: Decimal | None = None
    longitude: Decimal | None = None
    status: str = "submitted"
    application_note: str | None = Field(default=None, alias="applicationNote")
    contact: dict = Field(default_factory=dict)
    policies: dict = Field(default_factory=dict)
    media: list[dict] = Field(default_factory=list)
    amenities: list[StayAmenityInput] = Field(default_factory=list)
    room_types: list[StayRoomTypeInput] = Field(alias="roomTypes", min_length=1)
    metadata: dict = Field(default_factory=dict)

    model_config = ConfigDict(populate_by_name=True, serialize_by_alias=True)

    @model_validator(mode="after")
    def validate_coordinate_pair(self):
        if (self.latitude is None) != (self.longitude is None):
            raise ValueError("latitude and longitude must be provided together")
        return self


class StayAmenityResponse(BaseModel):
    id: UUID
    name: str
    flattened_value: bool | str | int | float | list | dict | None = Field(default=None, alias="value")
    category: str | None = None
    value_type: str = Field(alias="valueType")

    model_config = ConfigDict(from_attributes=True, populate_by_name=True, serialize_by_alias=True)


class StayRoomUnitResponse(BaseModel):
    id: UUID
    room_number: str = Field(alias="roomNumber")
    floor: str | None = None
    room_name: str | None = Field(default=None, alias="roomName")
    status: str

    model_config = ConfigDict(from_attributes=True, populate_by_name=True, serialize_by_alias=True)


class StayRoomTypeResponse(BaseModel):
    id: UUID
    name: str
    description: str | None = None
    size: str | None = None
    size_unit: str | None = Field(default=None, alias="sizeUnit")
    max_guests: str | None = Field(default=None, alias="maxGuests")
    base_price: Decimal | None = Field(default=None, alias="basePrice")
    currency: str
    bed_configuration: dict = Field(alias="bedConfiguration")
    bathroom: dict
    discounts: list[dict]
    room_units: list[StayRoomUnitResponse] = Field(default_factory=list, alias="roomUnits")

    model_config = ConfigDict(from_attributes=True, populate_by_name=True, serialize_by_alias=True)


class StayPropertyResponse(BaseModel):
    id: UUID
    vendor_id: UUID | None = Field(default=None, alias="vendorId")
    listing_id: UUID | None = Field(default=None, alias="listingId")
    name: str
    property_type: str = Field(alias="propertyType")
    description: str | None = None
    address: str | None = None
    city: str | None = None
    district: str | None = None
    latitude: Decimal | None = None
    longitude: Decimal | None = None
    status: str
    application_note: str | None = Field(default=None, alias="applicationNote")
    contact: dict
    policies: dict
    media: list[dict]
    metadata_json: dict = Field(validation_alias="metadata_json", serialization_alias="metadata")
    amenities: list[StayAmenityResponse] = Field(default_factory=list)
    room_types: list[StayRoomTypeResponse] = Field(default_factory=list, alias="roomTypes")
    created_at: datetime = Field(alias="createdAt")
    updated_at: datetime = Field(alias="updatedAt")

    model_config = ConfigDict(from_attributes=True, populate_by_name=True, serialize_by_alias=True)


class StayPropertyListResponse(BaseModel):
    properties: list[StayPropertyResponse]
    total: int


class StayPropertyUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    property_type: str | None = Field(default=None, alias="propertyType", min_length=1, max_length=80)
    description: str | None = None
    address: str | None = None
    city: str | None = None
    district: str | None = None
    latitude: Decimal | None = None
    longitude: Decimal | None = None
    status: str | None = None
    application_note: str | None = Field(default=None, alias="applicationNote")
    contact: dict | None = None
    policies: dict | None = None
    media: list[dict] | None = None
    amenities: list[StayAmenityInput] | None = None
    metadata: dict | None = None

    model_config = ConfigDict(populate_by_name=True, serialize_by_alias=True)

    @model_validator(mode="after")
    def validate_coordinate_pair(self):
        if (self.latitude is None) != (self.longitude is None):
            raise ValueError("latitude and longitude must be provided together")
        return self


class StayRoomTypeCreate(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    description: str | None = None
    size: str | None = None
    size_unit: str | None = Field(default=None, alias="sizeUnit")
    max_guests: int | None = Field(default=None, alias="maxGuests", ge=1)
    base_price: Decimal | None = Field(default=None, alias="basePrice", ge=0)
    currency: str = "LKR"
    bed_configuration: dict = Field(default_factory=dict, alias="bedConfiguration")
    bathroom: dict = Field(default_factory=dict)
    discounts: list[dict] = Field(default_factory=list)
    metadata: dict = Field(default_factory=dict)

    model_config = ConfigDict(populate_by_name=True, serialize_by_alias=True)


class StayRoomTypeUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=160)
    description: str | None = None
    size: str | None = None
    size_unit: str | None = Field(default=None, alias="sizeUnit")
    max_guests: int | None = Field(default=None, alias="maxGuests", ge=1)
    base_price: Decimal | None = Field(default=None, alias="basePrice", ge=0)
    currency: str | None = None
    bed_configuration: dict | None = Field(default=None, alias="bedConfiguration")
    bathroom: dict | None = None
    discounts: list[dict] | None = None
    metadata: dict | None = None

    model_config = ConfigDict(populate_by_name=True, serialize_by_alias=True)


class StayRoomUnitCreate(BaseModel):
    room_type_id: UUID = Field(alias="roomTypeId")
    room_number: str = Field(alias="roomNumber", min_length=1, max_length=80)
    floor: str | None = None
    room_name: str | None = Field(default=None, alias="roomName")
    status: str = "available"
    metadata: dict = Field(default_factory=dict)

    model_config = ConfigDict(populate_by_name=True, serialize_by_alias=True)


class StayRoomUnitUpdate(BaseModel):
    room_type_id: UUID | None = Field(default=None, alias="roomTypeId")
    room_number: str | None = Field(default=None, alias="roomNumber", min_length=1, max_length=80)
    floor: str | None = None
    room_name: str | None = Field(default=None, alias="roomName")
    status: str | None = None
    metadata: dict | None = None

    model_config = ConfigDict(populate_by_name=True, serialize_by_alias=True)


class StayRoomBlockCreate(BaseModel):
    room_unit_id: UUID = Field(alias="roomUnitId")
    start_date: date = Field(alias="startDate")
    end_date: date = Field(alias="endDate")
    block_type: StayRoomBlockType = Field(default=StayRoomBlockType.MANUAL, alias="blockType")
    reason: str | None = None
    metadata: dict = Field(default_factory=dict)

    model_config = ConfigDict(populate_by_name=True, serialize_by_alias=True)

    @model_validator(mode="after")
    def validate_date_range(self):
        if self.end_date <= self.start_date:
            raise ValueError("endDate must be after startDate")
        return self


class StayRoomBlockResponse(BaseModel):
    id: UUID
    property_id: UUID = Field(alias="propertyId")
    room_unit_id: UUID = Field(alias="roomUnitId")
    start_date: date = Field(alias="startDate")
    end_date: date = Field(alias="endDate")
    block_type: StayRoomBlockType = Field(alias="blockType")
    status: StayRoomBlockStatus
    reason: str | None = None
    blocked_by_user_id: UUID | None = Field(default=None, alias="blockedByUserId")
    metadata_json: dict = Field(validation_alias="metadata_json", serialization_alias="metadata")

    model_config = ConfigDict(from_attributes=True, populate_by_name=True, serialize_by_alias=True)


class StayRoomBlockListResponse(BaseModel):
    blocks: list[StayRoomBlockResponse] = Field(default_factory=list)
    total: int

    model_config = ConfigDict(populate_by_name=True, serialize_by_alias=True)


class StayRoomTypeInventoryResponse(StayRoomTypeResponse):
    total_units: int = Field(default=0, alias="totalUnits")


class StayInventoryResponse(BaseModel):
    property_id: UUID = Field(alias="propertyId")
    room_types: list[StayRoomTypeInventoryResponse] = Field(default_factory=list, alias="roomTypes")
    room_units: list[StayRoomUnitResponse] = Field(default_factory=list, alias="roomUnits")

    model_config = ConfigDict(populate_by_name=True, serialize_by_alias=True)


class StayAvailabilityNightResponse(BaseModel):
    date: date
    total_units: int = Field(alias="totalUnits")
    booked_units: int = Field(alias="bookedUnits")
    blocked_units: int = Field(alias="blockedUnits")
    available_units: int = Field(alias="availableUnits")
    nightly_price: Decimal | None = Field(default=None, alias="nightlyPrice")

    model_config = ConfigDict(populate_by_name=True, serialize_by_alias=True)


class StayAvailabilityRoomTypeResponse(BaseModel):
    room_type_id: UUID = Field(alias="roomTypeId")
    room_type_name: str = Field(alias="roomTypeName")
    available_count: int = Field(alias="availableCount")
    nightly_prices: list[StayAvailabilityNightResponse] = Field(default_factory=list, alias="nightlyPrices")
    total_price: Decimal = Field(alias="totalPrice")
    cancellation_info: dict | None = Field(default=None, alias="cancellationInfo")
    max_guests: int | None = Field(default=None, alias="maxGuests")

    model_config = ConfigDict(populate_by_name=True, serialize_by_alias=True)


class StayAvailabilitySearchRequest(BaseModel):
    property_id: UUID = Field(alias="propertyId")
    check_in_date: date = Field(alias="checkInDate")
    check_out_date: date = Field(alias="checkOutDate")
    guests: int = Field(ge=1)
    room_type_id: UUID | None = Field(default=None, alias="roomTypeId")

    model_config = ConfigDict(populate_by_name=True, serialize_by_alias=True)

    @model_validator(mode="after")
    def validate_date_range(self):
        if self.check_out_date <= self.check_in_date:
            raise ValueError("checkOutDate must be after checkInDate")
        return self


class StayAvailabilitySearchResponse(BaseModel):
    property_id: UUID = Field(alias="propertyId")
    check_in_date: date = Field(alias="checkInDate")
    check_out_date: date = Field(alias="checkOutDate")
    room_types: list[StayAvailabilityRoomTypeResponse] = Field(default_factory=list, alias="roomTypes")

    model_config = ConfigDict(populate_by_name=True, serialize_by_alias=True)


class StayBookingItemCreate(BaseModel):
    room_type_id: UUID = Field(alias="roomTypeId")
    room_count: int = Field(alias="roomCount", ge=1)
    guests: int = Field(ge=1)
    travelers: list[dict] = Field(default_factory=list)

    model_config = ConfigDict(populate_by_name=True, serialize_by_alias=True)


class StayBookingCreate(BaseModel):
    user_id: UUID = Field(alias="userId")
    property_id: UUID = Field(alias="propertyId")
    check_in_date: date = Field(alias="checkInDate")
    check_out_date: date = Field(alias="checkOutDate")
    guest_name: str = Field(alias="guestName", min_length=1, max_length=255)
    guest_email: str | None = Field(default=None, alias="guestEmail")
    guest_phone: str | None = Field(default=None, alias="guestPhone")
    special_requests: str | None = Field(default=None, alias="specialRequests")
    items: list[StayBookingItemCreate] = Field(min_length=1)

    model_config = ConfigDict(populate_by_name=True, serialize_by_alias=True)

    @model_validator(mode="after")
    def validate_date_range(self):
        if self.check_out_date <= self.check_in_date:
            raise ValueError("checkOutDate must be after checkInDate")
        return self


class StayBookingRoomResponse(BaseModel):
    id: UUID
    room_unit_id: UUID = Field(alias="roomUnitId")
    room_type_id: UUID = Field(alias="roomTypeId")
    check_in_date: date = Field(alias="checkInDate")
    check_out_date: date = Field(alias="checkOutDate")
    nightly_rate: Decimal = Field(alias="nightlyRate")
    guests: int
    metadata_json: dict = Field(validation_alias="metadata_json", serialization_alias="metadata")

    model_config = ConfigDict(from_attributes=True, populate_by_name=True, serialize_by_alias=True)


class StayBookingResponse(BaseModel):
    id: UUID
    booking_id: UUID = Field(alias="bookingId")
    property_id: UUID = Field(alias="propertyId")
    status: StayBookingStatus
    check_in_date: date = Field(alias="checkInDate")
    check_out_date: date = Field(alias="checkOutDate")
    guest_name: str = Field(alias="guestName")
    guest_email: str | None = Field(default=None, alias="guestEmail")
    guest_phone: str | None = Field(default=None, alias="guestPhone")
    special_requests: str | None = Field(default=None, alias="specialRequests")
    metadata_json: dict = Field(validation_alias="metadata_json", serialization_alias="metadata")
    rooms: list[StayBookingRoomResponse] = Field(default_factory=list)
    created_at: datetime = Field(alias="createdAt")
    updated_at: datetime = Field(alias="updatedAt")

    model_config = ConfigDict(from_attributes=True, populate_by_name=True, serialize_by_alias=True)


class StayBookingListResponse(BaseModel):
    bookings: list[StayBookingResponse]
    total: int


class StayCalendarQuery(BaseModel):
    start_date: date = Field(alias="startDate")
    end_date: date = Field(alias="endDate")
    room_type_id: UUID | None = Field(default=None, alias="roomTypeId")

    model_config = ConfigDict(populate_by_name=True, serialize_by_alias=True)

    @model_validator(mode="after")
    def validate_date_range(self):
        if self.end_date < self.start_date:
            raise ValueError("endDate must be on or after startDate")
        return self


class StayCalendarResponse(BaseModel):
    property_id: UUID = Field(alias="propertyId")
    entries: list[StayAvailabilityNightResponse]

    model_config = ConfigDict(populate_by_name=True, serialize_by_alias=True)
