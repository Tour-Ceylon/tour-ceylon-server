import uuid

from sqlalchemy import Column, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.config.database import Base


class GuestReview(Base):
    __tablename__ = "GuestReviews"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    listing_id = Column(UUID(as_uuid=True), ForeignKey("Listings.id"), nullable=False, index=True)
    author = Column(String, nullable=False)
    quote = Column(Text, nullable=False)

    listing = relationship("Listing", back_populates="guest_reviews")
