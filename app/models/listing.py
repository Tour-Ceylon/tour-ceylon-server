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

    @property
    def priced_variants(self) -> list:
        variants = list(self.variants or [])
        return [
            variant
            for variant in sorted(
                variants,
                key=lambda item: (
                    not item.is_default,
                    (item.pricing or {}).get("amount", float("inf")),
                    item.name.lower(),
                ),
            )
            if item.pricing is not None
        ]

    @property
    def default_variant(self):
        variants = list(self.variants or [])
        default = next((variant for variant in variants if variant.is_default), None)
        if default and default.pricing is not None:
            return default
        priced_variants = self.priced_variants
        return priced_variants[0] if priced_variants else None

    @property
    def from_price(self) -> dict | None:
        priced_variants = [
            variant for variant in list(self.variants or []) if variant.pricing is not None
        ]
        if not priced_variants:
            return None

        cheapest_variant = min(
            priced_variants,
            key=lambda item: (
                item.pricing["amount"],
                item.pricing["priority"],
                not item.is_default,
                item.name.lower(),
            ),
        )
        return {
            "amount": cheapest_variant.pricing["amount"],
            "currency": cheapest_variant.pricing["currency"],
            "priority": cheapest_variant.pricing["priority"],
            "variant_id": cheapest_variant.id,
            "variant_name": cheapest_variant.name,
            "booking_unit": cheapest_variant.booking_unit,
        }
