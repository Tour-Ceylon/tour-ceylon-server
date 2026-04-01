from sqlalchemy import Column, String, ForeignKey, UUID, Integer
from sqlalchemy.orm import relationship

from app.models.base import Base, UUIDMixin


class BookingTraveler(Base, UUIDMixin):
    __tablename__ = "booking_travelers"

    booking_item_id = Column(
        UUID(as_uuid=True),
        ForeignKey("booking_items.id"),
        nullable=False,
        index=True
    )

    first_name = Column(String, nullable=False)
    last_name = Column(String, nullable=False)

    age = Column(Integer, nullable=False)

    nationality = Column(String, nullable=True)

    passport_no = Column(String, nullable=True)

    special_notes = Column(String, nullable=True)

    booking_item = relationship("BookingItem", back_populates="travelers")
