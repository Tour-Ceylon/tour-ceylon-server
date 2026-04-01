from sqlalchemy import Column, Enum, String, ForeignKey, UUID
from sqlalchemy.orm import relationship

from app.models.base import Base, UUIDMixin, TimestampMixin
from app.models.enum import TransferLocationType, DestinationType


class TourDetails(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "cancellation_policies"


    listing_id = Column(UUID(as_uuid=True), ForeignKey("Listings.id"),nullable=False, index=True, unique=True)

    transfer_location_type = Column(
        Enum(TransferLocationType, name="transfer_location_type_enum"),
        nullable=False
    )

    destination_type = Column(
        Enum(DestinationType, name="destination_type_enum"),
        nullable=False
    )

    vehicle_policy = Column(String, nullable=False)