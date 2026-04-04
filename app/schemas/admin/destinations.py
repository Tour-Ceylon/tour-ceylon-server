from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.enum import DestinationType


class AdminDestinationOption(BaseModel):
    id: UUID
    name: str
    destination_type: DestinationType = Field(alias="destinationType")
    latitude: float | None = None
    longitude: float | None = None
    city: str | None = None
    district: str | None = None

    model_config = ConfigDict(from_attributes=True, populate_by_name=True, serialize_by_alias=True)
