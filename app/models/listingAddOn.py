from sqlalchemy import Boolean, Column, ForeignKey, Numeric, String, Text
from sqlalchemy.dialects.postgresql import UUID

from app.models.base import Base, TimestampMixin, UUIDMixin


class ListingAddOn(Base, UUIDMixin, TimestampMixin):
    """An optional extra a guest can add to a listing (airport pickup, packed lunch, ...).

    FEAT-3. The earlier add-on and "include" models were removed and their repositories left
    as stubs, so nothing was stored. `room_id` optionally ties an add-on to one stay room type.
    """

    __tablename__ = "listing_addons"

    listing_id = Column(UUID(as_uuid=True), ForeignKey("listings.id", ondelete="CASCADE"), nullable=False, index=True)
    room_id = Column(UUID(as_uuid=True), nullable=True)
    name = Column(String(150), nullable=False)
    description = Column(Text, nullable=True)
    price = Column(Numeric(10, 2), nullable=False, default=0)
    base_currency = Column(String(3), nullable=False, default="USD")
    is_active = Column(Boolean, nullable=False, default=True)
