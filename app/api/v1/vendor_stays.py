import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.config.database import get_db
from app.integrations.cloudinary import CloudinaryIntegrationError
from app.models.enum import UserRole
from app.models.user import User
from app.repositories.stay_repo import StayRepository
from app.schemas.stay_schema import StayPropertyCreate, StayPropertyListResponse, StayPropertyResponse

router = APIRouter()
logger = logging.getLogger("app.vendor_stays")


def get_stay_repository(db: Session = Depends(get_db)) -> StayRepository:
    return StayRepository(db)


def require_stay_vendor(current_user: User = Depends(get_current_user)) -> User:
    role = current_user.role.value if hasattr(current_user.role, "value") else current_user.role
    categories = current_user.approved_categories
    if not categories:
        # Fallback to all standard categories if empty/unset
        categories = ["Stay", "Tour", "Safari", "Experience", "Transfer"]
    if role in {UserRole.ADMIN.value, UserRole.SUPPORT.value}:
        return current_user
    if role != UserRole.VENDOR.value:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only vendors or admins can manage stay applications")
    if current_user.vendor_status != "approved":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Vendor is not approved")
    if "Stay" not in categories:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Vendor is not approved for Stay listings")
    return current_user


def is_admin_user(user: User) -> bool:
    role = user.role.value if hasattr(user.role, "value") else user.role
    return role in {UserRole.ADMIN.value, UserRole.SUPPORT.value}


@router.post("/", response_model=StayPropertyResponse, response_model_by_alias=True, status_code=status.HTTP_201_CREATED)
async def create_stay_property(
    payload: StayPropertyCreate,
    current_user: User = Depends(require_stay_vendor),
    repo: StayRepository = Depends(get_stay_repository),
):
    try:
        return repo.create_for_vendor(current_user.id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except CloudinaryIntegrationError as exc:
        repo.db.rollback()
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Failed to upload stay images") from exc
    except SQLAlchemyError as exc:
        repo.db.rollback()
        logger.exception("Failed to save stay application")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to save stay application") from exc


@router.get("/", response_model=StayPropertyListResponse, response_model_by_alias=True)
async def list_stay_properties(
    current_user: User = Depends(require_stay_vendor),
    repo: StayRepository = Depends(get_stay_repository),
):
    properties = repo.list_all() if is_admin_user(current_user) else repo.list_for_vendor(current_user.id)
    return StayPropertyListResponse(properties=properties, total=len(properties))


@router.get("/{property_id}", response_model=StayPropertyResponse, response_model_by_alias=True)
async def get_stay_property(
    property_id: UUID,
    current_user: User = Depends(require_stay_vendor),
    repo: StayRepository = Depends(get_stay_repository),
):
    property_record = repo.get_by_id(property_id) if is_admin_user(current_user) else repo.get_for_vendor(current_user.id, property_id)
    if property_record is None:
        property_record = repo.create_from_listing(current_user.id, property_id)
    if property_record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Stay property not found")
    return property_record


@router.put("/{property_id}", response_model=StayPropertyResponse, response_model_by_alias=True)
async def update_stay_property(
    property_id: UUID,
    payload: StayPropertyCreate,
    current_user: User = Depends(require_stay_vendor),
    repo: StayRepository = Depends(get_stay_repository),
):
    try:
        property_record = repo.update_for_vendor(current_user.id, property_id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except CloudinaryIntegrationError as exc:
        repo.db.rollback()
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Failed to upload stay images") from exc
    except SQLAlchemyError as exc:
        repo.db.rollback()
        logger.exception("Failed to update stay listing property_id=%s", property_id)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to update stay listing") from exc

    if property_record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Stay property not found")
    return property_record
