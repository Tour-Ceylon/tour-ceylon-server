from sqlalchemy import Column, String, ForeignKey, UUID, Numeric, DateTime, Enum
from sqlalchemy.orm import relationship

from app.models.base import Base, UUIDMixin, TimestampMixin
from app.models.enum import CurrencyCode, PaymentTransactionStatus, BookingStatus


class Booking(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "bookings"

    booking_reference = Column(String, nullable=False, unique=True, index=True)

    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id"),
        nullable=False,
        index=True
    )

    status = Column(Enum(BookingStatus, name="booking_status_enum"), nullable=False)

    total_amount = Column(Numeric(10, 2), nullable=False)

    currency = Column(Enum(CurrencyCode, name="currency_code_enum"), nullable=False, default=CurrencyCode.USD)

    payment_status = Column(Enum(PaymentTransactionStatus, name="payment_transaction_enum"), nullable=False)

    booked_at = Column(DateTime, nullable=False)

    # Relationships
    user = relationship("User", back_populates="bookings")
    booking_items = relationship("BookingItem", back_populates="booking", cascade="all, delete-orphan")
    stay_bookings = relationship("StayBooking", back_populates="booking", cascade="all, delete-orphan")
    payments = relationship("PaymentTransaction", back_populates="booking", cascade="all, delete-orphan")
    status_history = relationship("BookingStatusHistory", back_populates="booking", cascade="all, delete-orphan")
    reviews = relationship("Review", back_populates="booking")


Bookings = Booking
