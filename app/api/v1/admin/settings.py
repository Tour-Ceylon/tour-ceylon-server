from fastapi import APIRouter, Depends

from app.api.deps import require_role
from app.api.v1.admin.dependencies import get_admin_service
from app.models.enum import UserRole
from app.schemas.admin.settings import AdminSettingsResponse, AdminSettingsUpdate
from app.services.admin.dashboard_service import AdminDashboardService

router = APIRouter(
    tags=["admin-settings"],
    dependencies=[Depends(require_role([UserRole.ADMIN]))],
)


@router.get("/settings", response_model=AdminSettingsResponse)
async def get_settings(service: AdminDashboardService = Depends(get_admin_service)):
    return service.get_settings()


@router.patch("/settings", response_model=AdminSettingsResponse)
async def update_settings(
    payload: AdminSettingsUpdate,
    service: AdminDashboardService = Depends(get_admin_service),
):
    return service.update_settings(payload.model_dump())

