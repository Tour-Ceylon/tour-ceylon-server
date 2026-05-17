from fastapi import APIRouter, Depends, HTTPException, status, Response
from sqlalchemy.orm import Session
from typing import List
from uuid import UUID

from app.config.database import get_db
from app.services.transport_service import TransportService
from app.schemas.transport_schema import (
    VehicleCategoryCreate,
    VehicleCategoryUpdate,
    VehicleCategoryResponse,
    TransportBookingDetailResponse,
    TransportBookingStatusUpdate,
    TransportBookingNotesUpdate
)

router = APIRouter(prefix="/transport", tags=["admin-transport"])

def get_transport_service(db: Session = Depends(get_db)) -> TransportService:
    return TransportService(db)

@router.post("/categories", response_model=VehicleCategoryResponse, status_code=status.HTTP_201_CREATED)
async def create_vehicle_category(
    payload: VehicleCategoryCreate,
    service: TransportService = Depends(get_transport_service)
):
    """
    Create a new vehicle category.
    """
    try:
        return service.create_category(payload.model_dump())
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create vehicle category: {str(e)}"
        )

@router.get("/categories", response_model=List[VehicleCategoryResponse])
async def list_vehicle_categories(
    service: TransportService = Depends(get_transport_service)
):
    """
    List all vehicle categories.
    """
    return service.list_all_categories()

@router.patch("/categories/{category_id}", response_model=VehicleCategoryResponse)
async def update_vehicle_category(
    category_id: UUID,
    payload: VehicleCategoryUpdate,
    service: TransportService = Depends(get_transport_service)
):
    """
    Update a vehicle category.
    """
    updated = service.update_category(category_id, payload.model_dump(exclude_unset=True))
    if not updated:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Vehicle category not found"
        )
    return updated

@router.delete("/categories/{category_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_vehicle_category(
    category_id: UUID,
    service: TransportService = Depends(get_transport_service)
):
    """
    Deactivate (soft delete) a vehicle category.
    """
    success = service.delete_category(category_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Vehicle category not found"
        )
    return Response(status_code=status.HTTP_204_NO_CONTENT)

# --- Booking Management ---

@router.get("/bookings", response_model=List[TransportBookingDetailResponse])
async def list_transport_bookings(
    service: TransportService = Depends(get_transport_service)
):
    """
    List all transport bookings.
    """
    return service.list_all_bookings()

@router.get("/bookings/{booking_id}", response_model=TransportBookingDetailResponse)
async def get_transport_booking(
    booking_id: UUID,
    service: TransportService = Depends(get_transport_service)
):
    """
    Get detailed information about a specific transport booking.
    """
    booking = service.get_booking_by_id(booking_id)
    if not booking:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Booking not found"
        )
    return booking

@router.patch("/bookings/{booking_id}/status", response_model=TransportBookingDetailResponse)
async def update_booking_status(
    booking_id: UUID,
    payload: TransportBookingStatusUpdate,
    service: TransportService = Depends(get_transport_service)
):
    """
    Update the status of a transport booking.
    """
    updated = service.update_booking_status(booking_id, payload.booking_status)
    if not updated:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Booking not found"
        )
    return updated

@router.patch("/bookings/{booking_id}/notes", response_model=TransportBookingDetailResponse)
async def update_booking_notes(
    booking_id: UUID,
    payload: TransportBookingNotesUpdate,
    service: TransportService = Depends(get_transport_service)
):
    """
    Update internal notes for a transport booking.
    """
    updated = service.update_booking_notes(booking_id, payload.internal_notes)
    if not updated:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Booking not found"
        )
    return updated
