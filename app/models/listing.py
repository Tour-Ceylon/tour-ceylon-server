from sqlalchemy import Column, Enum, Float, ForeignKey, String, Text, UUID, and_
from sqlalchemy.orm import foreign, relationship

from app.models.base import Base, SoftDeleteMixin, TimestampMixin, UUIDMixin
from app.models.enum import CurrencyCode, ListingStatus, ListingType, MediaOwnerType
from app.models.media import MediaAsset


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
    cover_media_id = Column(UUID(as_uuid=True), ForeignKey("media_assets.id"), nullable=True)

    destination = relationship("Destination", back_populates="listings")
    media = relationship(
        "ListingMedia",
        back_populates="listing",
        cascade="all, delete-orphan",
        order_by="ListingMedia.sort_order",
    )
    media_assets = relationship(
        "MediaAsset",
        primaryjoin=lambda: and_(
            foreign(MediaAsset.owner_id) == Listing.id,
            MediaAsset.owner_type == MediaOwnerType.LISTING,
        ),
        order_by=lambda: (MediaAsset.sort_order, MediaAsset.created_at),
        viewonly=True,
    )
    cover_media = relationship("MediaAsset", foreign_keys=[cover_media_id], uselist=False)
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

    @property
    def ordered_media_assets(self) -> list[MediaAsset]:
        return sorted(
            list(self.media_assets or []),
            key=lambda media: (media.sort_order, media.created_at),
        )

    @property
    def cover_image(self) -> dict | None:
        media = self.cover_media or next(
            (item for item in self.ordered_media_assets if item.is_primary),
            None,
        )
        if media is None:
            return None
        return {
            "id": media.id,
            "url": media.secure_url,
            "alt_text": media.alt_text,
        }

    @property
    def gallery(self) -> list[dict]:
        return [
            {
                "id": media.id,
                "url": media.secure_url,
                "alt_text": media.alt_text,
                "sort_order": media.sort_order,
                "is_primary": media.is_primary,
                "width": media.width,
                "height": media.height,
                "format": media.format,
            }
            for media in self.ordered_media_assets
        ]
