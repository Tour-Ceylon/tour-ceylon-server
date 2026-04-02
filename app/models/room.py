import uuid

from sqlalchemy import Boolean, Column, Float, ForeignKey, String
from sqlalchemy.dialects.postgresql import JSON, UUID
from sqlalchemy.orm import relationship

from app.config.database import Base


class Room(Base):
    __tablename__ = "Rooms"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    listing_id = Column(UUID(as_uuid=True), ForeignKey("Listings.id"), nullable=False, index=True)
    name = Column(String, nullable=False)
    amenities = Column(JSON, nullable=True)
    price_per_night = Column(Float, nullable=False)
    available = Column(Boolean, default=True, nullable=False)

    listing = relationship("Listing", back_populates="rooms")

    @property
    def is_available(self) -> bool:
        return self.available
