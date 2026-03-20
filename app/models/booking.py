from datetime import datetime, timezone
import uuid 
from sqlalchemy import Column, Enum, DateTime, ForeignKey, Integer
from app.config.database import Base
from sqlalchemy.dialects.postgresql import UUID

from app.models.enum import BookingStatus


class Bookings(Base):
    __tablename__ = "Bookings"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("Users.id"), nullable=False)
    listing_id = Column(UUID(as_uuid=True), ForeignKey("Listings.id"), nullable=False)
    travel_date = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    travel_count = Column(Integer, default=1, nullable=False)
    unit_price_minor = Column(Integer, nullable=False)
    total_price_minor = Column(Integer, nullable=False)
    status = Column(
        Enum(BookingStatus),
        default=BookingStatus.PENDING_PAYMENT,
        nullable=False
    )
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
