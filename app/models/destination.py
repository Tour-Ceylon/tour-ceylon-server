from sqlalchemy import Column, String, Enum, Boolean, Float
from sqlalchemy.orm import relationship

from app.models.base import Base, UUIDMixin, TimestampMixin, SoftDeleteMixin
from app.models.enum import DestinationType


class Destination(Base, UUIDMixin, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "destinations"

    name = Column(String, unique=True, nullable=False, index=True)

    destination_type = Column(
        Enum(DestinationType, name="destination_type_enum"),
        nullable=False
    )

    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)

    listings = relationship("Listing", back_populates="destination")


