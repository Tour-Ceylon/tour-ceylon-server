from sqlalchemy import Boolean, Column, Enum, ForeignKey, Integer, JSON, String, Time, UUID
from sqlalchemy.orm import relationship

from app.models.base import Base, UUIDMixin 
from app.models.enum import SafariType


class SafariDetail(Base, UUIDMixin):
    __tablename__ = "safari_details"

    listing_id = Column(UUID(as_uuid=True), ForeignKey("listings.id"), nullable=False, index=True, unique=True)

    national_park = Column(String, nullable=False)

    safari_type = Column(
        Enum(SafariType, name="safari_type_enum"),
        nullable=False
    )

    duration_minutes = Column(Integer, nullable=False)

    guide_included = Column(Boolean, nullable=False)
    pickup_supported = Column(Boolean, nullable=False, default=False)
    start_time = Column(Time, nullable=True)
    end_time = Column(Time, nullable=True)
    included_items = Column(JSON, nullable=True)
    excluded_items = Column(JSON, nullable=True)
    languages = Column(JSON, nullable=True)
    difficulty_level = Column(String, nullable=True)
    age_restriction = Column(String, nullable=True)
    private_available = Column(Boolean, nullable=True)
    group_size_min = Column(Integer, nullable=True)
    group_size_max = Column(Integer, nullable=True)
    pickup_notes = Column(String, nullable=True)
    what_to_bring = Column(JSON, nullable=True)
    cancellation_policy = Column(String, nullable=True)
    accessibility_info = Column(String, nullable=True)
    best_season = Column(String, nullable=True)
    wildlife_highlights = Column(JSON, nullable=True)

    listing = relationship("Listing", back_populates="safari_detail")
