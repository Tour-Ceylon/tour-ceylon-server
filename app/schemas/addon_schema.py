from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class AddOnCreate(BaseModel):
    listing_id: UUID
    room_id: UUID | None = None
    name: str = Field(..., min_length=1, max_length=150)
    description: str | None = Field(None, max_length=1000)
    price: Decimal = Field(..., ge=0)
    base_currency: str = Field("USD", min_length=3, max_length=3)
    is_active: bool = True


class AddOnUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=150)
    description: str | None = Field(None, max_length=1000)
    price: Decimal | None = Field(None, ge=0)
    base_currency: str | None = Field(None, min_length=3, max_length=3)
    is_active: bool | None = None


class AddOnOut(BaseModel):
    """Matches the customer site's ListingAddOnResponse."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    listing_id: UUID
    room_id: UUID | None = None
    name: str
    description: str | None = None
    price: float
    base_currency: str
    is_active: bool
