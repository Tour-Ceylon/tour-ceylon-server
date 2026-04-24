from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, Response, UploadFile, status

from app.api.errors import AdminAPIError
from app.api.v1.admin.dependencies import get_admin_service, get_media_service
from app.schemas.admin.packages import PackageCreate, PackageResponse, PackageUpdate
from app.schemas.media_schema import MediaAssetListResponse, MediaPrimaryUpdateRequest, MediaReorderRequest, MediaUploadResponse
from app.services.admin.dashboard_service import AdminDashboardService
from app.models.enum import MediaOwnerType
from app.services.media_service import MediaService

router = APIRouter(prefix="/packages", tags=["admin-packages"])


@router.post("", response_model=PackageResponse, status_code=status.HTTP_201_CREATED)
async def create_package(
    payload: PackageCreate,
    service: AdminDashboardService = Depends(get_admin_service),
):
    return service.create_package(payload.model_dump())


@router.patch("/{package_id}", response_model=PackageResponse)
async def update_package(
    package_id: UUID,
    payload: PackageUpdate,
    service: AdminDashboardService = Depends(get_admin_service),
):
    return service.update_package(package_id, payload.model_dump(exclude_unset=True))


@router.delete("/{package_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_package(
    package_id: UUID,
    service: AdminDashboardService = Depends(get_admin_service),
):
    service.delete_package(package_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{package_id}/toggle-active", response_model=PackageResponse)
async def toggle_package(
    package_id: UUID,
    service: AdminDashboardService = Depends(get_admin_service),
):
    return service.toggle_package(package_id)


@router.post(
    "/{package_id}/media",
    response_model=MediaUploadResponse,
    status_code=status.HTTP_201_CREATED,
)
async def upload_package_media(
    package_id: UUID,
    files: list[UploadFile] = File(...),
    alt_texts: list[str] | None = Form(None),
    is_primary: bool = Form(False),
    sort_orders: list[int] | None = Form(None),
    service: MediaService = Depends(get_media_service),
):
    return service.upload_package_media(package_id, files, alt_texts, is_primary, sort_orders)


@router.get(
    "/{package_id}/media",
    response_model=MediaAssetListResponse,
)
async def get_package_media(
    package_id: UUID,
    service: MediaService = Depends(get_media_service),
):
    return service.list_owner_media(MediaOwnerType.PACKAGE, package_id)


@router.patch(
    "/{package_id}/media/{media_id}/primary",
    response_model=MediaAssetListResponse,
)
async def set_package_primary_media(
    package_id: UUID,
    media_id: UUID,
    payload: MediaPrimaryUpdateRequest,
    service: MediaService = Depends(get_media_service),
):
    if not payload.is_primary:
        raise AdminAPIError(status_code=status.HTTP_400_BAD_REQUEST, message="is_primary must be true")
    return service.set_primary(MediaOwnerType.PACKAGE, package_id, media_id)


@router.patch(
    "/{package_id}/media/reorder",
    response_model=MediaAssetListResponse,
)
async def reorder_package_media(
    package_id: UUID,
    payload: MediaReorderRequest,
    service: MediaService = Depends(get_media_service),
):
    return service.reorder(MediaOwnerType.PACKAGE, package_id, payload.items)


@router.delete(
    "/{package_id}/media/{media_id}",
    response_model=MediaAssetListResponse,
)
async def delete_package_media(
    package_id: UUID,
    media_id: UUID,
    service: MediaService = Depends(get_media_service),
):
    return service.delete_media(MediaOwnerType.PACKAGE, package_id, media_id)
