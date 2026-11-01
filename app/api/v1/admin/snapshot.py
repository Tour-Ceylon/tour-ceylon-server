from fastapi import APIRouter, Depends

from app.api.deps import require_role
from app.api.v1.admin.dependencies import get_admin_service
from app.models.enum import UserRole
from app.models.user import User
from app.schemas.admin.snapshot import AdminSnapshotResponse
from app.services.admin.dashboard_service import AdminDashboardService

router = APIRouter()


@router.get("/snapshot", response_model=AdminSnapshotResponse, response_model_by_alias=True)
def get_snapshot(
    service: AdminDashboardService = Depends(get_admin_service),
    current_user: User = Depends(require_role([UserRole.ADMIN, UserRole.VENDOR])),
):
    return service.get_snapshot(current_user)
