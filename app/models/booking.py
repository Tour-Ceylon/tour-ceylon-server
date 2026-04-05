from datetime import datetime, timezone
import uuid
<<<<<<< Updated upstream

from sqlalchemy import Column, DateTime, Enum, ForeignKey, Integer
from sqlalchemy.dialects.postgresql import UUID

from app.config.database import Base
=======

from sqlalchemy import Column, DateTime, Enum, ForeignKey, Integer
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.models.base import Base
>>>>>>> Stashed changes
from app.models.enum import BookingStatus


class Booking(Base):
	__tablename__ = "bookings"

	id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
	user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
<<<<<<< Updated upstream
	listing_id = Column(UUID(as_uuid=True), ForeignKey("Listings.id"), nullable=False, index=True)
=======
	listing_id = Column(UUID(as_uuid=True), ForeignKey("listings.id"), nullable=False, index=True)
>>>>>>> Stashed changes
	travel_date = Column(DateTime(timezone=True), nullable=False)
	travel_count = Column(Integer, nullable=False, default=1)
	unit_price_minor = Column(Integer, nullable=False)
	total_price_minor = Column(Integer, nullable=False)
	status = Column(Enum(BookingStatus), nullable=False, default=BookingStatus.PENDING_PAYMENT)
	created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
<<<<<<< Updated upstream
=======

	# Relationships
	booking_items = relationship("BookingItem", back_populates="booking", cascade="all, delete-orphan")
	user = relationship("User", back_populates="bookings")
	listing = relationship("Listing", back_populates="bookings")
>>>>>>> Stashed changes
