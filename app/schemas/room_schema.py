from app.schemas.listing_schema import (
    HotelDetailBase as RoomBase,
    HotelDetailBase as RoomCreate,
    HotelDetailResponse as RoomResponse,
    HotelDetailUpdate as RoomUpdate,
)

__all__ = ["RoomBase", "RoomCreate", "RoomUpdate", "RoomResponse"]
