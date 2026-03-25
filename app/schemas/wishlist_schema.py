from datetime import datetime
from enum import Enum
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class WishlistItemType(str, Enum):
    TOUR_PACKAGE = "tour_package"
    DESTINATION = "destination"


class WishlistToggleRequest(BaseModel):
    item_id: UUID
    item_type: WishlistItemType


class WishlistToggleResponse(BaseModel):
    status: str


class WishlistStatusResponse(BaseModel):
    is_wishlisted: bool


class WishlistRow(BaseModel):
    id: UUID
    user_id: UUID
    item_id: UUID
    item_type: WishlistItemType
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class FullWishlistResponse(BaseModel):
    packages: list[dict]
    destinations: list[dict]
