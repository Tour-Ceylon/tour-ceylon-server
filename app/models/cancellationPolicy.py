from sqlalchemy import Column, Enum, Integer, ForeignKey, UUID, Float
from sqlalchemy.orm import relationship

from app.models.base import Base, UUIDMixin, TimestampMixin
from app.models.enum import CancellationPolicyType, PenaltyType


class CancellationPolicy(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "cancellation_policies"


    listing_id = Column(UUID(as_uuid=True), ForeignKey("listings.id"), nullable=False, index=True)

    policy_type = Column(
        Enum(CancellationPolicyType, name="cancellation_policy_type_enum"),
        nullable=False,
        default=CancellationPolicyType.FLEXIBLE
        )    
    
    free_cancel_before_hours = Column(Float, nullable=True, default=0.0)

    penalty_amount = Column(Float, nullable=False)

    penalty_type = Column(
        Enum(PenaltyType, name="penalty_type_enum"),
        nullable=False,
        default=PenaltyType.PERCENTAGE
    )

    listing = relationship("Listing", back_populates="cancellation_policies")
