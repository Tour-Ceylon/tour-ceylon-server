from sqlalchemy import Column, String, Enum, Boolean
from sqlalchemy.orm import relationship

from app.models.base import Base, UUIDMixin, TimestampMixin, SoftDeleteMixin
from app.models.enum import UserRole


class User(Base, UUIDMixin, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "users"

    # Core fields
    email = Column(String, unique=True, nullable=False, index=True)
    full_name = Column(String, nullable=True)
    country = Column(String, nullable=True)

    # Role
    role = Column(
        Enum(UserRole, name="user_role_enum"),
        default=UserRole.TOURIST,
        nullable=False
    )

    # Relationships (based on your ERD)
    bookings = relationship("Booking", back_populates="user")
    wishlists = relationship("Wishlist", back_populates="user")
    reviews = relationship("Review", back_populates="user")