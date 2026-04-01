from sqlalchemy import Column, Enum, String, ForeignKey, UUID, Integer, Time
from sqlalchemy.orm import relationship

from app.models.base import Base, UUIDMixin
from app.models.enum import PropertyType


class HotelDetail(Base, UUIDMixin):
    __tablename__ = "hotel_details"

    listing_id = Column(
        UUID(as_uuid=True),
        ForeignKey("Listings.id"),
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