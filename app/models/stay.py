import builtins

from sqlalchemy import Column, ForeignKey, Numeric, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship

from app.models.base import Base, TimestampMixin, UUIDMixin


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
