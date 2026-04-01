from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.enum import CurrencyCode, DestinationType, ListingStatus, ListingType


class DestinationMapResponse(BaseModel):
    id: UUID
    name: str
    destination_type: DestinationType
    latitude: float | None = None
    longitude: float | None = None

    model_config = ConfigDict(from_attributes=True)


class CoordinateMixin(BaseModel):
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)

    @model_validator(mode="after")
    def validate_coordinate_pair(self):
        if (self.latitude is None) != (self.longitude is None):
            raise ValueError("latitude and longitude must be provided together")
        return self


class ListingBase(CoordinateMixin):
    listing_type: ListingType
    destination_id: UUID
    title: str
    slug: str | None = None
    description: str | None = None
    status: ListingStatus = ListingStatus.DRAFT
    base_currency: CurrencyCode = CurrencyCode.LKR
    is_active: bool = True


class ListingCreate(ListingBase):
    pass


class ListingUpdate(CoordinateMixin):
    listing_type: ListingType | None = None
    destination_id: UUID | None = None
    title: str | None = None
    slug: str | None = None
    description: str | None = None
    status: ListingStatus | None = None
    base_currency: CurrencyCode | None = None
    is_active: bool | None = None


class ListingResponse(BaseModel):
    id: UUID
    listing_type: ListingType
    destination_id: UUID
    title: str
    slug: str | None = None
    description: str | None = None
    status: ListingStatus
    base_currency: CurrencyCode
    is_active: bool
    latitude: float | None = None
    longitude: float | None = None
    destination: DestinationMapResponse | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ListingInDB(ListingResponse):
    pass


class ListingListResponse(BaseModel):
    listings: list[ListingResponse]
    total: int
    page: int
    per_page: int
    total_pages: int


class ListingSearchParams(BaseModel):
    listing_type: ListingType | None = None
    destination_id: UUID | None = None
    title: str | None = None
    base_currency: CurrencyCode | None = None
    is_active: bool | None = None
    page: int = 1
    per_page: int = 20
