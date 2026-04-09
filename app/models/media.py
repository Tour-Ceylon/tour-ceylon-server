from sqlalchemy import Boolean, Column, Enum, Integer, String, UUID

from app.models.base import Base, TimestampMixin, UUIDMixin
from app.models.enum import MediaAssetStatus, MediaOwnerType


class MediaAsset(Base, UUIDMixin, TimestampMixin):
    """Centralized media metadata for Cloudinary-backed assets."""

    __tablename__ = "media_assets"

    owner_type = Column(
        Enum(MediaOwnerType, name="media_owner_type_enum"),
        nullable=False,
        index=True,
    )
    owner_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    cloudinary_public_id = Column(String, nullable=False, unique=True)
    secure_url = Column(String, nullable=False)
    resource_type = Column(String, nullable=False, default="image")
    format = Column(String, nullable=True)
    width = Column(Integer, nullable=True)
    height = Column(Integer, nullable=True)
    bytes = Column(Integer, nullable=True)
    alt_text = Column(String, nullable=True)
    sort_order = Column(Integer, nullable=False, default=0)
    is_primary = Column(Boolean, nullable=False, default=False)
    status = Column(
        Enum(MediaAssetStatus, name="media_asset_status_enum"),
        nullable=False,
        default=MediaAssetStatus.ACTIVE,
    )
