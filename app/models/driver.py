from sqlalchemy import Column, String, Text, Integer, Numeric, Boolean, ForeignKey
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
