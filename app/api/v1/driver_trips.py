from typing import List, Optional
from uuid import UUID
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.config.database import get_db
from app.models.user import User
from app.schemas.driver_trip_schema import (
    DriverAvailabilityResponse,
    DriverAvailabilityUpdate,
    DriverEarningsResponse,
    DriverTripDeclineRecordResponse,
    DriverTripDeclineRequest,
    DriverTripDetailResponse,
    DriverTripStatusUpdate,
    DriverTripSummaryResponse,
)
from app.services.driver_trip_service import DriverTripService

router = APIRouter(prefix="/drivers/me", tags=["driver-trips"])


def get_driver_trip_service(db: Session = Depends(get_db)) -> DriverTripService:
    return DriverTripService(db)


@router.get("/availability", response_model=DriverAvailabilityResponse)
def get_my_availability(
    current_user: User = Depends(get_current_user),
    service: DriverTripService = Depends(get_driver_trip_service),
):
    """Get the authenticated driver's online/offline availability status."""
    return service.get_availability(current_user.id)


@router.patch("/availability", response_model=DriverAvailabilityResponse)
def update_my_availability(
    payload: DriverAvailabilityUpdate,
    current_user: User = Depends(get_current_user),
    service: DriverTripService = Depends(get_driver_trip_service),
):
    """Toggle the authenticated driver's online/offline status."""
    return service.update_availability(current_user.id, payload.is_online)


@router.get("/trips", response_model=List[DriverTripSummaryResponse])
def list_my_trips(
    status: str = Query("assigned", description="Trip bucket: assigned, upcoming, or history"),
    current_user: User = Depends(get_current_user),
    service: DriverTripService = Depends(get_driver_trip_service),
):
    """List trips for the authenticated driver filtered by bucket (assigned, upcoming, history)."""
    return service.get_trips(current_user.id, status_bucket=status)


@router.get("/trips/{booking_id}", response_model=DriverTripDetailResponse)
def get_my_trip_detail(
    booking_id: UUID,
    current_user: User = Depends(get_current_user),
    service: DriverTripService = Depends(get_driver_trip_service),
):
    """Get full details for a trip assigned to the authenticated driver."""
    return service.get_trip_detail(current_user.id, booking_id)


@router.post("/trips/{booking_id}/acknowledge", response_model=DriverTripDetailResponse)
def acknowledge_trip(
    booking_id: UUID,
    current_user: User = Depends(get_current_user),
    service: DriverTripService = Depends(get_driver_trip_service),
):
    """Acknowledge/accept an assigned trip."""
    return service.acknowledge_trip(current_user.id, booking_id)


@router.post("/trips/{booking_id}/decline", response_model=DriverTripDeclineRecordResponse)
def decline_trip(
    booking_id: UUID,
    payload: DriverTripDeclineRequest,
    current_user: User = Depends(get_current_user),
    service: DriverTripService = Depends(get_driver_trip_service),
):
    """Decline an assigned trip with a reason, releasing it back to unassigned."""
    return service.decline_trip(current_user.id, booking_id, reason=payload.reason, note=payload.note)


@router.patch("/trips/{booking_id}/status", response_model=DriverTripDetailResponse)
def update_trip_status(
    booking_id: UUID,
    payload: DriverTripStatusUpdate,
    current_user: User = Depends(get_current_user),
    service: DriverTripService = Depends(get_driver_trip_service),
):
    """Advance trip progress sequentially: en_route -> arrived -> in_progress -> completed."""
    return service.update_trip_status(current_user.id, booking_id, target_status=payload.status)


@router.get("/earnings", response_model=DriverEarningsResponse)
def get_my_earnings(
    period: str = Query("today", description="Earnings period: today, week, or month"),
    current_user: User = Depends(get_current_user),
    service: DriverTripService = Depends(get_driver_trip_service),
):
    """Get earnings and daily breakdowns for the authenticated driver."""
    return service.get_earnings(current_user.id, period=period)
