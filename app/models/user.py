from sqlalchemy import Column, String, Enum, Boolean
from sqlalchemy.types import TypeDecorator
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship

from app.models.base import Base, UUIDMixin, TimestampMixin, SoftDeleteMixin
from app.models.enum import UserRole


class UserRoleType(TypeDecorator):
    """
    Handles UserRole enum conversion case-insensitively and safely.
    Always binds to and returns uppercase UserRole: VENDOR, ADMIN, DRIVER, TOURIST.
    """
    impl = String(50)
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        if isinstance(value, UserRole):
            return value.value
        val_str = str(value).strip().upper()
        if hasattr(UserRole, val_str):
            return UserRole[val_str].value
        return UserRole.TOURIST.value

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        if isinstance(value, UserRole):
            return value
        val_str = str(value).strip().upper()
        if hasattr(UserRole, val_str):
            return UserRole[val_str]
        return UserRole.TOURIST


class User(Base, UUIDMixin, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "users"

    # Core fields
    clerk_user_id = Column(String, unique=True, nullable=True, index=True)
    email = Column(String, unique=True, nullable=False, index=True)
    full_name = Column(String, nullable=True)
    country = Column(String, nullable=True)

    # Role — DB is source of truth; Clerk metadata is synced FROM here
    role = Column(
        UserRoleType(),
        default=UserRole.TOURIST,
        nullable=False
    )

    # Vendor fields
    # vendor_status: "pending" | "approved" | "rejected" | "suspended"
    vendor_status = Column(String(50), nullable=True, default=None)
    # approved_categories: list of strings e.g. ["Stay", "Tour", "Safari"]
    approved_categories = Column(JSONB, nullable=False, default=list)
    # company_name: business/company name for vendor profile
    company_name = Column(String(255), nullable=True, default=None)
    # business_profile: flexible JSON blob for extra vendor business details
    business_profile = Column(JSONB, nullable=False, default=dict)

    # Relationships (based on your ERD)
    bookings = relationship("Booking", back_populates="user")
    wishlists = relationship("Wishlist", back_populates="user")
    reviews = relationship("Review", back_populates="user")
    transport_bookings = relationship("TransportBooking", back_populates="user")
    driver_profile = relationship("Driver", foreign_keys="Driver.user_id", back_populates="user", uselist=False, cascade="all, delete-orphan")
    changed_booking_statuses = relationship(
        "BookingStatusHistory",
        back_populates="changed_by_user",
        foreign_keys="BookingStatusHistory.changed_by_user_id",
    )
