import uuid
from datetime import datetime

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    String,
    Uuid,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship

from app.models.base import Base
from app.payments.constants import PaymentStatus

_STATUS_VALUES = ", ".join(f"'{s.value}'" for s in PaymentStatus)


class Payment(Base):
    """One checkout attempt against a payable target (provider-agnostic)."""

    __tablename__ = "payments"
    __table_args__ = (
        CheckConstraint(f"status IN ({_STATUS_VALUES})", name="ck_payments_status"),
        Index("ix_payments_target", "target_type", "target_id"),
    )

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)

    target_type = Column(String(32), nullable=False)
    target_id = Column(Uuid(as_uuid=True), nullable=False)

    provider = Column(String(32), nullable=False)
    # Sent to the gateway as its order id.
    order_id = Column(String(64), nullable=False, unique=True)

    amount = Column(Numeric(12, 2), nullable=False)
    currency = Column(String(3), nullable=False)

    status = Column(String(20), nullable=False, default=PaymentStatus.INITIATED.value, index=True)
    provider_payment_id = Column(String(128), nullable=True)

    created_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)
    updated_at = Column(
        DateTime(timezone=True), nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    events = relationship("PaymentEvent", back_populates="payment")


class PaymentEvent(Base):
    """Audit trail of every webhook attempt, valid or not."""

    __tablename__ = "payment_events"

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)

    payment_id = Column(
        Uuid(as_uuid=True),
        ForeignKey("payments.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    provider = Column(String(32), nullable=False)
    raw_payload = Column(JSON().with_variant(JSONB(), "postgresql"), nullable=False)
    signature_valid = Column(Boolean, nullable=False)
    status_code = Column(String(16), nullable=True)
    received_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)

    payment = relationship("Payment", back_populates="events")
