from sqlalchemy import Column, Enum, String, ForeignKey, UUID, Integer, Boolean
from sqlalchemy.orm import relationship

from app.models.base import Base, UUIDMixin 
from app.models.enum import SafariType


class SafariDetail(Base, UUIDMixin):
    __tablename__ = "safari_details"

    listing_id = Column(UUID(as_uuid=True), ForeignKey("Listings.id"),nullable=False, index=True, unique=True)

    national_park = Column(String, nullable=False)

    safari_type = Column(
        Enum(SafariType, name="safari_type_enum"),
        nullable=False
    )

    duration_minutes = Column(Integer, nullable=False)

    guide_inluded = Column(Boolean, nullable=False, )


