from sqlalchemy import Column, String, ForeignKey, UUID, Integer, DateTime, Enum
from sqlalchemy.orm import relationship


from app.models.base import Base, UUIDMixin, TimestampMixin
from app.models.enum import ReviewStatus


class Review(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "reviews"

    booking_id = Column(
        UUID(as_uuid=True),
        ForeignKey("Bookings.id"),
        nullable=False,
        index=True
    )

    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("Users.id"),
        nullable=False,
        index=True
    )

    listing_id = Column(
        UUID(as_uuid=True),
        ForeignKey("Listings.id"),
        nullable=False,
        index=True
    )

    rating = Column(Integer, nullable=False)

    title = Column(String, nullable=True)

    status = Column(Enum(ReviewStatus, name="review_status_enum"), nullable=False, default=ReviewStatus.PENDING)



    # Relationships
    user = relationship("User", back_populates="reviews")
    lisitng = relationship("Listing", back_populates="reviews")
    booking = relationship("Booking", back_populates="reviews")