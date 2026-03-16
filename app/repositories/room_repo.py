from typing import List, Optional
from uuid import UUID
from sqlalchemy.orm import Session

from app.models.room import Room
from app.schemas.room_schema import RoomCreate, RoomUpdate


class RoomRepository:

    def __init__(self, db: Session):
        self.db = db

    def create(self, room_data: RoomCreate) -> Room:

        db_room = Room(**room_data.model_dump())

        self.db.add(db_room)
        self.db.commit()
        self.db.refresh(db_room)

        return db_room

    def get_by_id(self, room_id: UUID) -> Optional[Room]:

        return self.db.query(Room).filter(Room.id == room_id).first()

    def get_by_listing(self, listing_id: UUID) -> List[Room]:

        return self.db.query(Room).filter(Room.listing_id == listing_id).all()

    def update(self, room_id: UUID, room_data: RoomUpdate) -> Optional[Room]:

        db_room = self.get_by_id(room_id)

        if not db_room:
            return None

        update_data = room_data.model_dump(exclude_unset=True)

        for field, value in update_data.items():
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