from sqlalchemy import Column, DateTime, Enum, Float, ForeignKey, Integer, UUID
from sqlalchemy.orm import relationship

from app.models.base import Base, UUIDMixin, TimestampMixin
from app.models.enum import CurrencyCode, PricingRuleType
from datetime import datetime

class PricingRule(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "pricing_rules"


    variant_id = Column(UUID(as_uuid=True), ForeignKey("listing_variants.id"), nullable=False, index=True)

    pricing_rule_type = Column(
        Enum(PricingRuleType, name="pricing_rule_type")
    )

    start_date = Column(DateTime(timezone=True), default=datetime.utcnow)
    end_date = Column(DateTime(timezone=True), default=datetime.utcnow)
    min_guest = Column(Integer, nullable=False)
    max_guest = Column(Integer, nullable=False)

    amount = Column(Float, nullable=False)
    currency = Column(
        Enum(CurrencyCode),
        default=CurrencyCode.USD,
        nullable=False
    )
    priority = Column(Integer, nullable=False)

    variant = relationship("ListingVariant", back_populates="pricing_rules")
