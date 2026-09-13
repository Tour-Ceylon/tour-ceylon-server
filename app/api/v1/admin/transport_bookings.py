import math
from datetime import datetime, timezone
from typing import Optional
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, or_
from sqlalchemy.orm import Session, joinedload

from app.api.deps import get_current_user
from app.api.v1.admin.drivers import require_driver_admin
from app.config.database import get_db
from app.models.driver import Driver
from app.models.enum import AssignmentStatus, DriverStatus
from app.models.transportBooking import TransportBooking
from app.models.user import User
from app.schemas.admin.transport_booking_schema import (
    AdminAssignDriverRequest,
    AdminAssignedDriverInfo,
    AdminTransportBookingDetailResponse,
    AdminTransportBookingListResponse,
)

router = APIRouter(prefix="/transport-bookings", tags=["admin-transport-bookings"])


def _to_booking_response(booking: TransportBooking) -> AdminTransportBookingDetailResponse:
    driver_info = None
    if booking.driver:
        full_name = None
        email = None
        phone = None
        if booking.driver.user:
            full_name = booking.driver.user.full_name
            email = booking.driver.user.email
            if booking.driver.user.business_profile:
                phone = booking.driver.user.business_profile.get("phone")

        driver_info = AdminAssignedDriverInfo(
            id=booking.driver.id,
            user_id=booking.driver.user_id,
            full_name=full_name,
            email=email,
            phone=phone,
            nic_number=booking.driver.nic_number,
            vehicle_make=booking.driver.vehicle_make,
            vehicle_model=booking.driver.vehicle_model,
            vehicle_plate_number=booking.driver.vehicle_plate_number,
            seats=booking.driver.seats,
            status=booking.driver.status,
            is_online=booking.driver.is_online,
            rating=float(booking.driver.rating) if booking.driver.rating is not None else None,
        )

    return AdminTransportBookingDetailResponse(
        id=booking.id,
        booking_reference=booking.booking_reference,
        customer_name=booking.customer_name,
        customer_email=booking.customer_email,
        customer_phone=booking.customer_phone,
        customer_country=booking.customer_country,
        pickup_location=booking.pickup_location,
        pickup_lat=booking.pickup_lat,
        pickup_lng=booking.pickup_lng,
        destination_location=booking.destination_location,
        destination_lat=booking.destination_lat,
        destination_lng=booking.destination_lng,
        distance_km=booking.distance_km,
        estimated_duration_minutes=booking.estimated_duration_minutes,
        travel_date=booking.travel_date,
        pickup_time=booking.pickup_time,
        passengers_count=booking.passengers_count,
        luggage_count=booking.luggage_count,
        special_requests=booking.special_requests,
        base_fare=booking.base_fare,
        price_per_km=booking.price_per_km,
        route_price=booking.route_price,
        extra_charges=booking.extra_charges,
        total_price=booking.total_price,
        currency=booking.currency,
        booking_status=booking.booking_status,
        payment_status=booking.payment_status,
        assignment_status=booking.assignment_status,
        assigned_at=booking.assigned_at,
        driver_responded_at=booking.driver_responded_at,
        created_at=booking.created_at,
        internal_notes=booking.internal_notes,
        vehicle_category=booking.vehicle_category,
        driver=driver_info,
    )


@router.get("", response_model=AdminTransportBookingListResponse)
def list_admin_transport_bookings(
    assignment_status: Optional[str] = Query(None, description="Filter by assignment status: unassigned, assigned, etc."),
    booking_status: Optional[str] = Query(None, description="Filter by booking status: pending, confirmed, completed, cancelled"),
    search: Optional[str] = Query(None, description="Search by customer, reference, pickup, destination"),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    _: User = Depends(require_driver_admin),
    db: Session = Depends(get_db),
):
    """List transport bookings with assignment status and driver details for admin dispatch."""
    query = (
        db.query(TransportBooking)
        .options(
            joinedload(TransportBooking.vehicle_category),
            joinedload(TransportBooking.driver).joinedload(Driver.user),
        )
    )

    if assignment_status:
        query = query.filter(TransportBooking.assignment_status == assignment_status)

    if booking_status:
        query = query.filter(TransportBooking.booking_status == booking_status)

    if search:
        pattern = f"%{search}%"
        query = query.filter(
            or_(
                TransportBooking.booking_reference.ilike(pattern),
                TransportBooking.customer_name.ilike(pattern),
                TransportBooking.customer_email.ilike(pattern),
                TransportBooking.pickup_location.ilike(pattern),
                TransportBooking.destination_location.ilike(pattern),
            )
        )

    total = query.count()
    skip = (page - 1) * per_page
    bookings = query.order_by(TransportBooking.created_at.desc()).offset(skip).limit(per_page).all()

    # Calculate status breakdown counts across the full dataset
    unassigned_count = db.query(func.count(TransportBooking.id)).filter(
        TransportBooking.assignment_status == AssignmentStatus.UNASSIGNED.value
    ).scalar() or 0

    assigned_count = db.query(func.count(TransportBooking.id)).filter(
        TransportBooking.assignment_status == AssignmentStatus.ASSIGNED.value
    ).scalar() or 0

    in_progress_count = db.query(func.count(TransportBooking.id)).filter(
        TransportBooking.assignment_status.in_([
            AssignmentStatus.ACKNOWLEDGED.value,
            AssignmentStatus.EN_ROUTE.value,
            AssignmentStatus.ARRIVED.value,
            AssignmentStatus.IN_PROGRESS.value,
        ])
    ).scalar() or 0

    completed_count = db.query(func.count(TransportBooking.id)).filter(
        TransportBooking.assignment_status == AssignmentStatus.COMPLETED.value
    ).scalar() or 0

    return AdminTransportBookingListResponse(
        bookings=[_to_booking_response(b) for b in bookings],
        total=total,
        page=page,
        per_page=per_page,
        total_pages=math.ceil(total / per_page) if total > 0 else 0,
        unassigned_count=unassigned_count,
        assigned_count=assigned_count,
        in_progress_count=in_progress_count,
        completed_count=completed_count,
    )


@router.get("/{booking_id}", response_model=AdminTransportBookingDetailResponse)
def get_admin_transport_booking(
    booking_id: UUID,
    _: User = Depends(require_driver_admin),
    db: Session = Depends(get_db),
):
    """Get single transport booking with full driver and assignment info."""
    booking = (
        db.query(TransportBooking)
        .options(
            joinedload(TransportBooking.vehicle_category),
            joinedload(TransportBooking.driver).joinedload(Driver.user),
        )
        .filter(TransportBooking.id == booking_id)
        .first()
    )
    if not booking:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Transport booking not found",
        )
    return _to_booking_response(booking)


@router.patch("/{booking_id}/assign", response_model=AdminTransportBookingDetailResponse)
def assign_driver_to_booking(
    booking_id: UUID,
    payload: AdminAssignDriverRequest,
    _: User = Depends(require_driver_admin),
    db: Session = Depends(get_db),
):
    """Assign an approved driver to a transport booking."""
    booking = (
        db.query(TransportBooking)
        .options(
            joinedload(TransportBooking.vehicle_category),
            joinedload(TransportBooking.driver).joinedload(Driver.user),
        )
        .filter(TransportBooking.id == booking_id)
        .first()
    )
    if not booking:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Transport booking not found",
        )

    driver = db.query(Driver).options(joinedload(Driver.user)).filter(Driver.id == payload.driver_id).first()
    if not driver:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Target driver not found",
        )

    if driver.status != DriverStatus.APPROVED.value:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Driver is currently in '{driver.status}' status and must be approved before being assigned trips.",
        )

    booking.driver_id = driver.id
    booking.driver = driver
    booking.assignment_status = AssignmentStatus.ASSIGNED.value
    booking.assigned_at = datetime.now(timezone.utc)
    booking.driver_responded_at = None

    db.commit()
    db.refresh(booking)

    return _to_booking_response(booking)
