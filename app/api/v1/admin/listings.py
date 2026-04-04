from uuid import UUID

from fastapi import APIRouter, Depends, Response, status

from app.api.v1.admin.dependencies import get_admin_service
from app.schemas.admin.listings import (
    ActivityListingCreate,
    ActivityListingResponse,
    ListingUpdateRequest,
    AdminListingCategory,
    StayListingCreate,
    StayListingResponse,
    TourListingCreate,
    TourListingResponse,
    TransferListingCreate,
    TransferListingResponse,
)
from app.services.admin.dashboard_service import AdminDashboardService

router = APIRouter(prefix="/listings", tags=["admin-listings"])

AdminListingResponse = (
    StayListingResponse
    | TourListingResponse
    | ActivityListingResponse
    | TransferListingResponse
)


@router.post(
    "/stay",
    response_model=StayListingResponse,
    response_model_by_alias=True,
    status_code=status.HTTP_201_CREATED,
)
async def create_stay_listing(
    payload: StayListingCreate,
    service: AdminDashboardService = Depends(get_admin_service),
):
    return service.create_listing("stay", payload.model_dump(by_alias=False))


@router.post(
    "/tour",
    response_model=TourListingResponse,
    response_model_by_alias=True,
    status_code=status.HTTP_201_CREATED,
)
async def create_tour_listing(
    payload: TourListingCreate,
    service: AdminDashboardService = Depends(get_admin_service),
):
    return service.create_listing("tour", payload.model_dump(by_alias=False))


@router.post(
    "/activity",
    response_model=ActivityListingResponse,
    response_model_by_alias=True,
    status_code=status.HTTP_201_CREATED,
)
async def create_activity_listing(
    payload: ActivityListingCreate,
    service: AdminDashboardService = Depends(get_admin_service),
):
    return service.create_listing("activity", payload.model_dump(by_alias=False))


@router.post(
    "/transfer",
    response_model=TransferListingResponse,
    response_model_by_alias=True,
    status_code=status.HTTP_201_CREATED,
)
async def create_transfer_listing(
    payload: TransferListingCreate,
    service: AdminDashboardService = Depends(get_admin_service),
):
    return service.create_listing("transfer", payload.model_dump(by_alias=False))


@router.patch(
    "/{category}/{listing_id}",
    response_model=AdminListingResponse,
    response_model_by_alias=True,
)
async def update_listing(
    category: AdminListingCategory,
    listing_id: UUID,
    payload: ListingUpdateRequest,
    service: AdminDashboardService = Depends(get_admin_service),
):
    return service.update_listing(
        category,
        listing_id,
        payload.model_dump(by_alias=False, exclude_unset=True),
    )


@router.delete("/{category}/{listing_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_listing(
    category: AdminListingCategory,
    listing_id: UUID,
    service: AdminDashboardService = Depends(get_admin_service),
):
    service.delete_listing(category, listing_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
