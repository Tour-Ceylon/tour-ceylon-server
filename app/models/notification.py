from sqlalchemy import Column, String, Text, Boolean, DateTime, JSON, ForeignKey, Enum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
import uuid
from enum import Enum as PyEnum

from app.models.base import Base, UUIDMixin, TimestampMixin


class NotificationType(str, PyEnum):
    BOOKING_CONFIRMED = "booking_confirmed"
    BOOKING_CANCELLED = "booking_cancelled"  
    BOOKING_QUOTED = "booking_quoted"


class ClientNotification(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "client_notifications"

    # User association (nullable for guest bookings)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True, index=True)
    
    # Email for guest notification matching (normalized lowercase)
    recipient_email = Column(String, nullable=False, index=True)
    
    # Notification details
    type = Column(Enum(NotificationType, name="notification_type_enum"), nullable=False)
    title = Column(String, nullable=False)
    message = Column(Text, nullable=False)
    
    # Associated booking inquiry
    booking_inquiry_id = Column(UUID(as_uuid=True), ForeignKey("booking_inquiries.id"), nullable=True, index=True)
    
    # Reference number for display
    reference = Column(String, nullable=True)
    
    # Payload for preview data (JSON)
    payload = Column(JSON, nullable=False, default={})
    
    # Read status
    is_read = Column(Boolean, nullable=False, default=False, index=True)
    read_at = Column(DateTime, nullable=True)
    
    # Relationships
    user = relationship("User", back_populates="notifications")
    booking_inquiry = relationship("BookingInquiry", backref="notifications")
