from sqlalchemy import Column, Enum, String, ForeignKey, UUID
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

    listing = relationship("Listing", back_populates="transfer_detail")
