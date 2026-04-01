from sqlalchemy import Column, Enum, String, ForeignKey, UUID, Integer
from sqlalchemy.orm import relationship

from app.models.base import Base, UUIDMixin



class TransferDetail(Base, UUIDMixin):
    __tablename__ = "transfer_details"


    listing_id = Column(UUID(as_uuid=True), ForeignKey("Listings.id"),nullable=False, index=True, unique=True)

    duration_days = Column(Integer, nullable=False)
    
    route_summary = Column(String, nullable=False)

    meeting_point = Column(String, nullable=False)

    