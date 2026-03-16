from uuid import UUID
from pydantic import BaseModel, ConfigDict


class TransferBase(BaseModel):
    listing_id: UUID
    origin: str
    destination: str
    vehicle_type: str
    price: float


class TransferCreate(TransferBase):
    pass


class TransferResponse(TransferBase):
    id: UUID

    model_config = ConfigDict(from_attributes=True)