import logging
from datetime import date
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.config.database import get_db
from app.integrations.cloudinary import CloudinaryIntegrationError
from app.models.enum import UserRole
from app.models.user import User
from app.repositories.stay_repo import StayRepository
from app.schemas.stay_schema import (
    StayBookingListResponse,
    StayCalendarResponse,
    StayInventoryResponse,
    StayRoomBlockListResponse,
    StayPropertyCreate,
    StayPropertyListResponse,
    StayPropertyResponse,
    StayRoomBlockCreate,
    StayRoomBlockResponse,
    StayRoomTypeCreate,
    StayRoomTypeResponse,
    StayRoomTypeUpdate,
    StayRoomUnitCreate,
    StayRoomUnitResponse,
    StayRoomUnitUpdate,
)
from app.services.stay_inventory_service import StayInventoryService

router = APIRouter()
logger = logging.getLogger("app.vendor_stays")


def get_stay_repository(db: Session = Depends(get_db)) -> StayRepository:
    return StayRepository(db)


def get_stay_inventory_service(db: Session = Depends(get_db)) -> StayInventoryService:
    return StayInventoryService(db)


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


def ensure_property_access(current_user: User, repo: StayRepository, property_id: UUID):
    property_record = repo.get_by_id(property_id) if is_admin_user(current_user) else repo.get_for_vendor(current_user.id, property_id)
    if property_record is None:
        if is_admin_user(current_user):
            from app.models.listing import Listing
            listing = repo.db.query(Listing).filter(Listing.id == property_id).first()
            if listing:
                property_record = repo.create_from_listing(listing.vendor_id, property_id)
        else:
            property_record = repo.create_from_listing(current_user.id, property_id)
            
    if property_record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Stay property not found")
    return property_record


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
    return ensure_property_access(current_user, repo, property_id)


@router.put("/{property_id}", response_model=StayPropertyResponse, response_model_by_alias=True)
async def update_stay_property(
    property_id: UUID,
    payload: StayPropertyCreate,
    current_user: User = Depends(require_stay_vendor),
    repo: StayRepository = Depends(get_stay_repository),
):
    try:
        property_record = repo.update_property(
            property_id, payload, user_id=current_user.id, is_admin=is_admin_user(current_user)
        )
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


@router.get("/{property_id}/inventory", response_model=StayInventoryResponse, response_model_by_alias=True)
async def get_stay_inventory(
    property_id: UUID,
    current_user: User = Depends(require_stay_vendor),
    repo: StayRepository = Depends(get_stay_repository),
    service: StayInventoryService = Depends(get_stay_inventory_service),
):
    ensure_property_access(current_user, repo, property_id)
    try:
        return service.list_inventory(property_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.post("/{property_id}/room-types", response_model=StayRoomTypeResponse, response_model_by_alias=True, status_code=status.HTTP_201_CREATED)
async def create_room_type(
    property_id: UUID,
    payload: StayRoomTypeCreate,
    current_user: User = Depends(require_stay_vendor),
    repo: StayRepository = Depends(get_stay_repository),
    service: StayInventoryService = Depends(get_stay_inventory_service),
):
    ensure_property_access(current_user, repo, property_id)
    try:
        return service.create_room_type(property_id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.patch("/{property_id}/room-types/{room_type_id}", response_model=StayRoomTypeResponse, response_model_by_alias=True)
async def update_room_type(
    property_id: UUID,
    room_type_id: UUID,
    payload: StayRoomTypeUpdate,
    current_user: User = Depends(require_stay_vendor),
    repo: StayRepository = Depends(get_stay_repository),
    service: StayInventoryService = Depends(get_stay_inventory_service),
):
    ensure_property_access(current_user, repo, property_id)
    try:
        return service.update_room_type(property_id, room_type_id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.delete("/{property_id}/room-types/{room_type_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_room_type(
    property_id: UUID,
    room_type_id: UUID,
    current_user: User = Depends(require_stay_vendor),
    repo: StayRepository = Depends(get_stay_repository),
    service: StayInventoryService = Depends(get_stay_inventory_service),
):
    ensure_property_access(current_user, repo, property_id)
    try:
        service.delete_room_type(property_id, room_type_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.post("/{property_id}/room-units", response_model=StayRoomUnitResponse, response_model_by_alias=True, status_code=status.HTTP_201_CREATED)
async def create_room_unit(
    property_id: UUID,
    payload: StayRoomUnitCreate,
    current_user: User = Depends(require_stay_vendor),
    repo: StayRepository = Depends(get_stay_repository),
    service: StayInventoryService = Depends(get_stay_inventory_service),
):
    ensure_property_access(current_user, repo, property_id)
    try:
        return service.create_room_unit(property_id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.patch("/{property_id}/room-units/{room_unit_id}", response_model=StayRoomUnitResponse, response_model_by_alias=True)
async def update_room_unit(
    property_id: UUID,
    room_unit_id: UUID,
    payload: StayRoomUnitUpdate,
    current_user: User = Depends(require_stay_vendor),
    repo: StayRepository = Depends(get_stay_repository),
    service: StayInventoryService = Depends(get_stay_inventory_service),
):
    ensure_property_access(current_user, repo, property_id)
    try:
        return service.update_room_unit(property_id, room_unit_id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.delete("/{property_id}/room-units/{room_unit_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_room_unit(
    property_id: UUID,
    room_unit_id: UUID,
    current_user: User = Depends(require_stay_vendor),
    repo: StayRepository = Depends(get_stay_repository),
    service: StayInventoryService = Depends(get_stay_inventory_service),
):
    ensure_property_access(current_user, repo, property_id)
    try:
        service.delete_room_unit(property_id, room_unit_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.get("/{property_id}/calendar", response_model=StayCalendarResponse, response_model_by_alias=True)
async def get_property_calendar(
    property_id: UUID,
    start_date: date = Query(..., alias="startDate"),
    end_date: date = Query(..., alias="endDate"),
    room_type_id: UUID | None = Query(None, alias="roomTypeId"),
    current_user: User = Depends(require_stay_vendor),
    repo: StayRepository = Depends(get_stay_repository),
    service: StayInventoryService = Depends(get_stay_inventory_service),
):
    property_record = ensure_property_access(current_user, repo, property_id)
    try:
        return service.get_calendar(property_record.id, start_date, end_date, room_type_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.get("/{property_id}/blocks", response_model=StayRoomBlockListResponse, response_model_by_alias=True)
async def list_property_blocks(
    property_id: UUID,
    room_type_id: UUID | None = Query(None, alias="roomTypeId"),
    start_date: date | None = Query(None, alias="startDate"),
    end_date: date | None = Query(None, alias="endDate"),
    current_user: User = Depends(require_stay_vendor),
    repo: StayRepository = Depends(get_stay_repository),
    service: StayInventoryService = Depends(get_stay_inventory_service),
):
    property_record = ensure_property_access(current_user, repo, property_id)
    try:
        return service.list_property_blocks(
            property_record.id,
            room_type_id=room_type_id,
            start_date=start_date,
            end_date=end_date,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.post("/{property_id}/blocks", response_model=StayRoomBlockResponse, response_model_by_alias=True, status_code=status.HTTP_201_CREATED)
async def create_room_block(
    property_id: UUID,
    payload: StayRoomBlockCreate,
    current_user: User = Depends(require_stay_vendor),
    repo: StayRepository = Depends(get_stay_repository),
    service: StayInventoryService = Depends(get_stay_inventory_service),
):
    property_record = ensure_property_access(current_user, repo, property_id)
    try:
        return service.create_room_block(property_record.id, current_user, payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.delete("/{property_id}/blocks/{block_id}", response_model=StayRoomBlockResponse, response_model_by_alias=True)
async def release_room_block(
    property_id: UUID,
    block_id: UUID,
    current_user: User = Depends(require_stay_vendor),
    repo: StayRepository = Depends(get_stay_repository),
    service: StayInventoryService = Depends(get_stay_inventory_service),
):
    property_record = ensure_property_access(current_user, repo, property_id)
    try:
        return service.release_room_block(property_record.id, block_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.get("/{property_id}/bookings", response_model=StayBookingListResponse, response_model_by_alias=True)
async def list_property_bookings(
    property_id: UUID,
    current_user: User = Depends(require_stay_vendor),
    repo: StayRepository = Depends(get_stay_repository),
    service: StayInventoryService = Depends(get_stay_inventory_service),
):
    property_record = ensure_property_access(current_user, repo, property_id)
    try:
        return service.list_property_bookings(property_record.id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
