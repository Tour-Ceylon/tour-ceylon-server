from sqlalchemy import Column, DateTime, Enum, ForeignKey, Integer, UUID
from sqlalchemy.orm import relationship

from app.models.base import Base, UUIDMixin, TimestampMixin
from app.models.enum import AvailabilityStatus
from datetime import datetime

class AvailabilityCalendar(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "availability_calendar"


    variant_id = Column(UUID(as_uuid=True), ForeignKey("listing_variants.id"), nullable=False, index=True)

    service_date = Column(DateTime(timezone=True), default=datetime.utcnow)

    total_capacity = Column(Integer, nullable=False)

    reserved_capacity = Column(Integer, nullable=False)

    available_capacity = Column(Integer, nullable=False)

    available_status = Column(
        Enum(AvailabilityStatus, name="availability_status_enum")
        )

    variant = relationship("ListingVariant", back_populates="availability_entries")
