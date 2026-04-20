from datetime import datetime, time
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.models.enum import (
    BookingUnit,
    CurrencyCode,
    DestinationType,
    ListingStatus,
    ListingType,
    PropertyType,
    SafariType,
    MediaType,
    TransferLocationType,
)
from app.schemas.media_schema import MediaAssetPublicResponse, MediaSummary


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
    property_name: str | None = None
    short_location: str | None = None
    address_line_1: str | None = None
    address_line_2: str | None = None
    city: str | None = None
    district: str | None = None
    postal_code: str | None = None
    contact_phone: str | None = None
    contact_email: str | None = None
    website: str | None = None
    google_map_url: str | None = None
    amenities: list[str] = Field(default_factory=list)
    languages_spoken: list[str] = Field(default_factory=list)
    room_count: int | None = None
    max_guest_capacity: int | None = None
    meal_plans: list[str] = Field(default_factory=list)
    parking_available: bool | None = None
    wifi_available: bool | None = None
    pets_allowed: bool | None = None
    smoking_policy: str | None = None
    cancellation_policy: str | None = None
    extra_bed_policy: str | None = None
    check_in_notes: str | None = None
    check_out_notes: str | None = None

    @field_validator("amenities", "languages_spoken", "meal_plans", mode="before")
    @classmethod
    def default_empty_lists(cls, value):
        if value is None:
            return []
        return value


class HotelDetailUpdate(BaseModel):
    property_type: PropertyType | None = None
    star_rating: int | None = None
    check_in_time: time | None = None
    check_out_time: time | None = None
    child_policy: str | None = None
    property_name: str | None = None
    short_location: str | None = None
    address_line_1: str | None = None
    address_line_2: str | None = None
    city: str | None = None
    district: str | None = None
    postal_code: str | None = None
    contact_phone: str | None = None
    contact_email: str | None = None
    website: str | None = None
    google_map_url: str | None = None
    amenities: list[str] | None = None
    languages_spoken: list[str] | None = None
    room_count: int | None = None
    max_guest_capacity: int | None = None
    meal_plans: list[str] | None = None
    parking_available: bool | None = None
    wifi_available: bool | None = None
    pets_allowed: bool | None = None
    smoking_policy: str | None = None
    cancellation_policy: str | None = None
    extra_bed_policy: str | None = None
    check_in_notes: str | None = None
    check_out_notes: str | None = None


class HotelDetailResponse(HotelDetailBase):
    id: UUID

    model_config = ConfigDict(from_attributes=True)


class TourDetailBase(BaseModel):
    duration_days: int
    route_summary: str
    meeting_point: str
    itinerary_highlights: list[str] = Field(default_factory=list)
    included_items: list[str] = Field(default_factory=list)
    excluded_items: list[str] = Field(default_factory=list)
    languages: list[str] = Field(default_factory=list)
    difficulty_level: str | None = None
    group_size_min: int | None = None
    group_size_max: int | None = None
    private_available: bool | None = None
    pickup_available: bool | None = None
    dropoff_available: bool | None = None
    pickup_notes: str | None = None
    dropoff_notes: str | None = None
    start_time: time | None = None
    end_time: time | None = None
    cancellation_policy: str | None = None
    what_to_bring: list[str] = Field(default_factory=list)
    child_policy: str | None = None
    accessibility_info: str | None = None

    @field_validator(
        "itinerary_highlights",
        "included_items",
        "excluded_items",
        "languages",
        "what_to_bring",
        mode="before",
    )
    @classmethod
    def default_empty_lists(cls, value):
        if value is None:
            return []
        return value


class TourDetailUpdate(BaseModel):
    duration_days: int | None = None
    route_summary: str | None = None
    meeting_point: str | None = None
    itinerary_highlights: list[str] | None = None
    included_items: list[str] | None = None
    excluded_items: list[str] | None = None
    languages: list[str] | None = None
    difficulty_level: str | None = None
    group_size_min: int | None = None
    group_size_max: int | None = None
    private_available: bool | None = None
    pickup_available: bool | None = None
    dropoff_available: bool | None = None
    pickup_notes: str | None = None
    dropoff_notes: str | None = None
    start_time: time | None = None
    end_time: time | None = None
    cancellation_policy: str | None = None
    what_to_bring: list[str] | None = None
    child_policy: str | None = None
    accessibility_info: str | None = None


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
    start_time: time | None = None
    end_time: time | None = None
    included_items: list[str] = Field(default_factory=list)
    excluded_items: list[str] = Field(default_factory=list)
    languages: list[str] = Field(default_factory=list)
    difficulty_level: str | None = None
    age_restriction: str | None = None
    private_available: bool | None = None
    group_size_min: int | None = None
    group_size_max: int | None = None
    pickup_notes: str | None = None
    what_to_bring: list[str] = Field(default_factory=list)
    cancellation_policy: str | None = None
    accessibility_info: str | None = None
    best_season: str | None = None
    wildlife_highlights: list[str] = Field(default_factory=list)

    @field_validator(
        "included_items",
        "excluded_items",
        "languages",
        "what_to_bring",
        "wildlife_highlights",
        mode="before",
    )
    @classmethod
    def default_empty_lists(cls, value):
        if value is None:
            return []
        return value


class SafariDetailUpdate(BaseModel):
    national_park: str | None = None
    safari_type: SafariType | None = None
    duration_minutes: int | None = None
    guide_included: bool | None = None
    pickup_supported: bool | None = None
    start_time: time | None = None
    end_time: time | None = None
    included_items: list[str] | None = None
    excluded_items: list[str] | None = None
    languages: list[str] | None = None
    difficulty_level: str | None = None
    age_restriction: str | None = None
    private_available: bool | None = None
    group_size_min: int | None = None
    group_size_max: int | None = None
    pickup_notes: str | None = None
    what_to_bring: list[str] | None = None
    cancellation_policy: str | None = None
    accessibility_info: str | None = None
    best_season: str | None = None
    wildlife_highlights: list[str] | None = None


class SafariDetailResponse(SafariDetailBase):
    id: UUID

    model_config = ConfigDict(from_attributes=True)


class TransferDetailBase(BaseModel):
    origin_type: TransferLocationType
    destination_type: DestinationType
    vehicle_policy: str
    vehicle_types: list[str] = Field(default_factory=list)
    max_passengers: int | None = None
    max_luggage: int | None = None
    air_conditioned: bool | None = None
    meet_and_greet_included: bool | None = None
    child_seats_available: bool | None = None
    pickup_instructions: str | None = None
    dropoff_instructions: str | None = None
    operating_start_time: time | None = None
    operating_end_time: time | None = None
    estimated_duration_minutes: int | None = None
    route_notes: str | None = None
    included_items: list[str] = Field(default_factory=list)
    excluded_items: list[str] = Field(default_factory=list)
    cancellation_policy: str | None = None
    waiting_time_policy: str | None = None

    @field_validator("vehicle_types", "included_items", "excluded_items", mode="before")
    @classmethod
    def default_empty_lists(cls, value):
        if value is None:
            return []
        return value


class TransferDetailUpdate(BaseModel):
    origin_type: TransferLocationType | None = None
    destination_type: DestinationType | None = None
    vehicle_policy: str | None = None
    vehicle_types: list[str] | None = None
    max_passengers: int | None = None
    max_luggage: int | None = None
    air_conditioned: bool | None = None
    meet_and_greet_included: bool | None = None
    child_seats_available: bool | None = None
    pickup_instructions: str | None = None
    dropoff_instructions: str | None = None
    operating_start_time: time | None = None
    operating_end_time: time | None = None
    estimated_duration_minutes: int | None = None
    route_notes: str | None = None
    included_items: list[str] | None = None
    excluded_items: list[str] | None = None
    cancellation_policy: str | None = None
    waiting_time_policy: str | None = None


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


class ListingVariantPricingResponse(BaseModel):
    amount: float
    currency: CurrencyCode
    priority: int


class ListingVariantPricingInput(ListingVariantPricingResponse):
    pass


class ListingVariantCreate(BaseModel):
    name: str
    booking_unit: BookingUnit
    capacity_min: int | None = None
    capacity_max: int | None = None
    is_default: bool = False
    pricing: ListingVariantPricingInput

    @model_validator(mode="after")
    def validate_capacity_range(self):
        if (
            self.capacity_min is not None
            and self.capacity_max is not None
            and self.capacity_min > self.capacity_max
        ):
            raise ValueError("capacity_min cannot be greater than capacity_max")
        return self


class ListingVariantResponse(BaseModel):
    id: UUID
    name: str
    booking_unit: BookingUnit
    capacity_min: int | None = None
    capacity_max: int | None = None
    is_default: bool
    pricing: ListingVariantPricingResponse | None = None

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
    variants: list[ListingVariantCreate] = Field(default_factory=list)
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
    def validate_variants(self):
        if self.listing_type == ListingType.HOTEL:
            if not self.variants:
                raise ValueError("hotel listings require at least one variant")
            if any(variant.booking_unit != BookingUnit.PER_ROOM for variant in self.variants):
                raise ValueError("hotel variants must use per_room booking")
        if self.variants and sum(1 for variant in self.variants if variant.is_default) != 1:
            raise ValueError("exactly one variant must be marked as default")
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
    variants: list[ListingVariantCreate] | None = None
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
    def validate_variants(self):
        if self.variants is None:
            return self
        if not self.variants:
            raise ValueError("at least one variant is required")
        if sum(1 for variant in self.variants if variant.is_default) != 1:
            raise ValueError("exactly one variant must be marked as default")
        return self

    @model_validator(mode="after")
    def validate_media_cover(self):
        if self.media is not None and sum(1 for media in self.media if media.is_cover) > 1:
            raise ValueError("only one media item can be marked as cover")
        return self


class ListingFromPriceResponse(ListingVariantPricingResponse):
    variant_id: UUID
    variant_name: str
    booking_unit: BookingUnit


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
    variants: list[ListingVariantResponse] = Field(default_factory=list)
    from_price: ListingFromPriceResponse | None = None
    cover_image: MediaSummary | None = None
    gallery: list[MediaAssetPublicResponse] = Field(default_factory=list)
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
