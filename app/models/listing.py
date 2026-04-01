from datetime import datetime, timezone
import uuid

from sqlalchemy import Boolean, Column, DateTime, Enum, Float, Integer, String, Text,ForeignKey, UUID


from app.config.database import Base
from app.models.base import Base, UUIDMixin, TimestampMixin, SoftDeleteMixin
from app.models.enum import ListingType, ListingStatus, CurrencyCode


class Listing(Base, UUIDMixin, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "Listings"

    destination_id = Column(UUID(as_uuid=True), ForeignKey("Destination.id"), nullable=False, index=True, unique=True)

    listing_type = Column(Enum(ListingType), nullable=False, index=True)
    title = Column(String, nullable=False)
    slug = Column(String, unique=True, index=True, nullable=True)
    description = Column(Text, nullable=True)
    status = Column(
        Enum(ListingStatus, name="listing_status_enum"),
        default=ListingStatus.DRAFT,
        nullable=False
    )
    base_currency = Column(
        Enum(CurrencyCode, name="currency_code_enum"),
        default=CurrencyCode.USD,
        nullable=False
    )

