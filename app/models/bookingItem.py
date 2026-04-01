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

    listings_id = Column(
        UUID(as_uuid=True),
        ForeignKey("listings.id"),
        nullable=False
    )

    variant_id = Column(
        UUID(as_uuid=True),
        ForeignKey("listings_variants.id"),
        nullable=False
    )

    travel_date = Column(Date, nullable=False)

    quantity = Column(Integer, nullable=False)

    unit_price = Column(Float, nullable=False)

    total_price = Column(Float, nullable=False)

    booking = relationship("Booking", back_populates="items")
    listing = relationship("Listing")
    variant = relationship("ListingVariant")