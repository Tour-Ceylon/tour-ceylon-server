from datetime import datetime, timezone
import uuid

from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Integer, String, Text, and_
from sqlalchemy.dialects.postgresql import JSON, UUID
from sqlalchemy.orm import foreign, relationship

from app.models.base import Base
from app.models.enum import MediaOwnerType
from app.models.media import MediaAsset


class Package(Base):
    __tablename__ = "Packages"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    name = Column(String, nullable=False)
    description = Column(Text, nullable=False)
    duration = Column(Integer, nullable=False)
    route = Column(String, nullable=False)
    base_price = Column(Float, nullable=False)
    image = Column(String, nullable=True)
    category = Column(String, nullable=False)
    includes = Column(JSON, nullable=False, default=list)
    itinerary = Column(JSON, nullable=False, default=list)
    is_active = Column(Boolean, nullable=False, default=True)

    # Structured Fields
    summary = Column(Text, nullable=True)
    nights = Column(Integer, nullable=True)
    trip_style = Column(String, nullable=True)
    start_location = Column(String, nullable=True)
    end_location = Column(String, nullable=True)
    destinations = Column(JSON, nullable=False, default=list)
    highlights = Column(JSON, nullable=False, default=list)
    exclusions = Column(JSON, nullable=False, default=list)
    quick_facts = Column(JSON, nullable=False, default=dict)
    structured_itinerary = Column(JSON, nullable=False, default=list)
    listing_refs = Column(JSON, nullable=False, default=list)

    cover_media_id = Column(UUID(as_uuid=True), ForeignKey("media_assets.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    add_ons = relationship("PackageAddOn", back_populates="package", cascade="all, delete-orphan")
    media_assets = relationship(
        "MediaAsset",
        primaryjoin=lambda: and_(
            foreign(MediaAsset.owner_id) == Package.id,
            MediaAsset.owner_type == MediaOwnerType.PACKAGE,
        ),
        order_by=lambda: (MediaAsset.sort_order, MediaAsset.created_at),
        viewonly=True,
    )
    cover_media = relationship("MediaAsset", foreign_keys=[cover_media_id], uselist=False)

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
    def normalized_structured_itinerary(self) -> list[dict]:
        return list(self.structured_itinerary or [])

    @property
    def derived_simple_itinerary(self) -> list[dict]:
        """
        Derives a simple itinerary from structured data if the latter exists.
        Ensures backward compatibility with legacy client views.
        """
        if self.normalized_structured_itinerary:
            simple_items: list[dict] = []
            for day in self.normalized_structured_itinerary:
                overview = day.get("overview")
                if overview:
                    description = overview
                else:
                    block_lines = []
                    for block in day.get("blocks", []) or []:
                        title = (block.get("title") or "").strip()
                        desc = (block.get("description") or "").strip()
                        if title and desc:
                            block_lines.append(f"{title}: {desc}")
                        elif title:
                            block_lines.append(title)
                    description = " ".join(block_lines).strip()

                simple_items.append({
                    "day": day.get("day"),
                    "title": day.get("title") or f"Day {day.get('day')}",
                    "description": description or "",
                })
            return simple_items

        return list(self.itinerary or [])


class AddOn(Base):
    __tablename__ = "AddOns"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    name = Column(String, nullable=False)
    description = Column(Text, nullable=False)
    price = Column(Float, nullable=False)
    category = Column(String, nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    package_links = relationship("PackageAddOn", back_populates="add_on", cascade="all, delete-orphan")


class PackageAddOn(Base):
    __tablename__ = "PackageAddOns"

    package_id = Column(UUID(as_uuid=True), ForeignKey("Packages.id"), primary_key=True)
    add_on_id = Column(UUID(as_uuid=True), ForeignKey("AddOns.id"), primary_key=True)

    package = relationship("Package", back_populates="add_ons")
    add_on = relationship("AddOn", back_populates="package_links")


class AdminSettings(Base):
    __tablename__ = "AdminSettings"

    id = Column(Integer, primary_key=True, autoincrement=True, index=True)
    site_name = Column(String, nullable=False, default="Tour Ceylon")
    contact_email = Column(String, nullable=False, default="support@tourceylon.com")
    default_currency = Column(String, nullable=False, default="LKR")
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
