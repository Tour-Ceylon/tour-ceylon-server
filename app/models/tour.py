import uuid 
from sqlalchemy import Column, String, Float, ForeignKey
from app.config.database import Base
from sqlalchemy.dialects.postgresql import UUID

class Tour(Base):
    __tablename__ = "Tours"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    listing_id = Column(UUID(as_uuid=True), ForeignKey("Listings.id"))

    duration = Column(String)
    route = Column(String)
    price = Column(Float)