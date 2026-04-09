import uuid

from sqlalchemy import Column, Float, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.config.database import Base


class ReviewMetric(Base):
    __tablename__ = "ReviewMetrics"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    listing_id = Column(UUID(as_uuid=True), ForeignKey("Listings.id"), nullable=False, index=True)
    label = Column(String, nullable=False)
    score = Column(Float, nullable=False)

    listing = relationship("Listing", back_populates="review_metrics")
