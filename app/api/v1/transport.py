from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from sqlalchemy.orm import Session
from typing import List

from app.config.database import get_db
from app.core.logging import logger
from app.services.transport_service import TransportService
from app.integrations.email_provider import email_provider
from app.schemas.transport_schema import (
    TransportEstimateRequest,
    TransportEstimateResponse,
    TransportBookingCreate,
    TransportBookingResponse,
    VehicleCategoryResponse,
    TransportLocationSuggestion,
    TransportBookingDetailResponse
)

router = APIRouter()
def get_transport_service(db: Session = Depends(get_db)) -> TransportService:
    return TransportService(db)


def send_transport_notification_email(booking: TransportBookingDetailResponse):
    """Background task to send transport booking notification email to business team"""
    try:
        success = email_provider.send_transport_booking_notification(booking)
        if success:
            logger.info(f"Business notification email sent for transport booking {booking.booking_reference}")
        else:
            logger.error(f"Failed to send business notification email for transport booking {booking.booking_reference}")
    except Exception as e:
        logger.error(f"Error sending transport business notification email: {str(e)}")


def send_transport_customer_confirmation_email(booking: TransportBookingDetailResponse):
    """Background task to send transport booking confirmation email to customer"""
    try:
        success = email_provider.send_transport_booking_customer_confirmation(booking)
        if success:
            logger.info(f"Customer confirmation email sent for transport booking {booking.booking_reference} to {booking.customer_email}")
        else:
            logger.error(f"Failed to send customer confirmation email for transport booking {booking.booking_reference}")
    except Exception as e:
        logger.error(f"Error sending transport customer confirmation email: {str(e)}")


@router.get("/categories", response_model=List[VehicleCategoryResponse])
async def list_active_vehicle_categories(
    service: TransportService = Depends(get_transport_service)
):
    """
    Get all active vehicle categories for transport.
    """
    return service.list_active_categories()

@router.get("/locations/search", response_model=List[TransportLocationSuggestion])
async def search_transport_locations(
    q: str,
    service: TransportService = Depends(get_transport_service)
):
    """
    Search live Sri Lanka pickup/dropoff locations through Geoapify.
    """
    if len(q.strip()) < 2:
        return []
    return await service.search_locations(q)

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
    background_tasks: BackgroundTasks,
    transport_service: TransportService = Depends(get_transport_service)
):
    """
    Create a new transport booking.

    This endpoint:
    1. Creates the transport booking record in the database
    2. Sends a notification email to the admin/business team (background task)
    3. Sends a confirmation email to the customer (background task)
    4. Returns the booking reference and status
    """
    try:
        booking = transport_service.create_booking(booking_data)

        # Fetch detailed booking (with vehicle category relation) for email templates
        detailed_booking = transport_service.get_booking_by_id(booking.id)
        if detailed_booking:
            detailed_response = TransportBookingDetailResponse.model_validate(detailed_booking, from_attributes=True)
            # Dispatch dual email notifications as background tasks
            background_tasks.add_task(send_transport_notification_email, detailed_response)        # Admin/Business team
            background_tasks.add_task(send_transport_customer_confirmation_email, detailed_response)  # Customer
            logger.info(f"Transport booking created: {booking.booking_reference} — email tasks queued")
        else:
            logger.warning(f"Transport booking created ({booking.booking_reference}) but could not fetch details for email dispatch")

        return TransportBookingResponse(
            id=booking.id,
            booking_reference=booking.booking_reference,
            booking_status=booking.booking_status,
            payment_status=booking.payment_status
        )
    except Exception as e:
        logger.error(f"Error creating transport booking: {str(e)}")
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
