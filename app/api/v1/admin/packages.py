from uuid import UUID

from fastapi import APIRouter, Depends, Response, status

from app.api.v1.admin.dependencies import get_admin_service
from app.schemas.admin.packages import PackageCreate, PackageResponse, PackageUpdate
from app.services.admin.dashboard_service import AdminDashboardService

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

