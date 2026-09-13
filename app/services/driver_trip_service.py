from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Dict, List, Optional
from uuid import UUID
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.driver import Driver
from app.models.enum import AssignmentStatus, DriverStatus
from app.models.transportBooking import TransportBooking
from app.repositories.driver_trip_repository import DriverTripRepository
from app.schemas.driver_trip_schema import (
    DriverAvailabilityResponse,
    DriverDailyEarningItem,
    DriverEarningsResponse,
    DriverTripCustomerInfo,
    DriverTripDeclineRecordResponse,
    DriverTripDetailResponse,
    DriverTripSummaryResponse,
)


ALLOWED_TRANSITIONS = {
    AssignmentStatus.ACKNOWLEDGED.value: [AssignmentStatus.EN_ROUTE.value],
    AssignmentStatus.EN_ROUTE.value: [AssignmentStatus.ARRIVED.value],
    AssignmentStatus.ARRIVED.value: [AssignmentStatus.IN_PROGRESS.value],
    AssignmentStatus.IN_PROGRESS.value: [AssignmentStatus.COMPLETED.value],
}


class DriverTripService:
    def __init__(self, db: Session):
        self.db = db
        self.repo = DriverTripRepository(db)

    def _resolve_driver(self, user_id: UUID) -> Driver:
        driver = self.repo.get_driver_by_user_id(user_id)
        if not driver:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Driver profile not found for the authenticated user",
            )
        if driver.status != DriverStatus.APPROVED.value:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Driver account is currently in '{driver.status}' status and cannot perform this action",
            )
        return driver

    def get_availability(self, user_id: UUID) -> DriverAvailabilityResponse:
        driver = self._resolve_driver(user_id)
        return DriverAvailabilityResponse(
            is_online=driver.is_online,
            last_online_at=driver.last_online_at,
        )

    def update_availability(self, user_id: UUID, is_online: bool) -> DriverAvailabilityResponse:
        driver = self._resolve_driver(user_id)
        updated = self.repo.update_driver_availability(driver, is_online)
        return DriverAvailabilityResponse(
            is_online=updated.is_online,
            last_online_at=updated.last_online_at,
        )

    def _format_summary(self, booking: TransportBooking) -> DriverTripSummaryResponse:
        return DriverTripSummaryResponse(
            id=booking.id,
            booking_reference=booking.booking_reference,
            travel_date=booking.travel_date,
            pickup_time=booking.pickup_time,
            pickup_location=booking.pickup_location,
            destination_location=booking.destination_location,
            distance_km=booking.distance_km,
            estimated_duration_minutes=booking.estimated_duration_minutes,
            passengers_count=booking.passengers_count,
            luggage_count=booking.luggage_count,
            special_requests=booking.special_requests,
            total_price=booking.total_price,
            currency=booking.currency,
            booking_status=booking.booking_status,
            payment_status=booking.payment_status,
            assignment_status=booking.assignment_status,
            assigned_at=booking.assigned_at,
            driver_responded_at=booking.driver_responded_at,
            created_at=booking.created_at,
            customer_name=booking.customer_name,
            customer_phone=booking.customer_phone,
        )

    def _format_detail(self, booking: TransportBooking) -> DriverTripDetailResponse:
        return DriverTripDetailResponse(
            id=booking.id,
            booking_reference=booking.booking_reference,
            travel_date=booking.travel_date,
            pickup_time=booking.pickup_time,
            pickup_location=booking.pickup_location,
            pickup_lat=booking.pickup_lat,
            pickup_lng=booking.pickup_lng,
            destination_location=booking.destination_location,
            destination_lat=booking.destination_lat,
            destination_lng=booking.destination_lng,
            distance_km=booking.distance_km,
            estimated_duration_minutes=booking.estimated_duration_minutes,
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
            customer=DriverTripCustomerInfo(
                name=booking.customer_name,
                phone=booking.customer_phone,
                email=booking.customer_email,
                country=booking.customer_country,
            ),
            vehicle_category_name=booking.vehicle_category.name if booking.vehicle_category else None,
        )

    def get_trips(self, user_id: UUID, status_bucket: str = "assigned") -> List[DriverTripSummaryResponse]:
        driver = self._resolve_driver(user_id)
        trips = self.repo.get_driver_trips(driver.id, status_bucket)
        return [self._format_summary(t) for t in trips]

    def get_trip_detail(self, user_id: UUID, booking_id: UUID) -> DriverTripDetailResponse:
        driver = self._resolve_driver(user_id)
        booking = self.repo.get_driver_trip_by_id(driver.id, booking_id)
        if not booking:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Trip booking not found or not assigned to this driver",
            )
        return self._format_detail(booking)

    def acknowledge_trip(self, user_id: UUID, booking_id: UUID) -> DriverTripDetailResponse:
        driver = self._resolve_driver(user_id)
        booking = self.repo.get_driver_trip_by_id(driver.id, booking_id)
        if not booking:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Trip booking not found or not assigned to this driver",
            )

        if booking.assignment_status != AssignmentStatus.ASSIGNED.value:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot acknowledge trip in '{booking.assignment_status}' state. Must be 'assigned'.",
            )

        updated = self.repo.update_assignment_status(
            booking=booking,
            new_status=AssignmentStatus.ACKNOWLEDGED.value,
            responded_at=datetime.now(timezone.utc),
        )
        return self._format_detail(updated)

    def decline_trip(
        self,
        user_id: UUID,
        booking_id: UUID,
        reason: str,
        note: Optional[str] = None
    ) -> DriverTripDeclineRecordResponse:
        driver = self._resolve_driver(user_id)
        booking = self.repo.get_driver_trip_by_id(driver.id, booking_id)
        if not booking:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Trip booking not found or not assigned to this driver",
            )

        if booking.assignment_status != AssignmentStatus.ASSIGNED.value:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot decline trip in '{booking.assignment_status}' state. Trips can only be declined before acknowledging.",
            )

        decline_record = self.repo.record_decline_and_unassign(
            booking=booking,
            driver_id=driver.id,
            reason=reason,
            note=note,
        )

        return DriverTripDeclineRecordResponse(
            id=decline_record.id,
            transport_booking_id=booking.id,
            booking_reference=booking.booking_reference,
            pickup_location=booking.pickup_location,
            destination_location=booking.destination_location,
            travel_date=booking.travel_date,
            total_price=booking.total_price,
            currency=booking.currency,
            reason=decline_record.reason,
            note=decline_record.note,
            created_at=decline_record.created_at,
        )

    def update_trip_status(
        self,
        user_id: UUID,
        booking_id: UUID,
        target_status: str
    ) -> DriverTripDetailResponse:
        driver = self._resolve_driver(user_id)
        booking = self.repo.get_driver_trip_by_id(driver.id, booking_id)
        if not booking:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Trip booking not found or not assigned to this driver",
            )

        current_status = booking.assignment_status
        allowed_next = ALLOWED_TRANSITIONS.get(current_status, [])

        if target_status not in allowed_next:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"Invalid status transition from '{current_status}' to '{target_status}'. "
                    f"Expected transition: {allowed_next if allowed_next else 'None (terminal state)'}"
                ),
            )

        updated = self.repo.update_assignment_status(booking=booking, new_status=target_status)
        return self._format_detail(updated)

    def get_earnings(self, user_id: UUID, period: str = "today") -> DriverEarningsResponse:
        driver = self._resolve_driver(user_id)
        today = date.today()

        if period == "today":
            start_date = today
            end_date = today
        elif period == "week":
            start_date = today - timedelta(days=6)
            end_date = today
        elif period == "month":
            start_date = today - timedelta(days=29)
            end_date = today
        else:
            start_date = today
            end_date = today
            period = "today"

        all_completed_trips = self.repo.get_completed_trips_in_date_range(driver.id)

        def _to_local_date(val) -> date:
            if isinstance(val, datetime):
                return val.astimezone().date() if val.tzinfo else val.date()
            elif isinstance(val, date):
                return val
            return today

        # Build daily buckets for chart
        daily_map: Dict[str, Dict] = {}
        curr = start_date
        while curr <= end_date:
            date_str = curr.isoformat()
            day_name = curr.strftime("%a")
            daily_map[date_str] = {
                "date": date_str,
                "day_name": day_name,
                "earnings": Decimal("0.00"),
                "trip_count": 0,
            }
            curr += timedelta(days=1)

        total_earnings = Decimal("0.00")
        period_trip_count = 0

        for trip in all_completed_trips:
            # Determine effective completion date with timezone awareness
            comp_date = None
            if trip.driver_responded_at:
                comp_date = _to_local_date(trip.driver_responded_at)
            elif trip.updated_at:
                comp_date = _to_local_date(trip.updated_at)
            elif trip.travel_date:
                comp_date = _to_local_date(trip.travel_date)

            if not comp_date:
                comp_date = today

            # Check if this completed trip belongs in the requested period
            is_in_period = False
            if period == "today":
                if comp_date == today or trip.travel_date == today or (trip.travel_date >= today and trip.updated_at and trip.updated_at.date() == today) or (trip.assignment_status == AssignmentStatus.COMPLETED.value and trip.updated_at and trip.updated_at.date() == today):
                    is_in_period = True
            else:
                if start_date <= comp_date <= end_date or (trip.travel_date and start_date <= trip.travel_date <= end_date):
                    is_in_period = True
                elif trip.updated_at and start_date <= trip.updated_at.date() <= end_date:
                    is_in_period = True
                elif comp_date >= start_date:
                    is_in_period = True

            if is_in_period:
                fare = Decimal(str(trip.total_price or 0))
                total_earnings += fare
                period_trip_count += 1

                bucket_key = comp_date.isoformat() if comp_date.isoformat() in daily_map else today.isoformat()
                if bucket_key in daily_map:
                    daily_map[bucket_key]["earnings"] += fare
                    daily_map[bucket_key]["trip_count"] += 1

        daily_items = [
            DriverDailyEarningItem(
                date=item["date"],
                day_name=item["day_name"],
                earnings=item["earnings"],
                trip_count=item["trip_count"],
            )
            for item in daily_map.values()
        ]

        return DriverEarningsResponse(
            period=period,
            total_earnings=total_earnings,
            trip_count=period_trip_count,
            currency="USD",
            daily_breakdown=daily_items,
            start_date=start_date,
            end_date=end_date,
        )
