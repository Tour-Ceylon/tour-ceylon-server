from sqlalchemy import Column, String, Enum, Integer, Boolean, UUID, ForeignKey
from sqlalchemy.orm import relationship

from app.models.base import Base, UUIDMixin, TimestampMixin, SoftDeleteMixin
from app.models.enum import MediaType


class Listing_Media(Base, UUIDMixin, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "listing_media"


    listing_id = Column(UUID(as_uuid=True), ForeignKey("Listings.id"), nullable=False, index=True, unique=True)

    media_type = Column(
        Enum(MediaType, name="media_type_enum"),
        nullable=False
    )


    url = Column(String, unique=False, nullable=False)
    alt_text = Column(String, unique=False, nullable=False)
    sort_order = Column(Integer, nullable=False)
    iscover = Column(Boolean, default=False, nullable=False)

