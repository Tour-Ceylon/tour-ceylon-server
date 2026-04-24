from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class MediaSummary(BaseModel):
    id: UUID
    url: str
    alt_text: str | None = None


class MediaAssetResponse(BaseModel):
    id: UUID
    secure_url: str
    alt_text: str | None = None
    is_primary: bool
    sort_order: int
    width: int | None = None
    height: int | None = None
    format: str | None = None

    model_config = ConfigDict(from_attributes=True)


class MediaAssetPublicResponse(BaseModel):
    id: UUID
    url: str
    alt_text: str | None = None
    sort_order: int
    is_primary: bool
    width: int | None = None
    height: int | None = None
    format: str | None = None


class MediaAssetListResponse(BaseModel):
    id: UUID
    cover_image: MediaSummary | None = None
    gallery: list[MediaAssetPublicResponse] = Field(default_factory=list)


class MediaUploadResponse(MediaAssetListResponse):
    pass


class MediaPrimaryUpdateRequest(BaseModel):
    is_primary: bool = True


class MediaReorderItem(BaseModel):
    id: UUID
    sort_order: int


class MediaReorderRequest(BaseModel):
    items: list[MediaReorderItem]
