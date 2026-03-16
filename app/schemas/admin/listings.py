from typing import Literal
from uuid import UUID

from pydantic import BaseModel


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


class AdminListingBase(BaseModel):
    title: str
    location: str
    description: str
    image: str
    rating: float
    reviewCount: float
    cancellationPolicy: str
    includes: list[str]
    recommendation: str
    isActive: bool = True


class StayListingCreate(AdminListingBase):
    rooms: list[RoomItem]
    reviewMetrics: list[ReviewMetricItem]
    guestReviews: list[GuestReviewItem]


class StayListingResponse(StayListingCreate):
    id: UUID
    category: Literal["stay"]


class TourListingCreate(AdminListingBase):
    duration: str
    route: str
    price: float
    highlights: list[str]


class TourListingResponse(TourListingCreate):
    id: UUID
    category: Literal["tour"]


class ActivityListingCreate(AdminListingBase):
    duration: str
    activityType: str
    difficulty: str
    price: float
    highlights: list[str]


class ActivityListingResponse(ActivityListingCreate):
    id: UUID
    category: Literal["activity"]


class TransferListingCreate(AdminListingBase):
    origin: str
    destination: str
    vehicleType: str
    price: float
    serviceHighlights: list[str]


class TransferListingResponse(TransferListingCreate):
    id: UUID
    category: Literal["transfer"]


class ListingUpdateRequest(BaseModel):
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
    destination: str | None = None
    vehicleType: str | None = None
    serviceHighlights: list[str] | None = None

