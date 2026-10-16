from sqlalchemy import Column, String, Text, Integer, Numeric, Boolean, ForeignKey, DateTime
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship

from app.models.base import Base, UUIDMixin, TimestampMixin


class LuggageSizeType(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "luggage_size_types"

    name = Column(String(100), nullable=False, unique=True)
    dimensions_display = Column(String(100), nullable=True)
    description = Column(Text, nullable=True)
    sort_order = Column(Integer, default=0, nullable=False)

    driver_capacities = relationship("DriverLuggageCapacity", back_populates="luggage_size_type")


class VehicleModelPreset(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "vehicle_model_presets"

    make = Column(String(100), nullable=False, index=True)
    model = Column(String(100), nullable=False, index=True)
    vehicle_category_id = Column(
        UUID(as_uuid=True),
        ForeignKey("vehicle_categories.id", ondelete="SET NULL"),
        nullable=True
    )
    default_seats = Column(Integer, nullable=False, default=4)
    default_luggage_capacity = Column(JSONB, nullable=False, default=dict)
    is_active = Column(Boolean, default=True, nullable=False)

    vehicle_category = relationship("VehicleCategory")


class Driver(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "drivers"

    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
        index=True
    )
    vendor_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True
    )

    nic_number = Column(String(50), unique=True, nullable=False, index=True)
    license_number = Column(String(50), nullable=True)
    license_photo_url = Column(Text, nullable=True)
    nic_photo_url = Column(Text, nullable=True)
    vehicle_registration_doc_url = Column(Text, nullable=True)
    insurance_doc_url = Column(Text, nullable=True)
    police_clearance_doc_url = Column(Text, nullable=True)

    vehicle_model_preset_id = Column(
        UUID(as_uuid=True),
        ForeignKey("vehicle_model_presets.id", ondelete="SET NULL"),
        nullable=True
    )
    vehicle_make = Column(String(100), nullable=False)
    vehicle_model = Column(String(100), nullable=False)
    vehicle_plate_number = Column(String(50), unique=True, nullable=False, index=True)
    seats = Column(Integer, nullable=False, default=4)

    # Status: pending_review | approved | rejected | suspended
    status = Column(String(50), nullable=False, default="pending_review", index=True)

    # Dispatch & Online Availability
    is_online = Column(Boolean, default=False, nullable=False, index=True)
    last_online_at = Column(DateTime(timezone=True), nullable=True)

    # Phase 2 fields
    base_location = Column(String(255), nullable=True)
    languages_spoken = Column(JSONB, nullable=True, default=list)
    years_experience = Column(Integer, nullable=True)
    bank_account_holder = Column(String(255), nullable=True)
    bank_name = Column(String(255), nullable=True)
    bank_account_number = Column(String(100), nullable=True)
    rating = Column(Numeric(3, 2), nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)

    # Relationships
    user = relationship("User", foreign_keys=[user_id], back_populates="driver_profile")
    vendor = relationship("User", foreign_keys=[vendor_id])
    vehicle_model_preset = relationship("VehicleModelPreset")
    luggage_capacities = relationship(
        "DriverLuggageCapacity",
        back_populates="driver",
        cascade="all, delete-orphan"
    )
    transport_bookings = relationship(
        "TransportBooking",
        back_populates="driver"
    )
    decline_reasons = relationship(
        "TripDeclineReason",
        back_populates="driver",
        cascade="all, delete-orphan"
    )


class DriverLuggageCapacity(Base, TimestampMixin):
    __tablename__ = "driver_luggage_capacity"

    driver_id = Column(
        UUID(as_uuid=True),
        ForeignKey("drivers.id", ondelete="CASCADE"),
        primary_key=True
    )
    luggage_size_type_id = Column(
        UUID(as_uuid=True),
        ForeignKey("luggage_size_types.id", ondelete="CASCADE"),
        primary_key=True
    )
    quantity = Column(Integer, default=0, nullable=False)

    driver = relationship("Driver", back_populates="luggage_capacities")
    luggage_size_type = relationship("LuggageSizeType", back_populates="driver_capacities")


class DriverProfileChangeRequest(Base, UUIDMixin, TimestampMixin):
    """A driver's proposed profile update, held until an admin approves or rejects it."""

    __tablename__ = "driver_profile_change_requests"

    driver_id = Column(
        UUID(as_uuid=True),
        ForeignKey("drivers.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # pending | approved | rejected | withdrawn
    status = Column(String(20), nullable=False, default="pending", index=True)
    # Only the fields that differ from the saved profile, e.g. {"bank_name": "...", "languages_spoken": [...]}
    proposed = Column(JSONB, nullable=False, default=dict)
    rejection_reason = Column(Text, nullable=True)
    reviewed_by_user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    reviewed_at = Column(DateTime(timezone=True), nullable=True)

    driver = relationship("Driver")


class TransportBookingDriverNote(Base, UUIDMixin, TimestampMixin):
    """A note an admin writes for the driver assigned to a booking (one editable note per booking)."""

    __tablename__ = "transport_booking_driver_notes"

    booking_id = Column(
        UUID(as_uuid=True),
        ForeignKey("transport_bookings.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
        index=True,
    )
    note = Column(Text, nullable=False)
    updated_by_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)


class DriverAvatarSubmission(Base, UUIDMixin, TimestampMixin):
    """A profile photo a driver uploaded; shown only once an admin approves it."""

    __tablename__ = "driver_avatar_submissions"

    driver_id = Column(UUID(as_uuid=True), ForeignKey("drivers.id", ondelete="CASCADE"), nullable=False, index=True)
    image_url = Column(Text, nullable=False)
    cloudinary_public_id = Column(String(255), nullable=True)
    # pending | approved | rejected | withdrawn
    status = Column(String(20), nullable=False, default="pending", index=True)
    rejection_reason = Column(Text, nullable=True)
    reviewed_by_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    reviewed_at = Column(DateTime(timezone=True), nullable=True)


class TripDeclineReason(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "trip_decline_reasons"

    transport_booking_id = Column(
        UUID(as_uuid=True),
        ForeignKey("transport_bookings.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    driver_id = Column(
        UUID(as_uuid=True),
        ForeignKey("drivers.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    reason = Column(String(255), nullable=False)
    note = Column(Text, nullable=True)

    transport_booking = relationship("TransportBooking", back_populates="decline_reasons")
    driver = relationship("Driver", back_populates="decline_reasons")
