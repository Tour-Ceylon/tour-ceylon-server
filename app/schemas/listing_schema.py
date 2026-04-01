from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.models.enum import ListingType, CurrencyType


class ListingBase(BaseModel):
    """Base listing schema with common fields."""
    type: ListingType
    title: str
    location: Optional[str] = None
    description: Optional[str] = None
    image: Optional[str] = None
    rating: Optional[float] = None
    review_count: Optional[int] = None
    group_size: Optional[int] = None
    cancellation_policy: Optional[str] = None
    includes: list[str] = []
    excludes: list[str] = []
    recommendation: Optional[str] = None
    is_active: bool = True

    # Client-specific extras
    slug: Optional[str] = None
    location_city: Optional[str] = None
    location_district: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    base_currency: CurrencyType = CurrencyType.LKR

    # Tour / Activity fields
    duration: Optional[str] = None
    route: Optional[str] = None
    price: Optional[float] = None
    highlights: Optional[list[str]] = None

    # Activity-only
    activity_type: Optional[str] = None
    difficulty: Optional[str] = None

    # Transfer-only
    origin: Optional[str] = None
    destination: Optional[str] = None
    vehicle_type: Optional[str] = None
    service_highlights: Optional[list[str]] = None


class ListingCreate(ListingBase):
    """Schema for creating a new listing."""
    pass


class ListingUpdate(BaseModel):
    """Schema for updating listing information (all fields optional)."""
    type: Optional[ListingType] = None
    title: Optional[str] = None
    location: Optional[str] = None
    description: Optional[str] = None
    image: Optional[str] = None
    rating: Optional[float] = None
    review_count: Optional[int] = None
    cancellation_policy: Optional[str] = None
    includes: Optional[list[str]] = None
    recommendation: Optional[str] = None
    is_active: Optional[bool] = None
    slug: Optional[str] = None
    location_city: Optional[str] = None
    location_district: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    base_currency: Optional[CurrencyType] = None
    duration: Optional[str] = None
    route: Optional[str] = None
    price: Optional[float] = None
    highlights: Optional[list[str]] = None
    activity_type: Optional[str] = None
    difficulty: Optional[str] = None
    origin: Optional[str] = None
    destination: Optional[str] = None
    vehicle_type: Optional[str] = None
    service_highlights: Optional[list[str]] = None


class ListingResponse(ListingBase):
    """Schema for listing API responses."""
    id: UUID
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ListingInDB(ListingResponse):
    """Schema for listing stored in database (includes all fields)."""
    pass


class ListingListResponse(BaseModel):
    """Schema for paginated listing list responses."""
    listings: list[ListingResponse]
    total: int
    page: int
    per_page: int
    total_pages: int


class ListingSearchParams(BaseModel):
    """Schema for listing search parameters."""
    type: Optional[ListingType] = None
    title: Optional[str] = None
    location_city: Optional[str] = None
    location_district: Optional[str] = None
    base_currency: Optional[CurrencyType] = None
    is_active: Optional[bool] = None
    page: int = 1
    per_page: int = 20