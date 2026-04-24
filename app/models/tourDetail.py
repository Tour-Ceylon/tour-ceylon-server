from sqlalchemy import Boolean, Column, ForeignKey, Integer, JSON, String, Time, UUID
from sqlalchemy.orm import relationship

from app.models.base import Base, UUIDMixin, TimestampMixin


class TourDetail(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "tour_details"


    listing_id = Column(UUID(as_uuid=True), ForeignKey("listings.id"), nullable=False, index=True, unique=True)

    duration_days = Column(Integer, nullable=False)

    route_summary = Column(String, nullable=False)

    meeting_point = Column(String, nullable=False)

    itinerary_highlights = Column(JSON, nullable=True)
    included_items = Column(JSON, nullable=True)
    excluded_items = Column(JSON, nullable=True)
    languages = Column(JSON, nullable=True)
    difficulty_level = Column(String, nullable=True)
    group_size_min = Column(Integer, nullable=True)
    group_size_max = Column(Integer, nullable=True)
    private_available = Column(Boolean, nullable=True)
    pickup_available = Column(Boolean, nullable=True)
    dropoff_available = Column(Boolean, nullable=True)
    pickup_notes = Column(String, nullable=True)
    dropoff_notes = Column(String, nullable=True)
    start_time = Column(Time, nullable=True)
    end_time = Column(Time, nullable=True)
    cancellation_policy = Column(String, nullable=True)
    what_to_bring = Column(JSON, nullable=True)
    child_policy = Column(String, nullable=True)
    accessibility_info = Column(String, nullable=True)

    listing = relationship("Listing", back_populates="tour_detail")


TourDetails = TourDetail
