from sqlalchemy import Column, ForeignKey, Integer, String, UUID
from sqlalchemy.orm import relationship

from app.models.base import Base, UUIDMixin, TimestampMixin


class TourDetail(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "tour_details"


    listing_id = Column(UUID(as_uuid=True), ForeignKey("listings.id"), nullable=False, index=True, unique=True)

    duration_days = Column(Integer, nullable=False)

    route_summary = Column(String, nullable=False)

    meeting_point = Column(String, nullable=False)

    listing = relationship("Listing", back_populates="tour_detail")


TourDetails = TourDetail
