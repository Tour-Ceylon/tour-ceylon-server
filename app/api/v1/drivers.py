from typing import List, Optional
from fastapi import APIRouter, Depends, File, UploadFile, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.config.database import get_db
from app.models.user import User
from app.schemas.driver_schema import (
    DriverAvatarSubmissionResponse,
    DriverProfileChangeResponse,
    DriverProfileChangeSubmit,
    DriverProfileUpdate,
    DriverResponse,
    LuggageSizeTypeResponse,
    VehicleModelPresetResponse,
)
from app.services.driver_avatar_service import MAX_BYTES, DriverAvatarService
from app.services.driver_profile_change_service import DriverProfileChangeService
from app.services.driver_service import DriverService

router = APIRouter(tags=["drivers"])


def get_driver_service(db: Session = Depends(get_db)) -> DriverService:
    return DriverService(db)


@router.get("/luggage-size-types", response_model=List[LuggageSizeTypeResponse])
def get_luggage_size_types(service: DriverService = Depends(get_driver_service)):
    """Public endpoint to get available luggage size tiers."""
    return service.get_luggage_size_types()


@router.get("/vehicle-model-presets", response_model=List[VehicleModelPresetResponse])
def get_vehicle_model_presets(service: DriverService = Depends(get_driver_service)):
    """Public endpoint to get available vehicle model presets."""
    return service.get_vehicle_model_presets()


@router.get("/drivers/me", response_model=DriverResponse)
def get_my_driver_profile(
    current_user: User = Depends(get_current_user),
    service: DriverService = Depends(get_driver_service),
):
    """Get profile of the currently logged-in driver."""
    return service.get_driver_by_user_id(current_user.id)


@router.post("/drivers/me/avatar", response_model=DriverAvatarSubmissionResponse, status_code=status.HTTP_201_CREATED)
def upload_my_avatar(
    photo: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Upload a profile photo (JPEG, PNG or WebP, up to 5 MB). It is shown only after an admin approves it."""
    data = photo.file.read(MAX_BYTES + 1)
    return DriverAvatarService(db).submit(current_user.id, data, photo.content_type)


@router.delete("/drivers/me/avatar", response_model=DriverAvatarSubmissionResponse)
def withdraw_my_avatar(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Withdraw the photo that is still waiting for review."""
    return DriverAvatarService(db).withdraw(current_user.id)


@router.get("/drivers/me/profile-change", response_model=Optional[DriverProfileChangeResponse])
def get_my_profile_change(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """The newest profile update this driver sent for review, or null."""
    service = DriverProfileChangeService(db)
    driver = service._driver_for_user(current_user.id)
    latest = service.latest_for_driver(driver.id)
    return DriverProfileChangeResponse.model_validate(latest) if latest else None


@router.post("/drivers/me/profile-change", response_model=DriverProfileChangeResponse, status_code=status.HTTP_201_CREATED)
def submit_my_profile_change(
    payload: DriverProfileChangeSubmit,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Send profile details (languages, experience, base location, payout details) for admin review.
    Nothing is saved to the driver's profile until an admin approves it."""
    return DriverProfileChangeService(db).submit(current_user.id, payload)


@router.delete("/drivers/me/profile-change", response_model=DriverProfileChangeResponse)
def withdraw_my_profile_change(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Withdraw the update that is still waiting for review."""
    return DriverProfileChangeService(db).withdraw(current_user.id)


@router.patch("/drivers/me", response_model=DriverResponse)
def update_my_driver_profile(
    payload: DriverProfileUpdate,
    current_user: User = Depends(get_current_user),
    service: DriverService = Depends(get_driver_service),
):
    """Send Phase 2 profile fields for admin review. Kept for older callers; the values are NOT saved
    until an admin approves them (see POST /drivers/me/profile-change)."""
    return service.update_driver_profile(current_user.id, payload)
