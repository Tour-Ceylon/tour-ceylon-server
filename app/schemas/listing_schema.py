from datetime import datetime, time
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.enum import (
    CurrencyCode,
    DestinationType,
    ListingStatus,
    ListingType,
    PropertyType,
    SafariType,
    MediaType,
    TransferLocationType,
)


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


class HotelDetailBase(BaseModel):
    property_type: PropertyType
    star_rating: int
    check_in_time: time
    check_out_time: time
    child_policy: str | None = None


class HotelDetailUpdate(BaseModel):
    property_type: PropertyType | None = None
    star_rating: int | None = None
    check_in_time: time | None = None
    check_out_time: time | None = None
    child_policy: str | None = None


class HotelDetailResponse(HotelDetailBase):
    id: UUID

    model_config = ConfigDict(from_attributes=True)


class TourDetailBase(BaseModel):
    duration_days: int
    route_summary: str
    meeting_point: str


class TourDetailUpdate(BaseModel):
    duration_days: int | None = None
    route_summary: str | None = None
    meeting_point: str | None = None


class TourDetailResponse(TourDetailBase):
    id: UUID
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class SafariDetailBase(BaseModel):
    national_park: str
    safari_type: SafariType
    duration_minutes: int
    guide_included: bool
    pickup_supported: bool = False


class SafariDetailUpdate(BaseModel):
    national_park: str | None = None
    safari_type: SafariType | None = None
    duration_minutes: int | None = None
    guide_included: bool | None = None
    pickup_supported: bool | None = None


class SafariDetailResponse(SafariDetailBase):
    id: UUID

    model_config = ConfigDict(from_attributes=True)


class TransferDetailBase(BaseModel):
    origin_type: TransferLocationType
    destination_type: DestinationType
    vehicle_policy: str


class TransferDetailUpdate(BaseModel):
    origin_type: TransferLocationType | None = None
    destination_type: DestinationType | None = None
    vehicle_policy: str | None = None


class TransferDetailResponse(TransferDetailBase):
    id: UUID

    model_config = ConfigDict(from_attributes=True)


class ListingMediaBase(BaseModel):
    url: str = Field(min_length=1)
    alt_text: str = Field(min_length=1)
    sort_order: int
    is_cover: bool = False
    media_type: MediaType = MediaType.IMAGE


class ListingMediaCreate(ListingMediaBase):
    pass


class ListingMediaResponse(ListingMediaBase):
    id: UUID
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ListingBase(CoordinateMixin):
    listing_type: ListingType
    destination_id: UUID
    title: str
    slug: str | None = None
    description: str | None = None
    status: ListingStatus = ListingStatus.DRAFT
    base_currency: CurrencyCode = CurrencyCode.LKR
    is_active: bool = True
    hotel_detail: HotelDetailBase | None = None
    tour_detail: TourDetailBase | None = None
    safari_detail: SafariDetailBase | None = None
    transfer_detail: TransferDetailBase | None = None
    media: list[ListingMediaCreate] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_matching_detail(self):
        detail_fields = {
            ListingType.HOTEL: self.hotel_detail,
            ListingType.TOUR: self.tour_detail,
            ListingType.SAFARI: self.safari_detail,
            ListingType.TRANSFER: self.transfer_detail,
        }
        expected_detail = detail_fields[self.listing_type]
        if expected_detail is None:
            raise ValueError(f"{self.listing_type.value} listings require the matching detail payload")

        mismatched = [
            name
            for name, detail in {
                "hotel_detail": self.hotel_detail,
                "tour_detail": self.tour_detail,
                "safari_detail": self.safari_detail,
                "transfer_detail": self.transfer_detail,
            }.items()
            if detail is not None
        ]
        if len(mismatched) > 1:
            raise ValueError("only one detail payload can be provided")
        return self

    @model_validator(mode="after")
    def validate_media_cover(self):
        if sum(1 for media in self.media if media.is_cover) > 1:
            raise ValueError("only one media item can be marked as cover")
        return self


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
    hotel_detail: HotelDetailUpdate | None = None
    tour_detail: TourDetailUpdate | None = None
    safari_detail: SafariDetailUpdate | None = None
    transfer_detail: TransferDetailUpdate | None = None
    media: list[ListingMediaCreate] | None = None

    @model_validator(mode="after")
    def validate_single_detail_payload(self):
        populated = [
            name
            for name, detail in {
                "hotel_detail": self.hotel_detail,
                "tour_detail": self.tour_detail,
                "safari_detail": self.safari_detail,
                "transfer_detail": self.transfer_detail,
            }.items()
            if detail is not None
        ]
        if len(populated) > 1:
            raise ValueError("only one detail payload can be provided")
        return self

    @model_validator(mode="after")
    def validate_media_cover(self):
        if self.media is not None and sum(1 for media in self.media if media.is_cover) > 1:
            raise ValueError("only one media item can be marked as cover")
        return self


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
    hotel_detail: HotelDetailResponse | None = None
    tour_detail: TourDetailResponse | None = None
    safari_detail: SafariDetailResponse | None = None
    transfer_detail: TransferDetailResponse | None = None
    media: list[ListingMediaResponse] = Field(default_factory=list)
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
    status: ListingStatus | None = None
    is_active: bool | None = None
    page: int = 1
    per_page: int = 20
