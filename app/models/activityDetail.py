from datetime import time
from sqlalchemy import ARRAY, Boolean, Column, ForeignKey, Integer, String, Text, Time, UUID
from sqlalchemy.orm import relationship

from app.models.base import Base, TimestampMixin, UUIDMixin


class ActivityDetail(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "activity_details"

    listing_id = Column(UUID(as_uuid=True), ForeignKey("listings.id"), nullable=False, unique=True, index=True)
    activity_type = Column(String, nullable=False)
    duration_minutes = Column(Integer, nullable=False)
    meeting_point = Column(String, nullable=True)
    start_time = Column(Time, nullable=True)
    end_time = Column(Time, nullable=True)
    included_items = Column(ARRAY(String), nullable=True)
    excluded_items = Column(ARRAY(String), nullable=True)
    languages = Column(ARRAY(String), nullable=True)
    difficulty_level = Column(String, nullable=True)
    age_restriction = Column(String, nullable=True)
    private_available = Column(Boolean, nullable=True)
    group_size_min = Column(Integer, nullable=True)
    group_size_max = Column(Integer, nullable=True)
    pickup_supported = Column(Boolean, nullable=True)
    pickup_notes = Column(Text, nullable=True)
    what_to_bring = Column(ARRAY(String), nullable=True)
    cancellation_policy = Column(Text, nullable=True)
    accessibility_info = Column(Text, nullable=True)
    highlights = Column(ARRAY(String), nullable=True)
    availability_notes = Column(Text, nullable=True)

    # Relationships
    listing = relationship("Listing", back_populates="activity_detail")