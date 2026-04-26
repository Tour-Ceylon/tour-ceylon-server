from pydantic import BaseModel

from app.schemas.admin.addons import AddOnResponse
from app.schemas.admin.listings import (
    ExperienceListingResponse,
    SafariListingResponse,
    StayListingResponse,
    TourListingResponse,
    TransferListingResponse,
)
from app.schemas.admin.packages import PackageResponse
from app.schemas.admin.settings import AdminSettingsResponse


class SnapshotListingsResponse(BaseModel):
    stay: list[StayListingResponse]
    tour: list[TourListingResponse]
    experience: list[ExperienceListingResponse]
    safari: list[SafariListingResponse]
    transfer: list[TransferListingResponse]


class AdminSnapshotResponse(BaseModel):
    packages: list[PackageResponse]
    addOns: list[AddOnResponse]
    settings: AdminSettingsResponse
    listings: SnapshotListingsResponse

