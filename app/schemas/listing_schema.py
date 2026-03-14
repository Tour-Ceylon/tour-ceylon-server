from datetime import datetime
from typing import Optional
from uuid import UUID
from pydantic import BaseModel, ConfigDict

from app.models.enum import ListingType, CurrencyType, ListingStatus


class ListingBase(BaseModel):
    """Base listing schema with common fields"""
    type: ListingType
    title: Optional[str] = None
    slug: Optional[str] = None
    description: Optional[str] = None
    location_city: Optional[str] = None
    location_district: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    base_currency: CurrencyType = CurrencyType.LKR
    status: ListingStatus = ListingStatus.ARCHIVED


class ListingCreate(ListingBase):
    """Schema for creating a new listing"""
    pass


class ListingUpdate(BaseModel):
    """Schema for updating listing information"""
    type: Optional[ListingType] = None
    title: Optional[str] = None
    slug: Optional[str] = None
    description: Optional[str] = None
    location_city: Optional[str] = None
    location_district: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    base_currency: Optional[CurrencyType] = None
    status: Optional[ListingStatus] = None


class ListingResponse(ListingBase):
    """Schema for listing API responses"""
    id: UUID
    created_at: datetime
    updated_at: datetime
    
    model_config = ConfigDict(from_attributes=True)


class ListingInDB(ListingResponse):
    """Schema for listing stored in database (includes all fields)"""
    pass


class ListingListResponse(BaseModel):
    """Schema for paginated listing list responses"""
    listings: list[ListingResponse]
    total: int
    page: int
    per_page: int
    total_pages: int


class ListingSearchParams(BaseModel):
    """Schema for listing search parameters"""
    type: Optional[ListingType] = None
    title: Optional[str] = None
    location_city: Optional[str] = None
    location_district: Optional[str] = None
    base_currency: Optional[CurrencyType] = None
    status: Optional[ListingStatus] = None
    page: int = 1
    per_page: int = 20