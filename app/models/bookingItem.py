from sqlalchemy import Column, ForeignKey, UUID, Integer, Date, Float
from sqlalchemy.orm import relationship

from app.models.base import Base, UUIDMixin


class BookingItem(Base, UUIDMixin):
    __tablename__ = "booking_items"

    booking_id = Column(
        UUID(as_uuid=True),
        ForeignKey("bookings.id"),
        nullable=False,
        index=True
    )

    listing_id = Column(
        UUID(as_uuid=True),
        ForeignKey("listings.id"),
        nullable=False
    )

    variant_id = Column(
        UUID(as_uuid=True),
        ForeignKey("listing_variants.id"),
        nullable=False
    )

    travel_date = Column(Date, nullable=False)

    quantity = Column(Integer, nullable=False)

    unit_price = Column(Float, nullable=False)

    total_price = Column(Float, nullable=False)

    booking = relationship("Booking", back_populates="booking_items")
    listing = relationship("Listing", back_populates="booking_items")
    variant = relationship("ListingVariant", back_populates="booking_items")
    travelers = relationship("BookingTraveler", back_populates="booking_item", cascade="all, delete-orphan")
