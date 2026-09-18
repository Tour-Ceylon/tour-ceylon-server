from sqlalchemy import Column, String, Date, ForeignKey, UUID
from sqlalchemy.orm import relationship

from app.models.base import Base, UUIDMixin, TimestampMixin

class ListingBlock(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "listing_blocks"

    listing_id = Column(UUID(as_uuid=True), ForeignKey("listings.id"), nullable=False, index=True)
    variant_id = Column(UUID(as_uuid=True), ForeignKey("listing_variants.id"), nullable=True, index=True)
    
    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=False)
    reason = Column(String, nullable=True)
    block_type = Column(String, nullable=True)

    listing = relationship("Listing", backref="blocks")
    variant = relationship("ListingVariant", backref="blocks")
