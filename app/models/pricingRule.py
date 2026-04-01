from sqlalchemy import Column, Enum, Integer, ForeignKey, UUID, Float
from sqlalchemy.orm import relationship

from app.models.base import Base, UUIDMixin, TimestampMixin, DateTime
from app.models.enum import PricingRuleType,CurrencyCode
from datetime import datetime

class PricingRule(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "pricing_rules"


    variant_id = Column(UUID(as_uuid=True), ForeignKey("Variants.id"),nullable=False, index=True, unique=True)

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
