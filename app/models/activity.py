import uuid

from sqlalchemy import Column, Float, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID

from app.config.database import Base


class Activity(Base):
    __tablename__ = "Activities"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    listing_id = Column(UUID(as_uuid=True), ForeignKey("Listings.id"), nullable=False, index=True, unique=True)
    duration = Column(String, nullable=False)
    activity_type = Column(String, nullable=False)
    difficulty = Column(String, nullable=False)
    price = Column(Float, nullable=False)
