from pydantic import BaseModel

from app.schemas.admin.addons import AddOnResponse
from app.schemas.admin.listings import (
    ActivityListingResponse,
    StayListingResponse,
    TourListingResponse,
    TransferListingResponse,
)
from app.schemas.admin.packages import PackageResponse
from app.schemas.admin.settings import AdminSettingsResponse


class SnapshotListingsResponse(BaseModel):
    stay: list[StayListingResponse]
    tour: list[TourListingResponse]
    activity: list[ActivityListingResponse]
    transfer: list[TransferListingResponse]


class AdminSnapshotResponse(BaseModel):
    packages: list[PackageResponse]
    addOns: list[AddOnResponse]
    settings: AdminSettingsResponse
    listings: SnapshotListingsResponse

