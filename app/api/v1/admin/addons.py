from uuid import UUID

from fastapi import APIRouter, Depends, Response, status

from app.api.v1.admin.dependencies import get_admin_service, require_admin_user
from app.schemas.admin.addons import AddOnCreate, AddOnResponse
from app.services.admin.dashboard_service import AdminDashboardService

router = APIRouter(prefix="/addons", tags=["admin-addons"], dependencies=[Depends(require_admin_user)])


@router.post("", response_model=AddOnResponse, status_code=status.HTTP_201_CREATED)
async def create_addon(
    payload: AddOnCreate,
    service: AdminDashboardService = Depends(get_admin_service),
):
    return service.create_addon(payload.model_dump())


@router.delete("/{addon_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_addon(
    addon_id: UUID,
    service: AdminDashboardService = Depends(get_admin_service),
):
    service.delete_addon(addon_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)

