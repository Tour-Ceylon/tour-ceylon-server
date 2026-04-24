from sqlalchemy import Boolean, Column, Enum, ForeignKey, Integer, JSON, String, Time, UUID
from sqlalchemy.orm import relationship

from app.models.base import Base, UUIDMixin
from app.models.enum import DestinationType, TransferLocationType



class TransferDetail(Base, UUIDMixin):
    __tablename__ = "transfer_details"


    listing_id = Column(UUID(as_uuid=True), ForeignKey("listings.id"), nullable=False, index=True, unique=True)

    origin_type = Column(
        Enum(TransferLocationType, name="transfer_location_type_enum"),
        nullable=False
    )

    destination_type = Column(
        Enum(DestinationType, name="destination_type_enum"),
        nullable=False
    )

    vehicle_policy = Column(String, nullable=False)
    vehicle_types = Column(JSON, nullable=True)
    max_passengers = Column(Integer, nullable=True)
    max_luggage = Column(Integer, nullable=True)
    air_conditioned = Column(Boolean, nullable=True)
    meet_and_greet_included = Column(Boolean, nullable=True)
    child_seats_available = Column(Boolean, nullable=True)
    pickup_instructions = Column(String, nullable=True)
    dropoff_instructions = Column(String, nullable=True)
    operating_start_time = Column(Time, nullable=True)
    operating_end_time = Column(Time, nullable=True)
    estimated_duration_minutes = Column(Integer, nullable=True)
    route_notes = Column(String, nullable=True)
    included_items = Column(JSON, nullable=True)
    excluded_items = Column(JSON, nullable=True)
    cancellation_policy = Column(String, nullable=True)
    waiting_time_policy = Column(String, nullable=True)

    listing = relationship("Listing", back_populates="transfer_detail")
