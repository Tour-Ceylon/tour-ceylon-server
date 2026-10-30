from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import require_role
from app.api.v1.admin.dependencies import get_admin_service
from app.config.settings import settings
from app.models.enum import UserRole
from app.models.user import User
from app.schemas.admin.snapshot import AdminSnapshotResponse
from app.services.admin.dashboard_service import AdminDashboardService

router = APIRouter(tags=["admin-reset"])


@router.post("/reset", response_model=AdminSnapshotResponse)
async def reset_dashboard(
    service: AdminDashboardService = Depends(get_admin_service),
    current_user: User = Depends(require_role([UserRole.ADMIN])),
):
    if settings.ENV.lower() == "production":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Database reset is permanently disabled in production environments",
        )
    return service.reset()

