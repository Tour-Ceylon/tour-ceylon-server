from uuid import UUID
from pydantic import BaseModel, ConfigDict


class ActivityBase(BaseModel):
    listing_id: UUID
    duration: str
    activity_type: str
    difficulty: str
    price: float


class ActivityCreate(ActivityBase):
    pass


class ActivityResponse(ActivityBase):
    id: UUID

    model_config = ConfigDict(from_attributes=True)