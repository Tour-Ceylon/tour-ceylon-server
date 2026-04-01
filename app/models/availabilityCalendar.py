from sqlalchemy import Column, Enum, Integer, ForeignKey, UUID, Float
from sqlalchemy.orm import relationship

from app.models.base import Base, UUIDMixin, TimestampMixin, DateTime
from app.models.enum import AvailabilityStatus
from datetime import datetime

class AvailabilityCalendar(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "availability_calendar"


    variant_id = Column(UUID(as_uuid=True), ForeignKey("Variants.id"),nullable=False, index=True, unique=True)

    service_date = Column(DateTime(timezone=True), default=datetime.utcnow)

    total_capacity = Column(Integer, nullable=False)

    reserved_capacity = Column(Integer, nullable=False)

    available_capacity = Column(Integer, nullable=False)

    available_status = Column(
        Enum(AvailabilityStatus, name="availability_status_enum")
        )
