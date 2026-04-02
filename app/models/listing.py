from datetime import datetime, timezone
import uuid

from sqlalchemy import Boolean, Column, DateTime, Enum, Float, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSON, UUID
from sqlalchemy.orm import relationship

from app.config.database import Base
from app.models.enum import CurrencyType, ListingType


class Listing(Base):
    __tablename__ = "Listings"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    type = Column(Enum(ListingType), nullable=False, index=True)
    title = Column(String, nullable=False)
    slug = Column(String, unique=True, index=True, nullable=True)
    description = Column(Text, nullable=True)

    location = Column(String, nullable=True)
    location_city = Column(String, nullable=True, index=True)
    location_district = Column(String, nullable=True, index=True)
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)

    image = Column(String, nullable=True)
    rating = Column(Float, nullable=True)
    review_count = Column(Integer, nullable=True)
    group_size = Column(Integer, nullable=True)
    cancellation_policy = Column(Text, nullable=True)
    includes = Column(JSON, nullable=True, default=list)
    excludes = Column(JSON, nullable=True, default=list)
    recommendation = Column(Text, nullable=True)
    is_active = Column(Boolean, default=True, nullable=False, index=True)
    base_currency = Column(Enum(CurrencyType), default=CurrencyType.LKR, nullable=False)

    duration = Column(String, nullable=True)
    route = Column(String, nullable=True)
    price = Column(Float, nullable=True)
    highlights = Column(JSON, nullable=True)

    activity_type = Column(String, nullable=True)
    difficulty = Column(String, nullable=True)

    origin = Column(String, nullable=True)
    destination = Column(String, nullable=True)
    vehicle_type = Column(String, nullable=True)
    service_highlights = Column(JSON, nullable=True)

    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    rooms = relationship("Room", back_populates="listing", cascade="all, delete-orphan")
    review_metrics = relationship("ReviewMetric", back_populates="listing", cascade="all, delete-orphan")
    guest_reviews = relationship("GuestReview", back_populates="listing", cascade="all, delete-orphan")
