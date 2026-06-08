from datetime import date, datetime
from uuid import UUID
from pydantic import BaseModel, Field, ConfigDict, field_validator
from app.models.enum import AvailabilityStatus

class AvailabilityCreate(BaseModel):
    variant_id: UUID = Field(alias="variantId")
    start_date: date = Field(alias="startDate")
    end_date: date = Field(alias="endDate")
    total_capacity: int = Field(alias="totalCapacity", ge=0)
    available_status: AvailabilityStatus = Field(alias="availableStatus", default=AvailabilityStatus.OPEN)

    model_config = ConfigDict(populate_by_name=True, serialize_by_alias=True)

    @field_validator("available_status", mode="before")
    @classmethod
    def map_status(cls, value):
        if isinstance(value, str):
            val = value.strip().lower()
            if val in ("available", "open"):
                return AvailabilityStatus.OPEN
            if val in ("low", "limited"):
                return AvailabilityStatus.LIMITED
            if val in ("sold_out", "sold-out"):
                return AvailabilityStatus.SOLD_OUT
            if val == "blocked":
                return AvailabilityStatus.BLOCKED
            try:
                return AvailabilityStatus(val)
            except ValueError:
                pass
        return value

class AvailabilityUpdate(BaseModel):
    total_capacity: int = Field(alias="totalCapacity", ge=0)
    available_status: AvailabilityStatus = Field(alias="availableStatus")

    model_config = ConfigDict(populate_by_name=True, serialize_by_alias=True)

    @field_validator("available_status", mode="before")
    @classmethod
    def map_status(cls, value):
        if isinstance(value, str):
            val = value.strip().lower()
            if val in ("available", "open"):
                return AvailabilityStatus.OPEN
            if val in ("low", "limited"):
                return AvailabilityStatus.LIMITED
            if val in ("sold_out", "sold-out"):
                return AvailabilityStatus.SOLD_OUT
            if val == "blocked":
                return AvailabilityStatus.BLOCKED
            try:
                return AvailabilityStatus(val)
            except ValueError:
                pass
        return value

class AvailabilityResponse(BaseModel):
    id: UUID
    variant_id: UUID = Field(alias="variantId")
    service_date: datetime = Field(alias="serviceDate")
    total_capacity: int = Field(alias="totalCapacity")
    reserved_capacity: int = Field(alias="reservedCapacity")
    available_capacity: int = Field(alias="availableCapacity")
    available_status: AvailabilityStatus = Field(alias="availableStatus")

    model_config = ConfigDict(from_attributes=True, populate_by_name=True, serialize_by_alias=True)

class AvailabilityListResponse(BaseModel):
    availability: list[AvailabilityResponse]
    total: int
