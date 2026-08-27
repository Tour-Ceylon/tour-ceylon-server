from typing import List
from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.config.database import get_db
from app.models.user import User
from app.schemas.driver_schema import (
    DriverProfileUpdate,
    DriverResponse,
    LuggageSizeTypeResponse,
    VehicleModelPresetResponse,
)
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


@router.patch("/drivers/me", response_model=DriverResponse)
def update_my_driver_profile(
    payload: DriverProfileUpdate,
    current_user: User = Depends(get_current_user),
    service: DriverService = Depends(get_driver_service),
):
    """Update Phase 2 profile fields of the currently logged-in driver."""
    return service.update_driver_profile(current_user.id, payload)
