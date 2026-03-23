import uuid

from sqlalchemy import Column, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID

from app.config.database import Base


class ListingInclude(Base):
    __tablename__ = "ListingIncludes"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    listing_id = Column(UUID(as_uuid=True), ForeignKey("Listings.id"), nullable=False, index=True)
    name = Column(String, nullable=False)
