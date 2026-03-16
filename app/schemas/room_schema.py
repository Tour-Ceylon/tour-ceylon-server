from uuid import UUID
from pydantic import BaseModel, ConfigDict
from typing import Optional


class RoomBase(BaseModel):
    listing_id: UUID
    name: str
    price_per_night: float
    available: bool = True


class RoomCreate(RoomBase):
    pass


class RoomUpdate(BaseModel):
    name: Optional[str] = None
    price_per_night: Optional[float] = None
    available: Optional[bool] = None


class RoomResponse(RoomBase):
    id: UUID

    model_config = ConfigDict(from_attributes=True)