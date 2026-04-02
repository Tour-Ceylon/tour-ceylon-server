from datetime import date, datetime
from decimal import Decimal
from typing import Optional
from uuid import UUID

from sqlalchemy import and_, func
from sqlalchemy.orm import Session, joinedload

from app.models.booking import Booking
from app.models.bookingItem import BookingItem
from app.models.bookingTraveler import BookingTraveler
from app.models.enum import BookingStatus
from app.schemas.booking_schema import BookingCreate, BookingSearchParams, BookingUpdate


class BookingRepository:
    """Repository class for Booking model database operations"""

    def __init__(self, db: Session):
        self.db = db

    def _base_query(self):
        return self.db.query(Booking).options(
            joinedload(Booking.booking_items).joinedload(BookingItem.travelers)
        )

    def create(self, booking_data: BookingCreate) -> Booking:
        booking_payload = booking_data.model_dump()
        item_payloads = booking_payload.pop("booking_items")

        db_booking = Booking(**booking_payload)
        self.db.add(db_booking)
        self.db.flush()

        self._replace_booking_items(db_booking, item_payloads)

        self.db.commit()
        self.db.refresh(db_booking)
        return self.get_by_id(db_booking.id)

    def get_by_id(self, booking_id: UUID) -> Optional[Booking]:
        return self._base_query().filter(Booking.id == booking_id).first()

    def get_by_user_id(self, user_id: UUID) -> list[Booking]:
        return self._base_query().filter(Booking.user_id == user_id).all()

    def get_by_listing_id(self, listing_id: UUID) -> list[Booking]:
        return (
            self._base_query()
            .join(Booking.booking_items)
            .filter(BookingItem.listing_id == listing_id)
            .distinct()
            .all()
        )

    def get_all(
        self,
        skip: int = 0,
        limit: int = 100,
        status: Optional[BookingStatus] = None,
    ) -> list[Booking]:
        query = self._base_query()

        if status is not None:
            query = query.filter(Booking.status == status)

        return query.order_by(Booking.created_at.desc()).offset(skip).limit(limit).all()

    def search(self, search_params: BookingSearchParams) -> tuple[list[Booking], int]:
        query = self._base_query()
        count_query = self.db.query(func.count(func.distinct(Booking.id)))
        needs_item_join = any(
            [
                search_params.listing_id,
                search_params.variant_id,
                search_params.travel_date_from,
                search_params.travel_date_to,
            ]
        )

        if needs_item_join:
            query = query.join(Booking.booking_items)
            count_query = count_query.select_from(Booking).join(Booking.booking_items)
        else:
            count_query = count_query.select_from(Booking)

        filters = []

        if search_params.user_id:
            filters.append(Booking.user_id == search_params.user_id)

        if search_params.status:
            filters.append(Booking.status == search_params.status)

        if search_params.booked_at_from:
            filters.append(Booking.booked_at >= search_params.booked_at_from)

        if search_params.booked_at_to:
            filters.append(Booking.booked_at <= search_params.booked_at_to)

        if search_params.min_total_amount is not None:
            filters.append(Booking.total_amount >= search_params.min_total_amount)

        if search_params.max_total_amount is not None:
            filters.append(Booking.total_amount <= search_params.max_total_amount)

        if search_params.listing_id:
            filters.append(BookingItem.listing_id == search_params.listing_id)

        if search_params.variant_id:
            filters.append(BookingItem.variant_id == search_params.variant_id)

        if search_params.travel_date_from:
            filters.append(BookingItem.travel_date >= search_params.travel_date_from)

        if search_params.travel_date_to:
            filters.append(BookingItem.travel_date <= search_params.travel_date_to)

        if filters:
            criteria = and_(*filters)
            query = query.filter(criteria)
            count_query = count_query.filter(criteria)

        total_count = count_query.scalar() or 0
        skip = (search_params.page - 1) * search_params.per_page
        bookings = (
            query.order_by(Booking.created_at.desc())
            .distinct()
            .offset(skip)
            .limit(search_params.per_page)
            .all()
        )

        return bookings, total_count

    def update(self, booking_id: UUID, booking_data: BookingUpdate) -> Optional[Booking]:
        db_booking = self.get_by_id(booking_id)
        if not db_booking:
            return None

        update_data = booking_data.model_dump(exclude_unset=True)
        item_payloads = update_data.pop("booking_items", None)

        for field, value in update_data.items():
            setattr(db_booking, field, value)

        if item_payloads is not None:
            self._replace_booking_items(db_booking, item_payloads)

        self.db.commit()
        self.db.refresh(db_booking)
        return self.get_by_id(db_booking.id)

    def delete(self, booking_id: UUID) -> bool:
        db_booking = self.get_by_id(booking_id)
        if not db_booking:
            return False

        self.db.delete(db_booking)
        self.db.commit()
        return True

    def update_status(self, booking_id: UUID, status: BookingStatus) -> Optional[Booking]:
        db_booking = self.get_by_id(booking_id)
        if not db_booking:
            return None

        db_booking.status = status
        self.db.commit()
        self.db.refresh(db_booking)
        return self.get_by_id(db_booking.id)

    def get_by_status(self, status: BookingStatus) -> list[Booking]:
        return self._base_query().filter(Booking.status == status).all()

    def get_user_bookings_by_status(self, user_id: UUID, status: BookingStatus) -> list[Booking]:
        return (
            self._base_query()
            .filter(Booking.user_id == user_id, Booking.status == status)
            .all()
        )

    def get_listing_bookings_by_status(self, listing_id: UUID, status: BookingStatus) -> list[Booking]:
        return (
            self._base_query()
            .join(Booking.booking_items)
            .filter(BookingItem.listing_id == listing_id, Booking.status == status)
            .distinct()
            .all()
        )

    def get_bookings_by_date_range(self, start_date: date, end_date: date) -> list[Booking]:
        return (
            self._base_query()
            .join(Booking.booking_items)
            .filter(BookingItem.travel_date >= start_date, BookingItem.travel_date <= end_date)
            .distinct()
            .all()
        )

    def count_by_status(self) -> dict:
        results = (
            self.db.query(Booking.status, func.count(Booking.id))
            .group_by(Booking.status)
            .all()
        )
        return {status: count for status, count in results}

    def count_by_user(self, user_id: UUID) -> int:
        return self.db.query(Booking).filter(Booking.user_id == user_id).count()

    def count_by_listing(self, listing_id: UUID) -> int:
        result = (
            self.db.query(func.count(func.distinct(Booking.id)))
            .join(Booking.booking_items)
            .filter(BookingItem.listing_id == listing_id)
            .scalar()
        )
        return result or 0

    def get_total_revenue(self, status: Optional[BookingStatus] = None) -> Decimal:
        query = self.db.query(func.sum(Booking.total_amount))

        if status:
            query = query.filter(Booking.status == status)

        result = query.scalar()
        return result or Decimal("0")

    def get_user_total_spent(self, user_id: UUID, status: Optional[BookingStatus] = None) -> Decimal:
        query = self.db.query(func.sum(Booking.total_amount)).filter(Booking.user_id == user_id)

        if status:
            query = query.filter(Booking.status == status)

        result = query.scalar()
        return result or Decimal("0")

    def get_listing_total_revenue(self, listing_id: UUID, status: Optional[BookingStatus] = None) -> Decimal:
        booking_ids_query = (
            self.db.query(Booking.id)
            .join(Booking.booking_items)
            .filter(BookingItem.listing_id == listing_id)
        )
        if status:
            booking_ids_query = booking_ids_query.filter(Booking.status == status)

        booking_ids_subquery = booking_ids_query.distinct().subquery()
        result = (
            self.db.query(func.sum(Booking.total_amount))
            .filter(Booking.id.in_(booking_ids_subquery))
            .scalar()
        )
        return result or Decimal("0")

    def get_monthly_revenue(self, year: int, month: int) -> Decimal:
        start_date = datetime(year, month, 1)
        if month == 12:
            end_date = datetime(year + 1, 1, 1)
        else:
            end_date = datetime(year, month + 1, 1)

        result = (
            self.db.query(func.sum(Booking.total_amount))
            .filter(
                Booking.created_at >= start_date,
                Booking.created_at < end_date,
                Booking.status.in_([BookingStatus.CONFIRMED, BookingStatus.COMPLETED]),
            )
            .scalar()
        )
        return result or Decimal("0")

    def exists_booking(self, user_id: UUID, listing_id: UUID, travel_date: date) -> bool:
        return (
            self.db.query(Booking)
            .join(Booking.booking_items)
            .filter(
                Booking.user_id == user_id,
                BookingItem.listing_id == listing_id,
                BookingItem.travel_date == travel_date,
            )
            .first()
            is not None
        )

    def _replace_booking_items(self, booking: Booking, item_payloads: list[dict]) -> None:
        booking.booking_items.clear()
        self.db.flush()

        for item_payload in item_payloads:
            traveler_payloads = item_payload.pop("travelers", [])
            booking_item = BookingItem(booking_id=booking.id, **item_payload)
            for traveler_payload in traveler_payloads:
                booking_item.travelers.append(BookingTraveler(**traveler_payload))
            booking.booking_items.append(booking_item)


def get_booking_repository(db: Session = None) -> BookingRepository:
    """Get booking repository instance"""
    if db is None:
        from app.config.database import SessionLocal

        db = SessionLocal()
    return BookingRepository(db)
