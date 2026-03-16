from uuid import UUID
from pydantic import BaseModel, ConfigDict


class ListingIncludeBase(BaseModel):
    listing_id: UUID
    name: str


class ListingIncludeCreate(ListingIncludeBase):
    pass


class ListingIncludeResponse(ListingIncludeBase):
    id: UUID

    model_config = ConfigDict(from_attributes=True)