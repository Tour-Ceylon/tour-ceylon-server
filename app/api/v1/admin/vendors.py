from uuid import UUID
from fastapi import APIRouter, Depends, Query, status

from app.api.v1.admin.dependencies import get_admin_service
from app.schemas.admin.vendor import VendorCreate, VendorResponse, VendorUpdate, VendorListResponse
from app.services.admin.dashboard_service import AdminDashboardService

router = APIRouter(prefix="/vendors", tags=["admin-vendors"])


@router.post("", response_model=VendorResponse, status_code=status.HTTP_201_CREATED)
async def create_vendor(
    payload: VendorCreate,
    service: AdminDashboardService = Depends(get_admin_service),
):
    return service.create_vendor(payload.model_dump())


@router.get("", response_model=VendorListResponse)
async def list_vendors(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    search: str | None = Query(None),
    service: AdminDashboardService = Depends(get_admin_service),
):
    return service.get_vendors(skip=skip, limit=limit, search=search)


@router.get("/{vendor_id}", response_model=VendorResponse)
async def get_vendor(
    vendor_id: UUID,
    service: AdminDashboardService = Depends(get_admin_service),
):
    return service.get_vendor(vendor_id)


@router.patch("/{vendor_id}", response_model=VendorResponse)
async def update_vendor(
    vendor_id: UUID,
    payload: VendorUpdate,
    service: AdminDashboardService = Depends(get_admin_service),
):
    return service.update_vendor(vendor_id, payload.model_dump(exclude_unset=True))


@router.delete("/{vendor_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_vendor(
    vendor_id: UUID,
    service: AdminDashboardService = Depends(get_admin_service),
):
    service.delete_vendor(vendor_id)
    return None
