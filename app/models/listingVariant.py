from sqlalchemy import Column, String, Enum, Integer, Boolean, UUID, ForeignKey
from sqlalchemy.orm import relationship

from app.models.base import Base, UUIDMixin, TimestampMixin, SoftDeleteMixin
from app.models.enum import BookingUnit


class Listing_Variant(Base, UUIDMixin, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "listing_variant"


    listing_id = Column(UUID(as_uuid=True), ForeignKey("Listings.id"), nullable=False, index=True, unique=True)


    name = Column(String, unique=True, nullable=False, index=True)

    booking_unit = Column(
        Enum(BookingUnit, name="booking_unit_enum"),
        nullable=False
    )

    
    capacity_min = Column(Integer, nullable=True)
    capacity_max = Column(Integer, nullable=True)

    is_defaut = Column(Boolean, default=True, nullable=False)


