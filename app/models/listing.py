from sqlalchemy import Column, Enum, Float, ForeignKey, String, Text, UUID
from sqlalchemy.orm import relationship

from app.models.base import Base, SoftDeleteMixin, TimestampMixin, UUIDMixin
from app.models.enum import ListingType, ListingStatus, CurrencyCode


class Listing(Base, UUIDMixin, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "listings"

    destination_id = Column(UUID(as_uuid=True), ForeignKey("destinations.id"), nullable=False, index=True)

    listing_type = Column(Enum(ListingType, name="listing_type_enum"), nullable=False, index=True)
    title = Column(String, nullable=False)
    slug = Column(String, unique=True, index=True, nullable=True)
    description = Column(Text, nullable=True)
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
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

    destination = relationship("Destination", back_populates="listings")
    media = relationship(
        "ListingMedia",
        back_populates="listing",
        cascade="all, delete-orphan",
        order_by="ListingMedia.sort_order",
    )
    variants = relationship("ListingVariant", back_populates="listing", cascade="all, delete-orphan")
    reviews = relationship("Review", back_populates="listing")
    wishlisted_by = relationship("Wishlist", back_populates="listing", cascade="all, delete-orphan")
    booking_items = relationship("BookingItem", back_populates="listing")
    cancellation_policies = relationship(
        "CancellationPolicy",
        back_populates="listing",
        cascade="all, delete-orphan",
    )
    hotel_detail = relationship(
        "HotelDetail",
        back_populates="listing",
        uselist=False,
        cascade="all, delete-orphan",
    )
    safari_detail = relationship(
        "SafariDetail",
        back_populates="listing",
        uselist=False,
        cascade="all, delete-orphan",
    )
    tour_detail = relationship(
        "TourDetail",
        back_populates="listing",
        uselist=False,
        cascade="all, delete-orphan",
    )
    transfer_detail = relationship(
        "TransferDetail",
        back_populates="listing",
        uselist=False,
        cascade="all, delete-orphan",
    )
