"""A note an admin writes for the driver assigned to a transport booking.

Separate from the customer's request (which comes from the booking form) and from the admin team's private
internal notes. Stored in `transport_booking_driver_notes`, one editable note per booking.
"""
from typing import Dict, Iterable, Optional, Tuple
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.exc import OperationalError, ProgrammingError
from sqlalchemy.orm import Session

from app.core.logging import logger
from app.models.driver import TransportBookingDriverNote
from app.models.user import User

_NOT_READY = HTTPException(
    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
    detail="Driver notes are not available yet. Please try again later.",
)


class DriverNoteService:
    def __init__(self, db: Session):
        self.db = db

    def for_bookings(self, booking_ids: Iterable[UUID]) -> Dict[UUID, TransportBookingDriverNote]:
        """{booking_id: note}. Returns {} (rather than failing) when the table has not been created yet."""
        ids = list(booking_ids)
        if not ids:
            return {}
        try:
            with self.db.begin_nested():
                rows = self.db.query(TransportBookingDriverNote).filter(TransportBookingDriverNote.booking_id.in_(ids)).all()
        except (ProgrammingError, OperationalError) as exc:
            logger.warning("driver_note.table_unavailable error=%s", str(exc).splitlines()[0])
            return {}
        return {row.booking_id: row for row in rows}

    def for_booking(self, booking_id: UUID) -> Optional[TransportBookingDriverNote]:
        return self.for_bookings([booking_id]).get(booking_id)

    @staticmethod
    def parts(note: Optional[TransportBookingDriverNote]) -> Tuple[Optional[str], Optional[object]]:
        """(text, updated_at) for response models."""
        return (note.note, note.updated_at) if note else (None, None)

    def set_note(self, booking_id: UUID, admin: User, text: str) -> Optional[TransportBookingDriverNote]:
        """Create or replace the note. An empty note removes it. Returns the saved note, or None if removed."""
        cleaned = (text or "").strip()
        try:
            with self.db.begin_nested():
                existing = (
                    self.db.query(TransportBookingDriverNote)
                    .filter(TransportBookingDriverNote.booking_id == booking_id)
                    .first()
                )
        except (ProgrammingError, OperationalError):
            raise _NOT_READY

        try:
            if not cleaned:
                if existing:
                    self.db.delete(existing)
                self.db.commit()
                return None
            if existing:
                existing.note = cleaned
                existing.updated_by_user_id = admin.id
                row = existing
            else:
                row = TransportBookingDriverNote(booking_id=booking_id, note=cleaned, updated_by_user_id=admin.id)
                self.db.add(row)
            self.db.commit()
        except (ProgrammingError, OperationalError):
            self.db.rollback()
            raise _NOT_READY
        self.db.refresh(row)
        return row
