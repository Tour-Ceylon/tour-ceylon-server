from sqlalchemy import Column, String, Enum, Integer, Boolean, UUID, ForeignKey
from sqlalchemy.orm import relationship

from app.models.base import Base, UUIDMixin, TimestampMixin, SoftDeleteMixin
from app.models.enum import BookingUnit


class ListingVariant(Base, UUIDMixin, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "listing_variants"


    listing_id = Column(UUID(as_uuid=True), ForeignKey("listings.id"), nullable=False, index=True)


    name = Column(String, unique=True, nullable=False, index=True)

    booking_unit = Column(
        Enum(BookingUnit, name="booking_unit_enum"),
        nullable=False
    )

    
    capacity_min = Column(Integer, nullable=True)
    capacity_max = Column(Integer, nullable=True)

    is_default = Column(Boolean, default=True, nullable=False)

    listing = relationship("Listing", back_populates="variants")
    booking_items = relationship("BookingItem", back_populates="variant")
    pricing_rules = relationship("PricingRule", back_populates="variant", cascade="all, delete-orphan")
    availability_entries = relationship(
        "AvailabilityCalendar",
        back_populates="variant",
        cascade="all, delete-orphan",
    )


Listing_Variant = ListingVariant
