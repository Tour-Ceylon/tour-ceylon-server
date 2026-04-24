from fastapi import APIRouter, Depends

from app.api.v1.admin.dependencies import get_admin_service
from app.schemas.admin.destinations import AdminDestinationOption
from app.services.admin.dashboard_service import AdminDashboardService

router = APIRouter()


@router.get("/destinations", response_model=list[AdminDestinationOption], response_model_by_alias=True)
async def get_destinations(service: AdminDashboardService = Depends(get_admin_service)):
    return service.get_destinations()
