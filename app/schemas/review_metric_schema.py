from uuid import UUID
from pydantic import BaseModel, ConfigDict


class ReviewMetricBase(BaseModel):
    listing_id: UUID
    label: str
    score: float


class ReviewMetricCreate(ReviewMetricBase):
    pass


class ReviewMetricResponse(ReviewMetricBase):
    id: UUID

    model_config = ConfigDict(from_attributes=True)