from sqlalchemy import Column, String, Integer, Numeric, Text, Enum
from sqlalchemy.dialects.postgresql import JSON

from app.models.base import Base, UUIDMixin, TimestampMixin
from app.models.enum import CurrencyCode, InquiryStatus


class BookingInquiry(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "booking_inquiries"

    # Unique reference like "INQ-12345678"
    reference = Column(String, nullable=False, unique=True, index=True)
    
    # Customer Information
    first_name = Column(String, nullable=False)
    last_name = Column(String, nullable=False)
    email = Column(String, nullable=False)
    phone = Column(String, nullable=False)
    nationality = Column(String, nullable=False)
    emergency_contact = Column(String, nullable=True)
    
    # Booking Details
    number_of_travelers = Column(Integer, nullable=False)
    special_requests = Column(Text, nullable=True)
    
    # Pricing
    subtotal = Column(Numeric(10, 2), nullable=False)
    total = Column(Numeric(10, 2), nullable=False)
    currency = Column(Enum(CurrencyCode, name="inquiry_currency_enum"), nullable=False)
    
    # Status tracking
    status = Column(Enum(InquiryStatus, name="inquiry_status_enum"), nullable=False, default=InquiryStatus.PENDING_CONTACT)
    
    # JSON field for cart items
    cart_items = Column(JSON, nullable=False)


BookingInquiries = BookingInquiry