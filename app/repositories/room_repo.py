from typing import Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.hotelDetail import HotelDetail
from app.schemas.room_schema import RoomCreate, RoomUpdate


class RoomRepository:
    """Deprecated compatibility repository backed by HotelDetail."""

    def __init__(self, db: Session):
        self.db = db

    def create(self, room_data: RoomCreate) -> HotelDetail:
        db_room = HotelDetail(**room_data.model_dump())
        self.db.add(db_room)
        self.db.commit()
        self.db.refresh(db_room)
        return db_room

    def get_by_id(self, room_id: UUID) -> Optional[HotelDetail]:
        return self.db.query(HotelDetail).filter(HotelDetail.id == room_id).first()

    def get_by_listing(self, listing_id: UUID) -> list[HotelDetail]:
        room = self.db.query(HotelDetail).filter(HotelDetail.listing_id == listing_id).first()
        return [room] if room else []

    def update(self, room_id: UUID, room_data: RoomUpdate) -> Optional[HotelDetail]:
        db_room = self.get_by_id(room_id)
        if not db_room:
            return None

        for field, value in room_data.model_dump(exclude_unset=True).items():
            setattr(db_room, field, value)

        self.db.commit()
        self.db.refresh(db_room)
        return db_room

    def delete(self, room_id: UUID) -> bool:
        db_room = self.get_by_id(room_id)
        if not db_room:
            return False

        self.db.delete(db_room)
        self.db.commit()
        return True
