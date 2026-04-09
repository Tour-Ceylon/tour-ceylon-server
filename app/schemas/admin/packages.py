from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.media_schema import MediaAssetPublicResponse, MediaSummary


class PackageItineraryItem(BaseModel):
    day: int
    title: str
    description: str


class PackageBase(BaseModel):
    name: str
    description: str
    duration: int
    route: str
    basePrice: float
    image: str | None = None
    category: str
    includes: list[str]
    itinerary: list[PackageItineraryItem]
    addOns: list[str]
    isActive: bool = True


class PackageCreate(PackageBase):
    pass


class PackageUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    duration: int | None = None
    route: str | None = None
    basePrice: float | None = None
    image: str | None = None
    category: str | None = None
    includes: list[str] | None = None
    itinerary: list[PackageItineraryItem] | None = None
    addOns: list[str] | None = None
    isActive: bool | None = None


class PackageResponse(PackageBase):
    id: UUID
    image: str | None = Field(default=None, exclude=True)
    cover_image: MediaSummary | None = None
    gallery: list[MediaAssetPublicResponse] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)
