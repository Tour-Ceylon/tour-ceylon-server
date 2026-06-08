from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


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
    base_price: Decimal | None = Field(default=None, alias="basePrice", ge=0, json_schema_extra={"format": "decimal"})
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
    room_types: list[StayRoomTypeInput] = Field(alias="roomTypes", min_length=0)
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
    max_guests: int | None = Field(default=None, alias="maxGuests")  # Fixed: should be int, not str
    base_price: Decimal | None = Field(default=None, alias="basePrice")
    currency: str
    bed_configuration: dict = Field(default_factory=dict, alias="bedConfiguration")
    bathroom: dict = Field(default_factory=dict)
    discounts: list[dict] = Field(default_factory=list)
    room_units: list[StayRoomUnitResponse] = Field(default_factory=list, alias="roomUnits")

    model_config = ConfigDict(from_attributes=True, populate_by_name=True, serialize_by_alias=True)


class StayPropertyResponse(BaseModel):
    id: UUID
    vendor_id: UUID = Field(alias="vendorId")
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
    contact: dict = Field(default_factory=dict)
    policies: dict = Field(default_factory=dict)
    media: list[dict] = Field(default_factory=list)
    metadata_json: dict = Field(default_factory=dict, validation_alias="metadata_json", serialization_alias="metadata", exclude_none=True)
    amenities: list[StayAmenityResponse] = Field(default_factory=list)
    room_types: list[StayRoomTypeResponse] = Field(default_factory=list, alias="roomTypes")
    created_at: datetime = Field(alias="createdAt")
    updated_at: datetime = Field(alias="updatedAt")

    model_config = ConfigDict(from_attributes=True, populate_by_name=True, serialize_by_alias=True)


class StayPropertyListResponse(BaseModel):
    properties: list[StayPropertyResponse]
    total: int
