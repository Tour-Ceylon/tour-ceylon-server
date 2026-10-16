from typing import Optional
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.config.database import get_db
from app.models.enum import UserRole
from app.models.user import User
from app.schemas.driver_schema import (
    DriverAvatarSubmissionResponse,
    DriverListResponse,
    DriverProfileChangeReject,
    DriverProfileChangeResponse,
    DriverResponse,
    DriverStatusUpdate,
)
from app.services.driver_avatar_service import DriverAvatarService
from app.services.driver_profile_change_service import DriverProfileChangeService
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
    is_online: Optional[bool] = Query(None, description="Filter by driver online availability"),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    _: User = Depends(require_driver_admin),
    service: DriverService = Depends(get_driver_service),
):
    """List and search driver applications with status and online filtering."""
    return service.list_drivers(status=status, search=search, is_online=is_online, page=page, per_page=per_page)


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


@router.post("/{driver_id}/avatar/approve", response_model=DriverAvatarSubmissionResponse)
def approve_driver_avatar(
    driver_id: UUID,
    admin: User = Depends(require_driver_admin),
    db: Session = Depends(get_db),
):
    """Approve the driver's pending profile photo; it becomes the photo shown across the portals."""
    return DriverAvatarService(db).approve(driver_id, admin)


@router.post("/{driver_id}/avatar/reject", response_model=DriverAvatarSubmissionResponse)
def reject_driver_avatar(
    driver_id: UUID,
    payload: DriverProfileChangeReject,
    admin: User = Depends(require_driver_admin),
    db: Session = Depends(get_db),
):
    """Reject the pending photo with a reason the driver will see."""
    return DriverAvatarService(db).reject(driver_id, admin, payload.reason)


@router.post("/{driver_id}/profile-change/approve", response_model=DriverProfileChangeResponse)
def approve_profile_change(
    driver_id: UUID,
    admin: User = Depends(require_driver_admin),
    db: Session = Depends(get_db),
):
    """Approve the driver's pending profile update: its values are saved to the driver's record."""
    return DriverProfileChangeService(db).approve(driver_id, admin)


@router.post("/{driver_id}/profile-change/reject", response_model=DriverProfileChangeResponse)
def reject_profile_change(
    driver_id: UUID,
    payload: DriverProfileChangeReject,
    admin: User = Depends(require_driver_admin),
    db: Session = Depends(get_db),
):
    """Reject the driver's pending profile update with a reason the driver will see."""
    return DriverProfileChangeService(db).reject(driver_id, admin, payload.reason)


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


@router.get("/by-user/{user_id}", response_model=DriverResponse)
def get_driver_by_user(
    user_id: UUID,
    _: User = Depends(require_driver_admin),
    service: DriverService = Depends(get_driver_service),
):
    """Lookup a driver's full profile by their *user* ID.

    Useful for admin UIs that only have the user-table UUID and need to
    fetch the corresponding driver record (documents, vehicle, status, etc.)
    without a separate search round-trip.
    """
    return service.get_driver_by_user_id(user_id)
