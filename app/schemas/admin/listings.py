from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, model_validator


AdminListingCategory = Literal["stay", "tour", "activity", "transfer"]


class ReviewMetricItem(BaseModel):
    label: str
    score: float


class GuestReviewItem(BaseModel):
    id: str | None = None
    author: str
    quote: str


class RoomItem(BaseModel):
    id: str | None = None
    name: str
    amenities: list[str]
    pricePerNight: float
    available: bool = True


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
    latitude: float | None = None
    longitude: float | None = None


class AdminListingBase(CoordinateMixin):
    destinationId: UUID
    title: str
    location: str | None = None
    description: str
    image: str | None = None
    rating: float | None = None
    reviewCount: float | None = None
    cancellationPolicy: str | None = None
    includes: list[str] = []
    recommendation: str | None = None
    isActive: bool = True


class StayListingCreate(AdminListingBase):
    rooms: list[RoomItem] = []
    reviewMetrics: list[ReviewMetricItem] = []
    guestReviews: list[GuestReviewItem] = []


class StayListingResponse(StayListingCreate):
    id: UUID
    category: Literal["stay"]
    destination: DestinationRef | None = None


class TourListingCreate(AdminListingBase):
    duration: str | None = None
    route: str | None = None
    price: float | None = None
    highlights: list[str] = []


class TourListingResponse(TourListingCreate):
    id: UUID
    category: Literal["tour"]
    destination: DestinationRef | None = None


class ActivityListingCreate(AdminListingBase):
    duration: str | None = None
    activityType: str | None = None
    difficulty: str | None = None
    price: float | None = None
    highlights: list[str] = []


class ActivityListingResponse(ActivityListingCreate):
    id: UUID
    category: Literal["activity"]
    destination: DestinationRef | None = None


class TransferListingCreate(AdminListingBase):
    origin: str | None = None
    destinationLabel: str | None = None
    vehicleType: str | None = None
    price: float | None = None
    serviceHighlights: list[str] = []


class TransferListingResponse(TransferListingCreate):
    id: UUID
    category: Literal["transfer"]
    destination: DestinationRef | None = None


class ListingUpdateRequest(CoordinateMixin):
    destinationId: UUID | None = None
    title: str | None = None
    location: str | None = None
    description: str | None = None
    image: str | None = None
    rating: float | None = None
    reviewCount: float | None = None
    cancellationPolicy: str | None = None
    includes: list[str] | None = None
    recommendation: str | None = None
    isActive: bool | None = None
    rooms: list[RoomItem] | None = None
    reviewMetrics: list[ReviewMetricItem] | None = None
    guestReviews: list[GuestReviewItem] | None = None
    duration: str | None = None
    route: str | None = None
    price: float | None = None
    highlights: list[str] | None = None
    activityType: str | None = None
    difficulty: str | None = None
    origin: str | None = None
    destinationLabel: str | None = None
    vehicleType: str | None = None
    serviceHighlights: list[str] | None = None
