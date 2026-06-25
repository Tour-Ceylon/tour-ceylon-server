from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.config.database import get_db
from app.schemas.stay_schema import (
    StayAvailabilitySearchRequest,
    StayAvailabilitySearchResponse,
    StayBookingCreate,
    StayBookingResponse,
)
from app.services.stay_inventory_service import StayInventoryService

router = APIRouter()


def get_stay_inventory_service(db: Session = Depends(get_db)) -> StayInventoryService:
    return StayInventoryService(db)


@router.post("/availability", response_model=StayAvailabilitySearchResponse, response_model_by_alias=True)
async def search_stay_availability(
    payload: StayAvailabilitySearchRequest,
    service: StayInventoryService = Depends(get_stay_inventory_service),
):
    try:
        return service.search_availability(payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.post("/bookings", response_model=StayBookingResponse, response_model_by_alias=True, status_code=status.HTTP_201_CREATED)
async def create_stay_booking(
    payload: StayBookingCreate,
    service: StayInventoryService = Depends(get_stay_inventory_service),
):
    try:
        booking = service.create_booking(payload)
        return StayBookingResponse.model_validate(booking)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
