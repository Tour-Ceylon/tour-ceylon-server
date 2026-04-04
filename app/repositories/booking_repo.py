from datetime import datetime
from typing import Optional
from uuid import UUID

from sqlalchemy import and_, func
from sqlalchemy.orm import Session

from app.models.booking import Booking
from app.models.enum import BookingStatus
from app.schemas.booking_schema import BookingCreate, BookingSearchParams, BookingUpdate


class BookingRepository:
	def __init__(self, db: Session):
		self.db = db

	def create(self, booking_data: BookingCreate) -> Booking:
		booking = Booking(**booking_data.model_dump())
		self.db.add(booking)
		self.db.commit()
		self.db.refresh(booking)
		return booking

	def get_by_id(self, booking_id: UUID) -> Optional[Booking]:
		return self.db.query(Booking).filter(Booking.id == booking_id).first()

	def get_all(self, skip: int = 0, limit: int = 100, status: Optional[BookingStatus] = None) -> list[Booking]:
		query = self.db.query(Booking)
		if status is not None:
			query = query.filter(Booking.status == status)
		return query.order_by(Booking.created_at.desc()).offset(skip).limit(limit).all()

	def get_by_user_id(self, user_id: UUID) -> list[Booking]:
		return (
			self.db.query(Booking)
			.filter(Booking.user_id == user_id)
			.order_by(Booking.created_at.desc())
			.all()
		)

	def get_by_listing_id(self, listing_id: UUID) -> list[Booking]:
		return (
			self.db.query(Booking)
			.filter(Booking.listing_id == listing_id)
			.order_by(Booking.created_at.desc())
			.all()
		)

	def get_by_status(self, status: BookingStatus) -> list[Booking]:
		return (
			self.db.query(Booking)
			.filter(Booking.status == status)
			.order_by(Booking.created_at.desc())
			.all()
		)

	def get_user_bookings_by_status(self, user_id: UUID, status: BookingStatus) -> list[Booking]:
		return (
			self.db.query(Booking)
			.filter(Booking.user_id == user_id, Booking.status == status)
			.order_by(Booking.created_at.desc())
			.all()
		)

	def get_listing_bookings_by_status(self, listing_id: UUID, status: BookingStatus) -> list[Booking]:
		return (
			self.db.query(Booking)
			.filter(Booking.listing_id == listing_id, Booking.status == status)
			.order_by(Booking.created_at.desc())
			.all()
		)

	def exists_booking(self, user_id: UUID, listing_id: UUID, travel_date: datetime) -> bool:
		return (
			self.db.query(Booking)
			.filter(
				Booking.user_id == user_id,
				Booking.listing_id == listing_id,
				Booking.travel_date == travel_date,
				Booking.status != BookingStatus.CANCELLED,
			)
			.first()
			is not None
		)

	def update(self, booking_id: UUID, booking_data: BookingUpdate) -> Optional[Booking]:
		booking = self.get_by_id(booking_id)
		if booking is None:
			return None

		for field, value in booking_data.model_dump(exclude_unset=True).items():
			setattr(booking, field, value)

		self.db.commit()
		self.db.refresh(booking)
		return booking

	def delete(self, booking_id: UUID) -> bool:
		booking = self.get_by_id(booking_id)
		if booking is None:
			return False
		self.db.delete(booking)
		self.db.commit()
		return True

	def update_status(self, booking_id: UUID, status: BookingStatus) -> Optional[Booking]:
		booking = self.get_by_id(booking_id)
		if booking is None:
			return None
		booking.status = status
		self.db.commit()
		self.db.refresh(booking)
		return booking

	def search(self, search_params: BookingSearchParams) -> tuple[list[Booking], int]:
		query = self.db.query(Booking)
		filters = []

		if search_params.user_id:
			filters.append(Booking.user_id == search_params.user_id)
		if search_params.listing_id:
			filters.append(Booking.listing_id == search_params.listing_id)
		if search_params.status:
			filters.append(Booking.status == search_params.status)
		if search_params.travel_date_from:
			filters.append(Booking.travel_date >= search_params.travel_date_from)
		if search_params.travel_date_to:
			filters.append(Booking.travel_date <= search_params.travel_date_to)
		if search_params.min_price is not None:
			filters.append(Booking.total_price_minor >= search_params.min_price)
		if search_params.max_price is not None:
			filters.append(Booking.total_price_minor <= search_params.max_price)

		if filters:
			query = query.filter(and_(*filters))

		total = query.count()
		skip = (search_params.page - 1) * search_params.per_page
		results = query.order_by(Booking.created_at.desc()).offset(skip).limit(search_params.per_page).all()
		return results, total

	def count_by_status(self) -> dict[BookingStatus, int]:
		rows = self.db.query(Booking.status, func.count(Booking.id)).group_by(Booking.status).all()
		return {status: count for status, count in rows}

	def get_total_revenue(self, status: BookingStatus | None = None) -> int:
		query = self.db.query(func.coalesce(func.sum(Booking.total_price_minor), 0))
		if status is not None:
			query = query.filter(Booking.status == status)
		return int(query.scalar() or 0)

	def count_by_user(self, user_id: UUID) -> int:
		return self.db.query(Booking).filter(Booking.user_id == user_id).count()

	def count_by_listing(self, listing_id: UUID) -> int:
		return self.db.query(Booking).filter(Booking.listing_id == listing_id).count()

	def get_user_total_spent(self, user_id: UUID, status: BookingStatus | None = None) -> int:
		query = self.db.query(func.coalesce(func.sum(Booking.total_price_minor), 0)).filter(Booking.user_id == user_id)
		if status is not None:
			query = query.filter(Booking.status == status)
		return int(query.scalar() or 0)

	def get_listing_total_revenue(self, listing_id: UUID, status: BookingStatus | None = None) -> int:
		query = self.db.query(func.coalesce(func.sum(Booking.total_price_minor), 0)).filter(Booking.listing_id == listing_id)
		if status is not None:
			query = query.filter(Booking.status == status)
		return int(query.scalar() or 0)
