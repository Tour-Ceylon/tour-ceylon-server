from sqlalchemy import Column, String, ForeignKey, UUID, DateTime, Enum
from sqlalchemy.orm import relationship
from datetime import datetime

from app.models.base import Base, UUIDMixin
from app.models.enum import BookingStatus, ChangedByType


class BookingStatusHistory(Base, UUIDMixin):
    __tablename__ = "booking_status_history"

    booking_id = Column(
        UUID(as_uuid=True),
        ForeignKey("bookings.id"),
        nullable=False,
        index=True
    )

    old_status = Column(
        Enum(BookingStatus, name="booking_status_enum"),
        nullable=True
    )

    new_status = Column(
        Enum(BookingStatus, name="booking_status_enum"),
        nullable=False
    )

    changed_by_type = Column(
        Enum(ChangedByType, name="changed_by_type_enum"),
        nullable=False
    )

    changed_by_user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id"),
        nullable=True
    )

    changed_at = Column(
        DateTime,
        default=datetime.utcnow,
        nullable=False
    )

    booking = relationship("Booking", back_populates="status_history")
    changed_by_user = relationship(
        "User",
        back_populates="changed_booking_statuses",
        foreign_keys=[changed_by_user_id],
    )
