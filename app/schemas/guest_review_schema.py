from uuid import UUID
from pydantic import BaseModel, ConfigDict


class GuestReviewBase(BaseModel):
    listing_id: UUID
    author: str
    quote: str


class GuestReviewCreate(GuestReviewBase):
    pass


class GuestReviewResponse(GuestReviewBase):
    id: UUID

    model_config = ConfigDict(from_attributes=True)