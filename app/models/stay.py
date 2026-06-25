import builtins

from sqlalchemy import Column, Date, Enum, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship

from app.models.base import Base, TimestampMixin, UUIDMixin
from app.models.enum import StayBookingStatus, StayRoomBlockStatus, StayRoomBlockType


class StayProperty(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "stay_properties"

    vendor_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    listing_id = Column(UUID(as_uuid=True), ForeignKey("listings.id"), nullable=True, index=True)

    name = Column(String(255), nullable=False)
    property_type = Column(String(80), nullable=False)
    description = Column(Text, nullable=True)
    address = Column(Text, nullable=True)
    city = Column(String(120), nullable=True, index=True)
    district = Column(String(120), nullable=True)
    latitude = Column(Numeric(10, 7), nullable=True)
    longitude = Column(Numeric(10, 7), nullable=True)
    status = Column(String(50), nullable=False, default="draft", index=True)
    application_note = Column(Text, nullable=True)
    contact = Column(JSONB, nullable=False, default=dict)
    policies = Column(JSONB, nullable=False, default=dict)
    media = Column(JSONB, nullable=False, default=list)
    metadata_json = Column("metadata", JSONB, nullable=False, default=dict)

    vendor = relationship("User")
    listing = relationship("Listing")
    amenities = relationship(
        "StayPropertyAmenityMap",
        back_populates="property",
        cascade="all, delete-orphan",
    )
    room_types = relationship(
        "StayRoomType",
        back_populates="property",
        cascade="all, delete-orphan",
    )
    room_units = relationship(
        "StayRoomUnit",
        back_populates="property",
        cascade="all, delete-orphan",
    )
    stay_bookings = relationship(
        "StayBooking",
        back_populates="property",
        cascade="all, delete-orphan",
    )
    room_blocks = relationship(
        "StayRoomBlock",
        back_populates="property",
        cascade="all, delete-orphan",
    )
    room_type_calendar_entries = relationship(
        "StayRoomTypeCalendar",
        back_populates="property",
        cascade="all, delete-orphan",
    )


class StayPropertyAmenity(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "stay_property_amenities"
    __table_args__ = (UniqueConstraint("name", name="uq_stay_property_amenities_name"),)

    name = Column(String(120), nullable=False)
    description = Column(Text, nullable=True)
    value_type = Column(String(40), nullable=False, default="boolean")
    category = Column(String(80), nullable=True)

    property_maps = relationship("StayPropertyAmenityMap", back_populates="amenity")


class StayPropertyAmenityMap(Base, TimestampMixin):
    __tablename__ = "stay_property_amenity_map"

    property_id = Column(
        UUID(as_uuid=True),
        ForeignKey("stay_properties.id", ondelete="CASCADE"),
        primary_key=True,
    )
    amenity_id = Column(
        UUID(as_uuid=True),
        ForeignKey("stay_property_amenities.id"),
        primary_key=True,
    )
    value = Column(JSONB, nullable=False, default=dict)

    property = relationship("StayProperty", back_populates="amenities")
    amenity = relationship("StayPropertyAmenity", back_populates="property_maps")

    @builtins.property
    def id(self):
        return self.amenity_id

    @builtins.property
    def name(self):
        return self.amenity.name

    @builtins.property
    def category(self):
        return self.amenity.category

    @builtins.property
    def value_type(self):
        return self.amenity.value_type

    @builtins.property
    def flattened_value(self):
        if isinstance(self.value, dict) and set(self.value.keys()) == {"value"}:
            return self.value["value"]
        return self.value


class StayRoomType(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "stay_room_types"
    __table_args__ = (UniqueConstraint("property_id", "name", name="uq_stay_room_types_property_name"),)

    property_id = Column(UUID(as_uuid=True), ForeignKey("stay_properties.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(160), nullable=False)
    description = Column(Text, nullable=True)
    size = Column(String(80), nullable=True)
    size_unit = Column(String(20), nullable=True)
    max_guests = Column(String(40), nullable=True)
    base_price = Column(Numeric(12, 2), nullable=True)
    currency = Column(String(10), nullable=False, default="LKR")
    bed_configuration = Column(JSONB, nullable=False, default=dict)
    bathroom = Column(JSONB, nullable=False, default=dict)
    discounts = Column(JSONB, nullable=False, default=list)
    metadata_json = Column("metadata", JSONB, nullable=False, default=dict)

    property = relationship("StayProperty", back_populates="room_types")
    room_units = relationship(
        "StayRoomUnit",
        back_populates="room_type",
        cascade="all, delete-orphan",
    )
    calendar_entries = relationship(
        "StayRoomTypeCalendar",
        back_populates="room_type",
        cascade="all, delete-orphan",
    )
    booking_rooms = relationship("StayBookingRoom", back_populates="room_type")


class StayRoomUnit(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "stay_room_units"
    __table_args__ = (UniqueConstraint("property_id", "room_number", name="uq_stay_room_units_property_room_number"),)

    property_id = Column(UUID(as_uuid=True), ForeignKey("stay_properties.id", ondelete="CASCADE"), nullable=False, index=True)
    room_type_id = Column(UUID(as_uuid=True), ForeignKey("stay_room_types.id", ondelete="CASCADE"), nullable=False, index=True)
    room_number = Column(String(80), nullable=False)
    floor = Column(String(80), nullable=True)
    room_name = Column(String(160), nullable=True)
    status = Column(String(50), nullable=False, default="available")
    metadata_json = Column("metadata", JSONB, nullable=False, default=dict)

    property = relationship("StayProperty", back_populates="room_units")
    room_type = relationship("StayRoomType", back_populates="room_units")
    booking_rooms = relationship("StayBookingRoom", back_populates="room_unit")
    room_blocks = relationship("StayRoomBlock", back_populates="room_unit")


class StayRoomProp(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "stay_room_props"
    __table_args__ = (UniqueConstraint("name", name="uq_stay_room_props_name"),)

    name = Column(String(120), nullable=False)
    description = Column(Text, nullable=True)
    value_type = Column(String(40), nullable=False, default="json")
    category = Column(String(80), nullable=True)

    room_maps = relationship("StayRoomPropMap", back_populates="prop")


class StayRoomPropMap(Base, TimestampMixin):
    __tablename__ = "stay_room_prop_map"

    room_id = Column(
        UUID(as_uuid=True),
        ForeignKey("stay_room_units.id", ondelete="CASCADE"),
        primary_key=True,
    )
    prop_id = Column(UUID(as_uuid=True), ForeignKey("stay_room_props.id"), primary_key=True)
    value = Column(JSONB, nullable=False, default=dict)

    room = relationship("StayRoomUnit")
    prop = relationship("StayRoomProp", back_populates="room_maps")


class StayBooking(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "stay_bookings"

    booking_id = Column(UUID(as_uuid=True), ForeignKey("bookings.id", ondelete="CASCADE"), nullable=False, index=True)
    property_id = Column(UUID(as_uuid=True), ForeignKey("stay_properties.id", ondelete="CASCADE"), nullable=False, index=True)
    status = Column(Enum(StayBookingStatus, name="stay_booking_status_enum"), nullable=False, default=StayBookingStatus.PENDING)
    check_in_date = Column(Date, nullable=False, index=True)
    check_out_date = Column(Date, nullable=False, index=True)
    guest_name = Column(String(255), nullable=False)
    guest_email = Column(String(255), nullable=True)
    guest_phone = Column(String(80), nullable=True)
    special_requests = Column(Text, nullable=True)
    metadata_json = Column("metadata", JSONB, nullable=False, default=dict)

    booking = relationship("Booking", back_populates="stay_bookings")
    property = relationship("StayProperty", back_populates="stay_bookings")
    rooms = relationship(
        "StayBookingRoom",
        back_populates="stay_booking",
        cascade="all, delete-orphan",
    )


class StayBookingRoom(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "stay_booking_rooms"

    stay_booking_id = Column(UUID(as_uuid=True), ForeignKey("stay_bookings.id", ondelete="CASCADE"), nullable=False, index=True)
    room_unit_id = Column(UUID(as_uuid=True), ForeignKey("stay_room_units.id", ondelete="RESTRICT"), nullable=False, index=True)
    room_type_id = Column(UUID(as_uuid=True), ForeignKey("stay_room_types.id", ondelete="RESTRICT"), nullable=False, index=True)
    check_in_date = Column(Date, nullable=False, index=True)
    check_out_date = Column(Date, nullable=False, index=True)
    nightly_rate = Column(Numeric(12, 2), nullable=False)
    guests = Column(Integer, nullable=False, default=1)
    metadata_json = Column("metadata", JSONB, nullable=False, default=dict)

    stay_booking = relationship("StayBooking", back_populates="rooms")
    room_unit = relationship("StayRoomUnit", back_populates="booking_rooms")
    room_type = relationship("StayRoomType", back_populates="booking_rooms")


class StayRoomBlock(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "stay_room_blocks"

    property_id = Column(UUID(as_uuid=True), ForeignKey("stay_properties.id", ondelete="CASCADE"), nullable=False, index=True)
    room_unit_id = Column(UUID(as_uuid=True), ForeignKey("stay_room_units.id", ondelete="CASCADE"), nullable=False, index=True)
    start_date = Column(Date, nullable=False, index=True)
    end_date = Column(Date, nullable=False, index=True)
    block_type = Column(Enum(StayRoomBlockType, name="stay_room_block_type_enum"), nullable=False, default=StayRoomBlockType.MANUAL)
    status = Column(Enum(StayRoomBlockStatus, name="stay_room_block_status_enum"), nullable=False, default=StayRoomBlockStatus.ACTIVE)
    reason = Column(Text, nullable=True)
    blocked_by_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True, index=True)
    metadata_json = Column("metadata", JSONB, nullable=False, default=dict)

    property = relationship("StayProperty", back_populates="room_blocks")
    room_unit = relationship("StayRoomUnit", back_populates="room_blocks")
    blocked_by_user = relationship("User")


class StayRoomTypeCalendar(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "stay_room_type_calendar"
    __table_args__ = (
        UniqueConstraint("property_id", "room_type_id", "stay_date", name="uq_stay_room_type_calendar_date"),
    )

    property_id = Column(UUID(as_uuid=True), ForeignKey("stay_properties.id", ondelete="CASCADE"), nullable=False, index=True)
    room_type_id = Column(UUID(as_uuid=True), ForeignKey("stay_room_types.id", ondelete="CASCADE"), nullable=False, index=True)
    stay_date = Column(Date, nullable=False, index=True)
    total_units = Column(Integer, nullable=False, default=0)
    booked_units = Column(Integer, nullable=False, default=0)
    blocked_units = Column(Integer, nullable=False, default=0)
    available_units = Column(Integer, nullable=False, default=0)

    property = relationship("StayProperty", back_populates="room_type_calendar_entries")
    room_type = relationship("StayRoomType", back_populates="calendar_entries")
