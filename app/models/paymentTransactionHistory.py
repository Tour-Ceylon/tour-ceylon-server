from sqlalchemy import Column, String, ForeignKey, UUID, Float, DateTime, Enum
from sqlalchemy.orm import relationship
from datetime import datetime

from app.models.base import Base, UUIDMixin
from app.models.enum import CurrencyCode, PaymentTransactionStatus, PaymentProvider


class PaymentTransaction(Base, UUIDMixin):
    __tablename__ = "payment_transactions"

    booking_id = Column(
        UUID(as_uuid=True),
        ForeignKey("bookings.id"),
        nullable=False,
        index=True
    )

    provider = Column(Enum(PaymentProvider, name="payment_provider_enum"), nullable=False)  # e.g., stripe, razorpay

    amount = Column(Float, nullable=False)

    currency = Column(Enum(CurrencyCode, name="currency_code_enum"), nullable=False, default=CurrencyCode.USD)

    status = Column(Enum(PaymentTransactionStatus, name="payment_status_enum"), nullable=False)

    external_reference = Column(String, nullable=True)  # gateway transaction ID

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationship
    booking = relationship("Booking", back_populates="payment_transactions")