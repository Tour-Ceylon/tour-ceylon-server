from datetime import date, datetime, timezone
from typing import List, Optional
from uuid import UUID
from sqlalchemy import func, or_
from sqlalchemy.orm import Session, joinedload

from app.models.driver import Driver, TripDeclineReason
from app.models.enum import AssignmentStatus
from app.models.transportBooking import TransportBooking


class DriverTripRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_driver_by_user_id(self, user_id: UUID) -> Optional[Driver]:
        return (
            self.db.query(Driver)
            .filter(Driver.user_id == user_id)
            .first()
        )

    def get_driver_by_id(self, driver_id: UUID) -> Optional[Driver]:
        return (
            self.db.query(Driver)
            .filter(Driver.id == driver_id)
            .first()
        )

    def update_driver_availability(self, driver: Driver, is_online: bool) -> Driver:
        driver.is_online = is_online
        if is_online:
            driver.last_online_at = datetime.now(timezone.utc)
        self.db.commit()
        self.db.refresh(driver)
        return driver

    def get_driver_trips(self, driver_id: UUID, status_bucket: str) -> List[TransportBooking]:
        query = (
            self.db.query(TransportBooking)
            .options(joinedload(TransportBooking.vehicle_category))
        )

        if status_bucket == "assigned":
            return (
                query.filter(
                    TransportBooking.driver_id == driver_id,
                    TransportBooking.assignment_status == AssignmentStatus.ASSIGNED.value
                )
                .order_by(TransportBooking.assigned_at.desc(), TransportBooking.travel_date.asc())
                .all()
            )
        elif status_bucket == "upcoming":
            return (
                query.filter(
                    TransportBooking.driver_id == driver_id,
                    TransportBooking.assignment_status.in_([
                        AssignmentStatus.ACKNOWLEDGED.value,
                        AssignmentStatus.EN_ROUTE.value,
                        AssignmentStatus.ARRIVED.value,
                        AssignmentStatus.IN_PROGRESS.value,
                    ])
                )
                .order_by(TransportBooking.travel_date.asc(), TransportBooking.pickup_time.asc())
                .all()
            )
        elif status_bucket == "history":
            return (
                query.filter(
                    TransportBooking.driver_id == driver_id,
                    or_(
                        TransportBooking.assignment_status == AssignmentStatus.COMPLETED.value,
                        TransportBooking.booking_status.in_(["completed", "cancelled"])
                    )
                )
                .order_by(TransportBooking.travel_date.desc(), TransportBooking.pickup_time.desc())
                .all()
            )
        else:
            return (
                query.filter(TransportBooking.driver_id == driver_id)
                .order_by(TransportBooking.travel_date.desc())
                .all()
            )

    def get_driver_trip_by_id(self, driver_id: UUID, booking_id: UUID) -> Optional[TransportBooking]:
        return (
            self.db.query(TransportBooking)
            .options(joinedload(TransportBooking.vehicle_category))
            .filter(
                TransportBooking.id == booking_id,
                TransportBooking.driver_id == driver_id
            )
            .first()
        )

    def update_assignment_status(
        self,
        booking: TransportBooking,
        new_status: str,
        responded_at: Optional[datetime] = None
    ) -> TransportBooking:
        booking.assignment_status = new_status
        now = datetime.now(timezone.utc)
        if responded_at:
            booking.driver_responded_at = responded_at
        if new_status == AssignmentStatus.COMPLETED.value:
            booking.booking_status = "completed"
            booking.driver_responded_at = now
        self.db.commit()
        self.db.refresh(booking)
        return booking

    def record_decline_and_unassign(
        self,
        booking: TransportBooking,
        driver_id: UUID,
        reason: str,
        note: Optional[str] = None
    ) -> TripDeclineReason:
        decline_record = TripDeclineReason(
            transport_booking_id=booking.id,
            driver_id=driver_id,
            reason=reason,
            note=note,
        )
        self.db.add(decline_record)

        booking.driver_id = None
        booking.assignment_status = AssignmentStatus.UNASSIGNED.value
        booking.driver_responded_at = datetime.now(timezone.utc)

        self.db.commit()
        self.db.refresh(decline_record)
        return decline_record

    def get_driver_declines(self, driver_id: UUID) -> List[TripDeclineReason]:
        return (
            self.db.query(TripDeclineReason)
            .options(joinedload(TripDeclineReason.transport_booking))
            .filter(TripDeclineReason.driver_id == driver_id)
            .order_by(TripDeclineReason.created_at.desc())
            .all()
        )

    def get_completed_trips_in_date_range(
        self,
        driver_id: UUID,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None
    ) -> List[TransportBooking]:
        query = (
            self.db.query(TransportBooking)
            .filter(
                TransportBooking.driver_id == driver_id,
                or_(
                    TransportBooking.assignment_status == AssignmentStatus.COMPLETED.value,
                    TransportBooking.booking_status == "completed"
                )
            )
        )
        return query.order_by(TransportBooking.travel_date.asc(), TransportBooking.updated_at.asc()).all()
