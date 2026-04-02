from sqlalchemy import Column, ForeignKey, UUID, DateTime, UniqueConstraint
from sqlalchemy.orm import relationship
from datetime import datetime

from app.models.base import Base, UUIDMixin


class Wishlist(Base, UUIDMixin):
    __tablename__ = "wishlists"

    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id"),
        nullable=False,
        index=True
    )

    listing_id = Column(
        UUID(as_uuid=True),
        ForeignKey("listings.id"),
        nullable=False,
        index=True
    )

    created_at = Column(
        DateTime,
        default=datetime.utcnow,
        nullable=False
    )

    # Prevent duplicate wishlist entries
    __table_args__ = (
        UniqueConstraint("user_id", "listing_id", name="uq_user_listing_wishlist"),
    )

    user = relationship("User", back_populates="wishlists")
    listing = relationship("Listing", back_populates="wishlisted_by")
