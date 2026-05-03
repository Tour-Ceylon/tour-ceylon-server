from typing import Literal
from uuid import UUID
from pydantic import AliasChoices, BaseModel, ConfigDict, Field

from app.schemas.media_schema import MediaAssetPublicResponse, MediaSummary

class PackageItineraryItem(BaseModel):
    day: int
    title: str
    description: str
    model_config = ConfigDict(from_attributes=True)

class PackageDestinationStop(BaseModel):
    id: str | None = None
    name: str
    order: int | None = None
    model_config = ConfigDict(from_attributes=True)

class PackageQuickFacts(BaseModel):
    airportTransferIncluded: bool | None = Field(None, validation_alias=AliasChoices("airportTransferIncluded", "airport_transfer_included"))
    boardBasis: str | None = Field(None, validation_alias=AliasChoices("boardBasis", "board_basis"))
    hotelCategory: str | None = Field(None, validation_alias=AliasChoices("hotelCategory", "hotel_category"))
    privateTour: bool | None = Field(None, validation_alias=AliasChoices("privateTour", "private_tour"))
    bestFor: list[str] = Field(default_factory=list, validation_alias=AliasChoices("bestFor", "best_for"))
    transportMode: str | None = Field(None, validation_alias=AliasChoices("transportMode", "transport_mode"))
    model_config = ConfigDict(from_attributes=True)

class PackageDayAccommodation(BaseModel):
    listingId: str | None = Field(None, validation_alias=AliasChoices("listingId", "listing_id"))
    hotelName: str | None = Field(None, validation_alias=AliasChoices("hotelName", "hotel_name"))
    roomType: str | None = Field(None, validation_alias=AliasChoices("roomType", "room_type"))
    mealBasis: str | None = Field(None, validation_alias=AliasChoices("mealBasis", "meal_basis"))
    note: str | None = None
    model_config = ConfigDict(from_attributes=True)

class PackageDayMedia(BaseModel):
    url: str
    altText: str | None = Field(None, validation_alias=AliasChoices("altText", "alt_text"))
    model_config = ConfigDict(from_attributes=True)

class PackageDayBlock(BaseModel):
    id: str | None = None
    type: Literal["arrival", "transfer", "sightseeing", "activity", "safari", "hotel", "meal", "leisure", "departure", "info"]
    title: str
    description: str | None = None
    linkedListingId: str | None = Field(None, validation_alias=AliasChoices("linkedListingId", "linked_listing_id"))
    linkedListingCategory: str | None = Field(None, validation_alias=AliasChoices("linkedListingCategory", "linked_listing_category"))
    startTime: str | None = Field(None, validation_alias=AliasChoices("startTime", "start_time"))
    endTime: str | None = Field(None, validation_alias=AliasChoices("endTime", "end_time"))
    durationMinutes: int | None = Field(None, validation_alias=AliasChoices("durationMinutes", "duration_minutes"))
    fromLabel: str | None = Field(None, validation_alias=AliasChoices("fromLabel", "from_label"))
    toLabel: str | None = Field(None, validation_alias=AliasChoices("toLabel", "to_label"))
    badges: list[str] = Field(default_factory=list)
    model_config = ConfigDict(from_attributes=True)

class PackageDay(BaseModel):
    day: int
    dateLabel: str | None = Field(None, validation_alias=AliasChoices("dateLabel", "date_label"))
    title: str
    destination: str | None = None
    transferLabel: str | None = Field(None, validation_alias=AliasChoices("transferLabel", "transfer_label"))
    overview: str | None = None
    accommodation: PackageDayAccommodation | None = None
    blocks: list[PackageDayBlock] = Field(default_factory=list)
    media: list[PackageDayMedia] = Field(default_factory=list)
    model_config = ConfigDict(from_attributes=True)

class PackageListingRef(BaseModel):
    listingId: str = Field(..., validation_alias=AliasChoices("listingId", "listing_id"))
    listingCategory: str = Field(..., validation_alias=AliasChoices("listingCategory", "listing_category"))
    role: str
    model_config = ConfigDict(from_attributes=True)

class PackageBase(BaseModel):
    name: str
    summary: str | None = None
    description: str
    duration: int
    nights: int | None = None
    route: str
    startLocation: str | None = Field(None, validation_alias=AliasChoices("startLocation", "start_location"))
    endLocation: str | None = Field(None, validation_alias=AliasChoices("endLocation", "end_location"))
    tripStyle: str | None = Field(None, validation_alias=AliasChoices("tripStyle", "trip_style"))
    basePrice: float = Field(..., validation_alias=AliasChoices("basePrice", "base_price"))
    image: str | None = None
    category: str
    includes: list[str] = Field(default_factory=list)
    exclusions: list[str] = Field(default_factory=list)
    highlights: list[str] = Field(default_factory=list)
    quickFacts: PackageQuickFacts = Field(default_factory=PackageQuickFacts, validation_alias=AliasChoices("quickFacts", "quick_facts"))
    destinations: list[PackageDestinationStop] = Field(default_factory=list)
    itinerary: list[PackageItineraryItem] = Field(default_factory=list)
    structuredItinerary: list[PackageDay] = Field(default_factory=list, validation_alias=AliasChoices("structuredItinerary", "structured_itinerary"))
    listingRefs: list[PackageListingRef] = Field(default_factory=list, validation_alias=AliasChoices("listingRefs", "listing_refs"))
    addOns: list[str] = Field(default_factory=list, validation_alias=AliasChoices("addOns", "add_ons"))
    isActive: bool = Field(True, validation_alias=AliasChoices("isActive", "is_active"))
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

class PackageCreate(PackageBase):
    pass

class PackageUpdate(PackageBase):
    pass

class PackageResponse(PackageBase):
    id: UUID
    cover_image: MediaSummary | None = None
    gallery: list[dict] = Field(default_factory=list)
    addOnDetails: list[dict] = Field(default_factory=list, validation_alias=AliasChoices("addOnDetails", "add_on_details"))
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)
