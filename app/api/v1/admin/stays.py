from datetime import date
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.config.database import get_db
from app.models.enum import UserRole
from app.models.user import User
from app.schemas.stay_schema import (
    StayBookingCreate,
    StayBookingListResponse,
    StayBookingResponse,
    StayCalendarResponse,
    StayInventoryResponse,
    StayRoomBlockCreate,
    StayRoomBlockListResponse,
    StayRoomBlockResponse,
    StayRoomTypeCreate,
    StayRoomTypeResponse,
    StayRoomTypeUpdate,
    StayRoomUnitCreate,
    StayRoomUnitResponse,
    StayRoomUnitUpdate,
)
from app.models.stay import StayProperty
from app.services.stay_inventory_service import StayInventoryService

router = APIRouter(prefix="/stays", tags=["admin-stays"])


def get_stay_inventory_service(db: Session = Depends(get_db)) -> StayInventoryService:
    return StayInventoryService(db)


def require_stay_admin(current_user: User = Depends(get_current_user)) -> User:
    role = current_user.role.value if hasattr(current_user.role, "value") else current_user.role
    if role not in {UserRole.ADMIN.value, UserRole.SUPPORT.value}:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")
    return current_user


@router.get("/{property_id}/inventory", response_model=StayInventoryResponse, response_model_by_alias=True)
async def get_inventory(
    property_id: UUID,
    _: User = Depends(require_stay_admin),
    service: StayInventoryService = Depends(get_stay_inventory_service),
):
    try:
        return service.list_inventory(property_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.post("/{property_id}/room-types", response_model=StayRoomTypeResponse, response_model_by_alias=True, status_code=status.HTTP_201_CREATED)
async def create_room_type(
    property_id: UUID,
    payload: StayRoomTypeCreate,
    _: User = Depends(require_stay_admin),
    service: StayInventoryService = Depends(get_stay_inventory_service),
):
    try:
        return service.create_room_type(property_id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.patch("/{property_id}/room-types/{room_type_id}", response_model=StayRoomTypeResponse, response_model_by_alias=True)
async def update_room_type(
    property_id: UUID,
    room_type_id: UUID,
    payload: StayRoomTypeUpdate,
    _: User = Depends(require_stay_admin),
    service: StayInventoryService = Depends(get_stay_inventory_service),
):
    try:
        return service.update_room_type(property_id, room_type_id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.delete("/{property_id}/room-types/{room_type_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_room_type(
    property_id: UUID,
    room_type_id: UUID,
    _: User = Depends(require_stay_admin),
    service: StayInventoryService = Depends(get_stay_inventory_service),
):
    try:
        service.delete_room_type(property_id, room_type_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.post("/{property_id}/room-units", response_model=StayRoomUnitResponse, response_model_by_alias=True, status_code=status.HTTP_201_CREATED)
async def create_room_unit(
    property_id: UUID,
    payload: StayRoomUnitCreate,
    _: User = Depends(require_stay_admin),
    service: StayInventoryService = Depends(get_stay_inventory_service),
):
    try:
        return service.create_room_unit(property_id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.patch("/{property_id}/room-units/{room_unit_id}", response_model=StayRoomUnitResponse, response_model_by_alias=True)
async def update_room_unit(
    property_id: UUID,
    room_unit_id: UUID,
    payload: StayRoomUnitUpdate,
    _: User = Depends(require_stay_admin),
    service: StayInventoryService = Depends(get_stay_inventory_service),
):
    try:
        return service.update_room_unit(property_id, room_unit_id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.delete("/{property_id}/room-units/{room_unit_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_room_unit(
    property_id: UUID,
    room_unit_id: UUID,
    _: User = Depends(require_stay_admin),
    service: StayInventoryService = Depends(get_stay_inventory_service),
):
    try:
        service.delete_room_unit(property_id, room_unit_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


def _require_admin_property(service: StayInventoryService, property_id: UUID) -> StayProperty:
    prop = service.get_property(property_id)
    if prop is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Stay property not found")
    return prop


@router.get("/{property_id}/calendar", response_model=StayCalendarResponse, response_model_by_alias=True)
async def get_calendar(
    property_id: UUID,
    start_date: date = Query(..., alias="startDate"),
    end_date: date = Query(..., alias="endDate"),
    room_type_id: UUID | None = Query(None, alias="roomTypeId"),
    _: User = Depends(require_stay_admin),
    service: StayInventoryService = Depends(get_stay_inventory_service),
):
    prop = _require_admin_property(service, property_id)
    try:
        return service.get_calendar(prop.id, start_date, end_date, room_type_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.get("/{property_id}/blocks", response_model=StayRoomBlockListResponse, response_model_by_alias=True)
async def list_blocks(
    property_id: UUID,
    room_type_id: UUID | None = Query(None, alias="roomTypeId"),
    start_date: date | None = Query(None, alias="startDate"),
    end_date: date | None = Query(None, alias="endDate"),
    _: User = Depends(require_stay_admin),
    service: StayInventoryService = Depends(get_stay_inventory_service),
):
    prop = _require_admin_property(service, property_id)
    try:
        return service.list_property_blocks(
            prop.id,
            room_type_id=room_type_id,
            start_date=start_date,
            end_date=end_date,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.post("/{property_id}/blocks", response_model=StayRoomBlockResponse, response_model_by_alias=True, status_code=status.HTTP_201_CREATED)
async def create_block(
    property_id: UUID,
    payload: StayRoomBlockCreate,
    current_user: User = Depends(require_stay_admin),
    service: StayInventoryService = Depends(get_stay_inventory_service),
):
    prop = _require_admin_property(service, property_id)
    try:
        return service.create_room_block(prop.id, current_user, payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.delete("/{property_id}/blocks/{block_id}", response_model=StayRoomBlockResponse, response_model_by_alias=True)
async def release_block(
    property_id: UUID,
    block_id: UUID,
    _: User = Depends(require_stay_admin),
    service: StayInventoryService = Depends(get_stay_inventory_service),
):
    prop = _require_admin_property(service, property_id)
    try:
        return service.release_room_block(prop.id, block_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.get("/{property_id}/bookings", response_model=StayBookingListResponse, response_model_by_alias=True)
async def list_bookings(
    property_id: UUID,
    _: User = Depends(require_stay_admin),
    service: StayInventoryService = Depends(get_stay_inventory_service),
):
    prop = _require_admin_property(service, property_id)
    try:
        return service.list_property_bookings(prop.id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.post("/{property_id}/bookings", response_model=StayBookingResponse, response_model_by_alias=True, status_code=status.HTTP_201_CREATED)
async def create_booking(
    property_id: UUID,
    payload: StayBookingCreate,
    _: User = Depends(require_stay_admin),
    service: StayInventoryService = Depends(get_stay_inventory_service),
):
    prop = _require_admin_property(service, property_id)
    if payload.property_id != property_id and payload.property_id != prop.id:
        payload.property_id = prop.id
    try:
        booking = service.create_booking(payload, confirm=True)
        return StayBookingResponse.model_validate(booking)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
