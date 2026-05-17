from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List

from app.config.database import get_db
from app.services.transport_service import TransportService
from app.schemas.transport_schema import (
    TransportEstimateRequest,
    TransportEstimateResponse,
    TransportBookingCreate,
    TransportBookingResponse,
    VehicleCategoryResponse,
    TransportBookingDetailResponse
)

router = APIRouter()
def get_transport_service(db: Session = Depends(get_db)) -> TransportService:
    return TransportService(db)

@router.get("/categories", response_model=List[VehicleCategoryResponse])
async def list_active_vehicle_categories(
    service: TransportService = Depends(get_transport_service)
):
    """
    Get all active vehicle categories for transport.
    """
    return service.list_active_categories()

@router.post("/quote", response_model=TransportEstimateResponse)
async def get_transport_quote(
    request: TransportEstimateRequest,
    transport_service: TransportService = Depends(get_transport_service)
):
    """
    Get transport distance and price estimates (quote) for different vehicle categories.
    """
    try:
        return await transport_service.get_estimates(request)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while calculating quote"
        )

@router.post("/bookings", response_model=TransportBookingResponse, status_code=status.HTTP_201_CREATED)
async def create_transport_booking(
    booking_data: TransportBookingCreate,
    transport_service: TransportService = Depends(get_transport_service)
):
    """
    Create a new transport booking.
    """
    try:
        booking = transport_service.create_booking(booking_data)
        return TransportBookingResponse(
            id=booking.id,
            booking_reference=booking.booking_reference,
            booking_status=booking.booking_status,
            payment_status=booking.payment_status
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create transport booking"
        )

@router.get("/bookings/{booking_reference}", response_model=TransportBookingDetailResponse)
async def get_booking_by_reference(
    booking_reference: str,
    service: TransportService = Depends(get_transport_service)
):
    """
    Retrieve booking details using the booking reference.
    """
    booking = service.get_booking_by_reference(booking_reference)
    if not booking:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Booking not found"
        )
    return booking
