from typing import Optional
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.config.database import get_db
from app.models.enum import UserRole
from app.models.user import User
from app.schemas.driver_schema import DriverListResponse, DriverResponse, DriverStatusUpdate
from app.services.driver_service import DriverService

router = APIRouter(prefix="/drivers", tags=["admin-drivers"])


def get_driver_service(db: Session = Depends(get_db)) -> DriverService:
    return DriverService(db)


def require_driver_admin(current_user: User = Depends(get_current_user)) -> User:
    role = current_user.role.value if hasattr(current_user.role, "value") else str(current_user.role)
    if role not in {UserRole.ADMIN.value, "ADMIN", "admin"}:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")
    return current_user


@router.get("", response_model=DriverListResponse)
def list_drivers(
    status: Optional[str] = Query(None, description="Filter by status: pending_review, approved, rejected, suspended"),
    search: Optional[str] = Query(None, description="Search by name, email, NIC, or plate number"),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    _: User = Depends(require_driver_admin),
    service: DriverService = Depends(get_driver_service),
):
    """List and search driver applications with status filtering."""
    return service.list_drivers(status=status, search=search, page=page, per_page=per_page)


@router.get("/{driver_id}", response_model=DriverResponse)
def get_driver(
    driver_id: UUID,
    _: User = Depends(require_driver_admin),
    service: DriverService = Depends(get_driver_service),
):
    """Get detailed driver profile including documents and luggage capacities."""
    return service.get_driver_by_id(driver_id)


@router.patch("/{driver_id}/status", response_model=DriverResponse)
def update_driver_status(
    driver_id: UUID,
    payload: DriverStatusUpdate,
    _: User = Depends(require_driver_admin),
    service: DriverService = Depends(get_driver_service),
):
    """Update driver verification status (pending_review, approved, rejected, suspended)."""
    return service.update_driver_status(driver_id, payload.status.value)


@router.post("/{driver_id}/approve", response_model=DriverResponse)
def approve_driver(
    driver_id: UUID,
    _: User = Depends(require_driver_admin),
    service: DriverService = Depends(get_driver_service),
):
    """Approve a driver application."""
    return service.update_driver_status(driver_id, "approved")


@router.post("/{driver_id}/reject", response_model=DriverResponse)
def reject_driver(
    driver_id: UUID,
    _: User = Depends(require_driver_admin),
    service: DriverService = Depends(get_driver_service),
):
    """Reject a driver application."""
    return service.update_driver_status(driver_id, "rejected")


@router.post("/{driver_id}/suspend", response_model=DriverResponse)
def suspend_driver(
    driver_id: UUID,
    _: User = Depends(require_driver_admin),
    service: DriverService = Depends(get_driver_service),
):
    """Suspend an approved driver."""
    return service.update_driver_status(driver_id, "suspended")
