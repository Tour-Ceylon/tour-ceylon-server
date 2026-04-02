from fastapi import APIRouter, Depends

from app.api.v1.admin.dependencies import get_admin_service, require_admin_user
from app.schemas.admin.snapshot import AdminSnapshotResponse
from app.services.admin.dashboard_service import AdminDashboardService

router = APIRouter(tags=["admin-reset"], dependencies=[Depends(require_admin_user)])


@router.post("/reset", response_model=AdminSnapshotResponse)
async def reset_dashboard(service: AdminDashboardService = Depends(get_admin_service)):
    return service.reset()

