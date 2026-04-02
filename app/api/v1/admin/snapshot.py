from fastapi import APIRouter, Depends

from app.api.v1.admin.dependencies import get_admin_service
from app.schemas.admin.snapshot import AdminSnapshotResponse
from app.services.admin.dashboard_service import AdminDashboardService

router = APIRouter()


@router.get("/snapshot", response_model=AdminSnapshotResponse, response_model_by_alias=True)
async def get_snapshot(service: AdminDashboardService = Depends(get_admin_service)):
    return service.get_snapshot()
