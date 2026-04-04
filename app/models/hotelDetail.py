from sqlalchemy import Boolean, Column, Enum, ForeignKey, Integer, JSON, String, Time, UUID
from sqlalchemy.orm import relationship

from app.models.base import Base, UUIDMixin
from app.models.enum import PropertyType


class HotelDetail(Base, UUIDMixin):
    __tablename__ = "hotel_details"

    listing_id = Column(
        UUID(as_uuid=True),
        ForeignKey("listings.id"),
        nullable=False,
        index=True,
        unique=True
    )

    property_type = Column(
        Enum(PropertyType, name="property_type_enum"),
        nullable=False
    )

    star_rating = Column(Integer, nullable=False)

    check_in_time = Column(Time, nullable=False)

    check_out_time = Column(Time, nullable=False)

    child_policy = Column(String, nullable=True)
    property_name = Column(String, nullable=True)
    short_location = Column(String, nullable=True)
    address_line_1 = Column(String, nullable=True)
    address_line_2 = Column(String, nullable=True)
    city = Column(String, nullable=True)
    district = Column(String, nullable=True)
    postal_code = Column(String, nullable=True)
    contact_phone = Column(String, nullable=True)
    contact_email = Column(String, nullable=True)
    website = Column(String, nullable=True)
    google_map_url = Column(String, nullable=True)
    amenities = Column(JSON, nullable=True)
    languages_spoken = Column(JSON, nullable=True)
    room_count = Column(Integer, nullable=True)
    max_guest_capacity = Column(Integer, nullable=True)
    meal_plans = Column(JSON, nullable=True)
    parking_available = Column(Boolean, nullable=True)
    wifi_available = Column(Boolean, nullable=True)
    pets_allowed = Column(Boolean, nullable=True)
    smoking_policy = Column(String, nullable=True)
    cancellation_policy = Column(String, nullable=True)
    extra_bed_policy = Column(String, nullable=True)
    check_in_notes = Column(String, nullable=True)
    check_out_notes = Column(String, nullable=True)

    listing = relationship("Listing", back_populates="hotel_detail")
