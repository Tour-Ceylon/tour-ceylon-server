from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, Response, UploadFile, status

from app.api.deps import get_current_user

from app.api.errors import AdminAPIError
from app.api.v1.admin.dependencies import get_admin_service, get_media_service
from app.models.enum import ListingType, MediaOwnerType
from app.schemas.admin.listings import (
    SafariListingCreate,
    SafariListingResponse,
    ExperienceListingCreate,
    ExperienceListingResponse,
    ListingUpdateRequest,
    ListingStatusUpdateRequest,
    AdminListingCategory,
    StayListingCreate,
    StayListingResponse,
    TourListingCreate,
    TourListingResponse,
    TransferListingCreate,
    TransferListingResponse,
)
from app.schemas.media_schema import MediaAltTextUpdateRequest, MediaAssetListResponse, MediaPrimaryUpdateRequest, MediaReorderRequest, MediaUploadResponse
from app.services.admin.dashboard_service import AdminDashboardService
from app.services.media_service import MediaService
from app.models.user import User

router = APIRouter(prefix="/listings", tags=["admin-listings"])

AdminListingResponse = (
    StayListingResponse
    | TourListingResponse
    | SafariListingResponse
    | ExperienceListingResponse
    | TransferListingResponse
)

LISTING_TYPE_MAP = {
    "stay": ListingType.HOTEL,
    "tour": ListingType.TOUR,
    "safari": ListingType.SAFARI,
    "experience": ListingType.EXPERIENCE,
    "transfer": ListingType.TRANSFER,
}


def _ensure_category_matches_listing(service: MediaService, category: str, listing_id: UUID):
    listing = service.listing_repo.get_by_id(listing_id)
    if listing is None or listing.listing_type != LISTING_TYPE_MAP[category]:
        raise AdminAPIError(status_code=status.HTTP_404_NOT_FOUND, message="Listing not found")
    return listing


@router.post(
    "/stay",
    response_model=StayListingResponse,
    response_model_by_alias=True,
    status_code=status.HTTP_201_CREATED,
)
@router.post(
    "/stay/",
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
@router.post(
    "/tour/",
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
    "/safari",
    response_model=SafariListingResponse,
    response_model_by_alias=True,
    status_code=status.HTTP_201_CREATED,
)
@router.post(
    "/safari/",
    response_model=SafariListingResponse,
    response_model_by_alias=True,
    status_code=status.HTTP_201_CREATED,
)
async def create_safari_listing(
    payload: SafariListingCreate,
    service: AdminDashboardService = Depends(get_admin_service),
):
    return service.create_listing("safari", payload.model_dump(by_alias=False))


@router.post(
    "/experience",
    response_model=ExperienceListingResponse,
    response_model_by_alias=True,
    status_code=status.HTTP_201_CREATED,
)
@router.post(
    "/experience/",
    response_model=ExperienceListingResponse,
    response_model_by_alias=True,
    status_code=status.HTTP_201_CREATED,
)
async def create_experience_listing(
    payload: ExperienceListingCreate,
    service: AdminDashboardService = Depends(get_admin_service),
):
    return service.create_listing("experience", payload.model_dump(by_alias=False))


@router.post(
    "/transfer",
    response_model=TransferListingResponse,
    response_model_by_alias=True,
    status_code=status.HTTP_201_CREATED,
)
@router.post(
    "/transfer/",
    response_model=TransferListingResponse,
    response_model_by_alias=True,
    status_code=status.HTTP_201_CREATED,
)
async def create_transfer_listing(
    payload: TransferListingCreate,
    service: AdminDashboardService = Depends(get_admin_service),
):
    return service.create_listing("transfer", payload.model_dump(by_alias=False))


@router.get(
    "/stay",
    response_model=list[StayListingResponse],
    response_model_by_alias=True,
)
@router.get(
    "/stay/",
    response_model=list[StayListingResponse],
    response_model_by_alias=True,
)
async def get_stay_listings(
    service: AdminDashboardService = Depends(get_admin_service),
    current_user: User = Depends(get_current_user),
):
    return service.get_listings("stay", current_user)


@router.get(
    "/tour",
    response_model=list[TourListingResponse],
    response_model_by_alias=True,
)
@router.get(
    "/tour/",
    response_model=list[TourListingResponse],
    response_model_by_alias=True,
)
async def get_tour_listings(
    service: AdminDashboardService = Depends(get_admin_service),
    current_user: User = Depends(get_current_user),
):
    return service.get_listings("tour", current_user)


@router.get(
    "/safari",
    response_model=list[SafariListingResponse],
    response_model_by_alias=True,
)
@router.get(
    "/safari/",
    response_model=list[SafariListingResponse],
    response_model_by_alias=True,
)
async def get_safari_listings(
    service: AdminDashboardService = Depends(get_admin_service),
    current_user: User = Depends(get_current_user),
):
    return service.get_listings("safari", current_user)


@router.get(
    "/experience",
    response_model=list[ExperienceListingResponse],
    response_model_by_alias=True,
)
@router.get(
    "/experience/",
    response_model=list[ExperienceListingResponse],
    response_model_by_alias=True,
)
async def get_experience_listings(
    service: AdminDashboardService = Depends(get_admin_service),
    current_user: User = Depends(get_current_user),
):
    return service.get_listings("experience", current_user)


@router.get(
    "/transfer",
    response_model=list[TransferListingResponse],
    response_model_by_alias=True,
)
@router.get(
    "/transfer/",
    response_model=list[TransferListingResponse],
    response_model_by_alias=True,
)
async def get_transfer_listings(
    service: AdminDashboardService = Depends(get_admin_service),
    current_user: User = Depends(get_current_user),
):
    return service.get_listings("transfer", current_user)


@router.patch(
    "/{category}/{listing_id}/status",
    response_model=AdminListingResponse,
    response_model_by_alias=True,
)
async def update_listing_status(
    category: AdminListingCategory,
    listing_id: UUID,
    payload: ListingStatusUpdateRequest,
    service: AdminDashboardService = Depends(get_admin_service),
):
    return service.update_listing_status(category, listing_id, payload.status)


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


@router.post(
    "/{category}/{listing_id}/media",
    response_model=MediaUploadResponse,
    status_code=status.HTTP_201_CREATED,
)
async def upload_listing_media(
    category: AdminListingCategory,
    listing_id: UUID,
    files: list[UploadFile] = File(...),
    alt_texts: list[str] | None = Form(None),
    is_primary: bool = Form(False),
    sort_orders: list[int] | None = Form(None),
    service: MediaService = Depends(get_media_service),
):
    _ensure_category_matches_listing(service, category, listing_id)
    return service.upload_listing_media(listing_id, files, alt_texts, is_primary, sort_orders)


@router.get(
    "/{category}/{listing_id}/media",
    response_model=MediaAssetListResponse,
)
async def get_listing_media(
    category: AdminListingCategory,
    listing_id: UUID,
    service: MediaService = Depends(get_media_service),
):
    _ensure_category_matches_listing(service, category, listing_id)
    return service.list_owner_media(MediaOwnerType.LISTING, listing_id)


@router.patch(
    "/{category}/{listing_id}/media/{media_id}/primary",
    response_model=MediaAssetListResponse,
)
async def set_listing_primary_media(
    category: AdminListingCategory,
    listing_id: UUID,
    media_id: UUID,
    payload: MediaPrimaryUpdateRequest,
    service: MediaService = Depends(get_media_service),
):
    _ensure_category_matches_listing(service, category, listing_id)
    if not payload.is_primary:
        raise AdminAPIError(status_code=status.HTTP_400_BAD_REQUEST, message="is_primary must be true")
    return service.set_primary(MediaOwnerType.LISTING, listing_id, media_id)


@router.patch(
    "/{category}/{listing_id}/media/{media_id}/alt-text",
    response_model=MediaAssetListResponse,
)
async def update_listing_media_alt_text(
    category: AdminListingCategory,
    listing_id: UUID,
    media_id: UUID,
    payload: MediaAltTextUpdateRequest,
    service: MediaService = Depends(get_media_service),
):
    _ensure_category_matches_listing(service, category, listing_id)
    return service.update_alt_text(MediaOwnerType.LISTING, listing_id, media_id, payload.alt_text)


@router.patch(
    "/{category}/{listing_id}/media/reorder",
    response_model=MediaAssetListResponse,
)
async def reorder_listing_media(
    category: AdminListingCategory,
    listing_id: UUID,
    payload: MediaReorderRequest,
    service: MediaService = Depends(get_media_service),
):
    _ensure_category_matches_listing(service, category, listing_id)
    return service.reorder(MediaOwnerType.LISTING, listing_id, payload.items)


@router.delete(
    "/{category}/{listing_id}/media/{media_id}",
    response_model=MediaAssetListResponse,
)
async def delete_listing_media(
    category: AdminListingCategory,
    listing_id: UUID,
    media_id: UUID,
    service: MediaService = Depends(get_media_service),
):
    _ensure_category_matches_listing(service, category, listing_id)
    return service.delete_media(MediaOwnerType.LISTING, listing_id, media_id)
