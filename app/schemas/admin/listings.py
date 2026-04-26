from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.models.enum import BookingUnit, CurrencyCode, DestinationType, MediaType, PropertyType, SafariType, TransferLocationType
from app.schemas.media_schema import MediaAssetPublicResponse, MediaSummary


AdminListingCategory = Literal["stay", "tour", "safari", "experience", "transfer"]


class CoordinateMixin(BaseModel):
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)

    @model_validator(mode="after")
    def validate_coordinate_pair(self):
        if (self.latitude is None) != (self.longitude is None):
            raise ValueError("latitude and longitude must be provided together")
        return self


class DestinationRef(BaseModel):
    id: UUID
    name: str
    destination_type: DestinationType = Field(alias="destinationType")
    latitude: float | None = None
    longitude: float | None = None

    model_config = ConfigDict(from_attributes=True, populate_by_name=True, serialize_by_alias=True)


class AdminHotelDetail(BaseModel):
    property_type: PropertyType = Field(alias="propertyType")
    star_rating: int = Field(alias="starRating")
    check_in_time: str = Field(alias="checkInTime")
    check_out_time: str = Field(alias="checkOutTime")
    child_policy: str | None = Field(default=None, alias="childPolicy")
    property_name: str | None = Field(default=None, alias="propertyName")
    short_location: str | None = Field(default=None, alias="shortLocation")
    address_line_1: str | None = Field(default=None, alias="addressLine1")
    address_line_2: str | None = Field(default=None, alias="addressLine2")
    city: str | None = None
    district: str | None = None
    postal_code: str | None = Field(default=None, alias="postalCode")
    contact_phone: str | None = Field(default=None, alias="contactPhone")
    contact_email: str | None = Field(default=None, alias="contactEmail")
    website: str | None = None
    google_map_url: str | None = Field(default=None, alias="googleMapUrl")
    amenities: list[str] = Field(default_factory=list)
    languages_spoken: list[str] = Field(default_factory=list, alias="languagesSpoken")
    room_count: int | None = Field(default=None, alias="roomCount")
    max_guest_capacity: int | None = Field(default=None, alias="maxGuestCapacity")
    meal_plans: list[str] = Field(default_factory=list, alias="mealPlans")
    parking_available: bool | None = Field(default=None, alias="parkingAvailable")
    wifi_available: bool | None = Field(default=None, alias="wifiAvailable")
    pets_allowed: bool | None = Field(default=None, alias="petsAllowed")
    smoking_policy: str | None = Field(default=None, alias="smokingPolicy")
    cancellation_policy: str | None = Field(default=None, alias="cancellationPolicy")
    extra_bed_policy: str | None = Field(default=None, alias="extraBedPolicy")
    check_in_notes: str | None = Field(default=None, alias="checkInNotes")
    check_out_notes: str | None = Field(default=None, alias="checkOutNotes")

    model_config = ConfigDict(populate_by_name=True, serialize_by_alias=True)

    @field_validator("amenities", "languages_spoken", "meal_plans", mode="before")
    @classmethod
    def default_empty_lists(cls, value):
        if value is None:
            return []
        return value


class AdminTourDetail(BaseModel):
    duration_days: int = Field(alias="durationDays")
    route_summary: str = Field(alias="routeSummary")
    meeting_point: str = Field(alias="meetingPoint")
    itinerary_highlights: list[str] = Field(default_factory=list, alias="itineraryHighlights")
    included_items: list[str] = Field(default_factory=list, alias="includedItems")
    excluded_items: list[str] = Field(default_factory=list, alias="excludedItems")
    languages: list[str] = Field(default_factory=list)
    difficulty_level: str | None = Field(default=None, alias="difficultyLevel")
    group_size_min: int | None = Field(default=None, alias="groupSizeMin")
    group_size_max: int | None = Field(default=None, alias="groupSizeMax")
    private_available: bool | None = Field(default=None, alias="privateAvailable")
    pickup_available: bool | None = Field(default=None, alias="pickupAvailable")
    dropoff_available: bool | None = Field(default=None, alias="dropoffAvailable")
    pickup_notes: str | None = Field(default=None, alias="pickupNotes")
    dropoff_notes: str | None = Field(default=None, alias="dropoffNotes")
    start_time: str | None = Field(default=None, alias="startTime")
    end_time: str | None = Field(default=None, alias="endTime")
    cancellation_policy: str | None = Field(default=None, alias="cancellationPolicy")
    what_to_bring: list[str] = Field(default_factory=list, alias="whatToBring")
    child_policy: str | None = Field(default=None, alias="childPolicy")
    accessibility_info: str | None = Field(default=None, alias="accessibilityInfo")

    model_config = ConfigDict(populate_by_name=True, serialize_by_alias=True)

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


class AdminSafariDetail(BaseModel):
    national_park: str = Field(alias="nationalPark")
    safari_type: SafariType = Field(alias="safariType")
    duration_minutes: int = Field(alias="durationMinutes")
    guide_included: bool = Field(alias="guideIncluded")
    pickup_supported: bool = Field(default=False, alias="pickupSupported")
    start_time: str | None = Field(default=None, alias="startTime")
    end_time: str | None = Field(default=None, alias="endTime")
    included_items: list[str] = Field(default_factory=list, alias="includedItems")
    excluded_items: list[str] = Field(default_factory=list, alias="excludedItems")
    languages: list[str] = Field(default_factory=list)
    difficulty_level: str | None = Field(default=None, alias="difficultyLevel")
    age_restriction: str | None = Field(default=None, alias="ageRestriction")
    private_available: bool | None = Field(default=None, alias="privateAvailable")
    group_size_min: int | None = Field(default=None, alias="groupSizeMin")
    group_size_max: int | None = Field(default=None, alias="groupSizeMax")
    pickup_notes: str | None = Field(default=None, alias="pickupNotes")
    what_to_bring: list[str] = Field(default_factory=list, alias="whatToBring")
    cancellation_policy: str | None = Field(default=None, alias="cancellationPolicy")
    accessibility_info: str | None = Field(default=None, alias="accessibilityInfo")
    best_season: str | None = Field(default=None, alias="bestSeason")
    wildlife_highlights: list[str] = Field(default_factory=list, alias="wildlifeHighlights")

    model_config = ConfigDict(populate_by_name=True, serialize_by_alias=True)

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


class AdminTransferDetail(BaseModel):
    origin_type: TransferLocationType = Field(alias="originType")
    destination_type: DestinationType = Field(alias="destinationType")
    vehicle_policy: str = Field(alias="vehiclePolicy")
    vehicle_types: list[str] = Field(default_factory=list, alias="vehicleTypes")
    max_passengers: int | None = Field(default=None, alias="maxPassengers")
    max_luggage: int | None = Field(default=None, alias="maxLuggage")
    air_conditioned: bool | None = Field(default=None, alias="airConditioned")
    meet_and_greet_included: bool | None = Field(default=None, alias="meetAndGreetIncluded")
    child_seats_available: bool | None = Field(default=None, alias="childSeatsAvailable")
    pickup_instructions: str | None = Field(default=None, alias="pickupInstructions")
    dropoff_instructions: str | None = Field(default=None, alias="dropoffInstructions")
    operating_start_time: str | None = Field(default=None, alias="operatingStartTime")
    operating_end_time: str | None = Field(default=None, alias="operatingEndTime")
    estimated_duration_minutes: int | None = Field(default=None, alias="estimatedDurationMinutes")
    route_notes: str | None = Field(default=None, alias="routeNotes")
    included_items: list[str] = Field(default_factory=list, alias="includedItems")
    excluded_items: list[str] = Field(default_factory=list, alias="excludedItems")
    cancellation_policy: str | None = Field(default=None, alias="cancellationPolicy")
    waiting_time_policy: str | None = Field(default=None, alias="waitingTimePolicy")

    model_config = ConfigDict(populate_by_name=True, serialize_by_alias=True)

    @field_validator("vehicle_types", "included_items", "excluded_items", mode="before")
    @classmethod
    def default_empty_lists(cls, value):
        if value is None:
            return []
        return value


class AdminListingMedia(BaseModel):
    url: str = Field(min_length=1)
    alt_text: str = Field(alias="altText", min_length=1)
    sort_order: int = Field(alias="sortOrder")
    is_cover: bool = Field(default=False, alias="isCover")
    media_type: MediaType = Field(default=MediaType.IMAGE, alias="mediaType")

    model_config = ConfigDict(populate_by_name=True, serialize_by_alias=True)


class AdminListingMediaResponse(AdminListingMedia):
    id: UUID


class ListingVariantPriceInput(BaseModel):
    amount: float = Field(ge=0)
    currency: CurrencyCode
    priority: int = Field(ge=0)

    model_config = ConfigDict(use_enum_values=True)


class ListingVariantAdminInput(BaseModel):
    name: str = Field(min_length=1)
    booking_unit: BookingUnit = Field(alias="bookingUnit")
    capacity_min: int | None = Field(default=None, alias="capacityMin", ge=0)
    capacity_max: int | None = Field(default=None, alias="capacityMax", ge=0)
    is_default: bool = Field(default=False, alias="isDefault")
    pricing: ListingVariantPriceInput

    model_config = ConfigDict(populate_by_name=True, serialize_by_alias=True)

    @model_validator(mode="after")
    def validate_capacity_range(self):
        if (
            self.capacity_min is not None
            and self.capacity_max is not None
            and self.capacity_min > self.capacity_max
        ):
            raise ValueError("capacityMin cannot be greater than capacityMax")
        return self


class ListingVariantAdminResponse(BaseModel):
    id: UUID
    name: str
    booking_unit: BookingUnit = Field(alias="bookingUnit")
    capacity_min: int | None = Field(default=None, alias="capacityMin")
    capacity_max: int | None = Field(default=None, alias="capacityMax")
    is_default: bool = Field(default=False, alias="isDefault")
    pricing: ListingVariantPriceInput | None = None

    model_config = ConfigDict(populate_by_name=True, serialize_by_alias=True)


class ListingFromPriceResponse(ListingVariantPriceInput):
    variant_id: UUID = Field(alias="variantId")
    variant_name: str = Field(alias="variantName")
    booking_unit: BookingUnit = Field(alias="bookingUnit")

    model_config = ConfigDict(populate_by_name=True, serialize_by_alias=True)


class AdminListingBase(CoordinateMixin):
    destination_id: UUID = Field(alias="destinationId")
    title: str
    description: str | None = None
    is_active: bool = Field(default=True, alias="isActive")
    media: list[AdminListingMedia] = Field(default_factory=list)
    variants: list[ListingVariantAdminInput] = Field(default_factory=list)

    model_config = ConfigDict(populate_by_name=True, serialize_by_alias=True)

    @model_validator(mode="after")
    def validate_media_cover(self):
        if sum(1 for media in self.media if media.is_cover) > 1:
            raise ValueError("only one media item can be marked as cover")
        return self


class StayListingCreate(AdminListingBase):
    hotel_detail: AdminHotelDetail = Field(alias="hotelDetail")

    @model_validator(mode="after")
    def validate_variants(self):
        if not self.variants:
            raise ValueError("at least one variant is required")
        if sum(1 for variant in self.variants if variant.is_default) != 1:
            raise ValueError("exactly one variant must be marked as default")
        return self


class StayListingResponse(AdminListingBase):
    id: UUID
    category: Literal["stay"]
    destination: DestinationRef | None = None
    media: list[AdminListingMediaResponse] = Field(default_factory=list, exclude=True)
    from_price: ListingFromPriceResponse | None = Field(default=None, alias="fromPrice")
    cover_image: MediaSummary | None = None
    gallery: list[MediaAssetPublicResponse] = Field(default_factory=list)
    variants: list[ListingVariantAdminResponse] = Field(default_factory=list)
    hotel_detail: AdminHotelDetail | None = Field(default=None, alias="hotelDetail")


class TourListingCreate(AdminListingBase):
    tour_detail: AdminTourDetail = Field(alias="tourDetail")

    @model_validator(mode="after")
    def validate_variants(self):
        if not self.variants:
            raise ValueError("at least one variant is required")
        if sum(1 for variant in self.variants if variant.is_default) != 1:
            raise ValueError("exactly one variant must be marked as default")
        return self


class TourListingResponse(AdminListingBase):
    id: UUID
    category: Literal["tour"]
    destination: DestinationRef | None = None
    media: list[AdminListingMediaResponse] = Field(default_factory=list, exclude=True)
    from_price: ListingFromPriceResponse | None = Field(default=None, alias="fromPrice")
    cover_image: MediaSummary | None = None
    gallery: list[MediaAssetPublicResponse] = Field(default_factory=list)
    variants: list[ListingVariantAdminResponse] = Field(default_factory=list)
    tour_detail: AdminTourDetail | None = Field(default=None, alias="tourDetail")


class AdminActivityDetail(BaseModel):
    activity_type: str = Field(alias="activityType")
    duration_minutes: int = Field(alias="durationMinutes")
    meeting_point: str | None = Field(default=None, alias="meetingPoint")
    start_time: str | None = Field(default=None, alias="startTime")
    end_time: str | None = Field(default=None, alias="endTime")
    included_items: list[str] = Field(default_factory=list, alias="includedItems")
    excluded_items: list[str] = Field(default_factory=list, alias="excludedItems")
    languages: list[str] = Field(default_factory=list)
    difficulty_level: str | None = Field(default=None, alias="difficultyLevel")
    age_restriction: str | None = Field(default=None, alias="ageRestriction")
    private_available: bool | None = Field(default=None, alias="privateAvailable")
    group_size_min: int | None = Field(default=None, alias="groupSizeMin")
    group_size_max: int | None = Field(default=None, alias="groupSizeMax")
    pickup_supported: bool | None = Field(default=None, alias="pickupSupported")
    pickup_notes: str | None = Field(default=None, alias="pickupNotes")
    what_to_bring: list[str] = Field(default_factory=list, alias="whatToBring")
    cancellation_policy: str | None = Field(default=None, alias="cancellationPolicy")
    accessibility_info: str | None = Field(default=None, alias="accessibilityInfo")
    highlights: list[str] = Field(default_factory=list)
    availability_notes: str | None = Field(default=None, alias="availabilityNotes")

    model_config = ConfigDict(populate_by_name=True, serialize_by_alias=True)

    @field_validator(
        "included_items",
        "excluded_items", 
        "languages",
        "what_to_bring",
        "highlights",
        mode="before",
    )
    @classmethod
    def default_empty_lists(cls, value):
        if value is None:
            return []
        return value


class SafariListingCreate(AdminListingBase):
    safari_detail: AdminSafariDetail = Field(alias="safariDetail")

    @model_validator(mode="after")
    def validate_variants(self):
        if not self.variants:
            raise ValueError("at least one variant is required")
        if sum(1 for variant in self.variants if variant.is_default) != 1:
            raise ValueError("exactly one variant must be marked as default")
        return self


class SafariListingResponse(AdminListingBase):
    id: UUID
    category: Literal["safari"]
    destination: DestinationRef | None = None
    media: list[AdminListingMediaResponse] = Field(default_factory=list, exclude=True)
    from_price: ListingFromPriceResponse | None = Field(default=None, alias="fromPrice")
    cover_image: MediaSummary | None = None
    gallery: list[MediaAssetPublicResponse] = Field(default_factory=list)
    variants: list[ListingVariantAdminResponse] = Field(default_factory=list)
    safari_detail: AdminSafariDetail | None = Field(default=None, alias="safariDetail")


class ExperienceListingCreate(AdminListingBase):
    activity_detail: AdminActivityDetail = Field(alias="activityDetail")

    @model_validator(mode="after")
    def validate_variants(self):
        if not self.variants:
            raise ValueError("at least one variant is required")
        if sum(1 for variant in self.variants if variant.is_default) != 1:
            raise ValueError("exactly one variant must be marked as default")
        return self


class ExperienceListingResponse(AdminListingBase):
    id: UUID
    category: Literal["experience"]
    destination: DestinationRef | None = None
    media: list[AdminListingMediaResponse] = Field(default_factory=list, exclude=True)
    from_price: ListingFromPriceResponse | None = Field(default=None, alias="fromPrice")
    cover_image: MediaSummary | None = None
    gallery: list[MediaAssetPublicResponse] = Field(default_factory=list)
    variants: list[ListingVariantAdminResponse] = Field(default_factory=list)
    activity_detail: AdminActivityDetail | None = Field(default=None, alias="activityDetail")


class TransferListingCreate(AdminListingBase):
    transfer_detail: AdminTransferDetail = Field(alias="transferDetail")

    @model_validator(mode="after")
    def validate_variants(self):
        if not self.variants:
            raise ValueError("at least one variant is required")
        if sum(1 for variant in self.variants if variant.is_default) != 1:
            raise ValueError("exactly one variant must be marked as default")
        return self


class TransferListingResponse(AdminListingBase):
    id: UUID
    category: Literal["transfer"]
    destination: DestinationRef | None = None
    media: list[AdminListingMediaResponse] = Field(default_factory=list, exclude=True)
    from_price: ListingFromPriceResponse | None = Field(default=None, alias="fromPrice")
    cover_image: MediaSummary | None = None
    gallery: list[MediaAssetPublicResponse] = Field(default_factory=list)
    variants: list[ListingVariantAdminResponse] = Field(default_factory=list)
    transfer_detail: AdminTransferDetail | None = Field(default=None, alias="transferDetail")


class ListingUpdateRequest(CoordinateMixin):
    destination_id: UUID | None = Field(default=None, alias="destinationId")
    title: str | None = None
    description: str | None = None
    is_active: bool | None = Field(default=None, alias="isActive")
    hotel_detail: AdminHotelDetail | None = Field(default=None, alias="hotelDetail")
    tour_detail: AdminTourDetail | None = Field(default=None, alias="tourDetail")
    safari_detail: AdminSafariDetail | None = Field(default=None, alias="safariDetail")
    activity_detail: AdminActivityDetail | None = Field(default=None, alias="activityDetail")
    transfer_detail: AdminTransferDetail | None = Field(default=None, alias="transferDetail")
    media: list[AdminListingMedia] | None = None
    variants: list[ListingVariantAdminInput] | None = None

    model_config = ConfigDict(populate_by_name=True, serialize_by_alias=True)

    @model_validator(mode="after")
    def validate_single_detail_payload(self):
        populated_details = [
            detail
            for detail in [
                self.hotel_detail,
                self.tour_detail,
                self.safari_detail,
                self.activity_detail,
                self.transfer_detail,
            ]
            if detail is not None
        ]
        if len(populated_details) > 1:
            raise ValueError("only one detail payload can be provided")
        return self

    @model_validator(mode="after")
    def validate_media_cover(self):
        if self.media is not None and sum(1 for media in self.media if media.is_cover) > 1:
            raise ValueError("only one media item can be marked as cover")
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
