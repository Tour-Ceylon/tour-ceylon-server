from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, timedelta
from decimal import Decimal
import logging
import time
from uuid import UUID, uuid4

from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from app.models.booking import Booking
from app.models.bookingItem import BookingItem
from app.models.enum import BookingStatus, CurrencyCode, PaymentTransactionStatus, StayBookingStatus, StayRoomBlockStatus
from app.models.listingVariant import ListingVariant
from app.models.stay import (
    StayBooking,
    StayBookingRoom,
    StayProperty,
    StayRoomBlock,
    StayRoomType,
    StayRoomTypeCalendar,
    StayRoomUnit,
)
from app.models.user import User
from app.schemas.stay_schema import (
    StayAvailabilityNightResponse,
    StayAvailabilityRoomTypeResponse,
    StayAvailabilitySearchRequest,
    StayAvailabilitySearchResponse,
    StayBookingCreate,
    StayBookingListResponse,
    StayBookingResponse,
    StayCalendarResponse,
    StayInventoryResponse,
    StayRoomBlockListResponse,
    StayRoomBlockCreate,
    StayRoomBlockResponse,
    StayRoomTypeCreate,
    StayRoomTypeInventoryResponse,
    StayRoomTypeUpdate,
    StayRoomUnitCreate,
    StayRoomUnitResponse,
    StayRoomUnitUpdate,
)


ACTIVE_PARENT_BOOKING_STATUSES = {
    BookingStatus.PENDING,
    BookingStatus.CONFIRMED,
    BookingStatus.COMPLETED,
}


INACTIVE_UNIT_STATUSES = {"maintenance", "blocked", "inactive", "out_of_service"}
logger = logging.getLogger("app.stay_inventory")


class StayInventoryService:
    def __init__(self, db: Session):
        self.db = db

    def get_property(self, property_id: UUID) -> StayProperty | None:
        return (
            self.db.query(StayProperty)
            .options(
                joinedload(StayProperty.room_types).joinedload(StayRoomType.room_units),
                joinedload(StayProperty.stay_bookings).joinedload(StayBooking.rooms),
            )
            .filter(StayProperty.id == property_id)
            .first()
        )

    def list_inventory(self, property_id: UUID) -> StayInventoryResponse:
        property_record = self._require_property(property_id)
        room_types = [
            StayRoomTypeInventoryResponse.model_validate(
                {
                    **self._room_type_payload(room_type),
                    "totalUnits": len(room_type.room_units or []),
                }
            )
            for room_type in sorted(property_record.room_types or [], key=lambda item: item.name.lower())
        ]
        room_units = [
            StayRoomUnitResponse.model_validate(room_unit)
            for room_unit in sorted(property_record.room_units or [], key=lambda item: item.room_number)
        ]
        return StayInventoryResponse(propertyId=property_record.id, roomTypes=room_types, roomUnits=room_units)

    def create_room_type(self, property_id: UUID, payload: StayRoomTypeCreate) -> StayRoomType:
        property_record = self._require_property(property_id)
        room_type = StayRoomType(
            property_id=property_record.id,
            name=payload.name.strip(),
            description=payload.description,
            size=payload.size,
            size_unit=payload.size_unit,
            max_guests=str(payload.max_guests) if payload.max_guests is not None else None,
            base_price=payload.base_price,
            currency=payload.currency,
            bed_configuration=payload.bed_configuration,
            bathroom=payload.bathroom,
            discounts=payload.discounts,
            metadata_json=payload.metadata,
        )
        self.db.add(room_type)
        self.db.commit()
        self.db.refresh(room_type)
        return room_type

    def update_room_type(self, property_id: UUID, room_type_id: UUID, payload: StayRoomTypeUpdate) -> StayRoomType:
        room_type = self._require_room_type(property_id, room_type_id)
        for field, value in payload.model_dump(by_alias=False, exclude_unset=True).items():
            if field == "max_guests" and value is not None:
                value = str(value)
            if field == "metadata":
                field = "metadata_json"
            setattr(room_type, field, value)
        self.db.add(room_type)
        self.db.commit()
        self.db.refresh(room_type)
        return room_type

    def delete_room_type(self, property_id: UUID, room_type_id: UUID) -> None:
        room_type = self._require_room_type(property_id, room_type_id)
        if room_type.booking_rooms:
            raise ValueError("Cannot delete a room type that has booking history")
        self.db.delete(room_type)
        self.db.commit()

    def create_room_unit(self, property_id: UUID, payload: StayRoomUnitCreate) -> StayRoomUnit:
        self._require_room_type(property_id, payload.room_type_id)
        room_unit = StayRoomUnit(
            property_id=property_id,
            room_type_id=payload.room_type_id,
            room_number=payload.room_number.strip(),
            floor=payload.floor,
            room_name=payload.room_name,
            status=payload.status,
            metadata_json=payload.metadata,
        )
        self.db.add(room_unit)
        self.db.commit()
        self.db.refresh(room_unit)
        return room_unit

    def update_room_unit(self, property_id: UUID, room_unit_id: UUID, payload: StayRoomUnitUpdate) -> StayRoomUnit:
        room_unit = self._require_room_unit(property_id, room_unit_id)
        if payload.room_type_id is not None:
            self._require_room_type(property_id, payload.room_type_id)
        for field, value in payload.model_dump(by_alias=False, exclude_unset=True).items():
            if field == "metadata":
                field = "metadata_json"
            setattr(room_unit, field, value)
        self.db.add(room_unit)
        self.db.commit()
        self.db.refresh(room_unit)
        return room_unit

    def delete_room_unit(self, property_id: UUID, room_unit_id: UUID) -> None:
        room_unit = self._require_room_unit(property_id, room_unit_id)
        if room_unit.booking_rooms:
            raise ValueError("Cannot delete a room unit that has booking history")
        self.db.delete(room_unit)
        self.db.commit()

    def create_room_block(self, property_id: UUID, actor: User, payload: StayRoomBlockCreate) -> StayRoomBlock:
        started_at = time.perf_counter()
        room_unit = self._require_room_unit(property_id, payload.room_unit_id)
        if room_unit.status.lower() in INACTIVE_UNIT_STATUSES:
            raise ValueError("Cannot block an inactive room unit")

        overlapping_booking_exists = (
            self.db.query(StayBookingRoom.id)
            .join(StayBooking, StayBookingRoom.stay_booking_id == StayBooking.id)
            .join(Booking, StayBooking.booking_id == Booking.id)
            .filter(
                StayBookingRoom.room_unit_id == payload.room_unit_id,
                Booking.status.in_(list(ACTIVE_PARENT_BOOKING_STATUSES)),
                StayBooking.status != StayBookingStatus.CANCELLED,
                StayBookingRoom.check_in_date < payload.end_date,
                StayBookingRoom.check_out_date > payload.start_date,
            )
            .first()
            is not None
        )
        if overlapping_booking_exists:
            raise ValueError("Cannot block a room that is already booked in that date range")

        block = StayRoomBlock(
            property_id=property_id,
            room_unit_id=payload.room_unit_id,
            start_date=payload.start_date,
            end_date=payload.end_date,
            block_type=payload.block_type,
            status=StayRoomBlockStatus.ACTIVE,
            reason=payload.reason,
            blocked_by_user_id=actor.id,
            metadata_json=payload.metadata,
        )
        self.db.add(block)
        self.db.flush()
        self.refresh_calendar(property_id, {room_unit.room_type_id}, payload.start_date, payload.end_date - timedelta(days=1))
        self.db.commit()
        self.db.refresh(block)
        logger.info(
            "stay_inventory.create_room_block_timing property_id=%s room_type_id=%s room_unit_id=%s start_date=%s end_date=%s elapsed_ms=%.2f",
            property_id,
            room_unit.room_type_id,
            payload.room_unit_id,
            payload.start_date,
            payload.end_date,
            (time.perf_counter() - started_at) * 1000,
        )
        return block

    def release_room_block(self, property_id: UUID, block_id: UUID) -> StayRoomBlock:
        started_at = time.perf_counter()
        block = (
            self.db.query(StayRoomBlock)
            .filter(StayRoomBlock.id == block_id, StayRoomBlock.property_id == property_id)
            .first()
        )
        if block is None:
            raise ValueError("Room block not found")
        block.status = StayRoomBlockStatus.RELEASED
        room_unit = self._require_room_unit(property_id, block.room_unit_id)
        self.refresh_calendar(property_id, {room_unit.room_type_id}, block.start_date, block.end_date - timedelta(days=1))
        self.db.commit()
        self.db.refresh(block)
        logger.info(
            "stay_inventory.release_room_block_timing property_id=%s room_type_id=%s block_id=%s start_date=%s end_date=%s elapsed_ms=%.2f",
            property_id,
            room_unit.room_type_id,
            block_id,
            block.start_date,
            block.end_date,
            (time.perf_counter() - started_at) * 1000,
        )
        return block

    def get_calendar(
        self,
        property_id: UUID,
        start_date: date,
        end_date: date,
        room_type_id: UUID | None = None,
    ) -> StayCalendarResponse:
        started_at = time.perf_counter()
        property_record = self._require_property(property_id)
        room_type_ids = {room_type.id for room_type in property_record.room_types or []}
        if room_type_id is not None:
            self._require_room_type(property_id, room_type_id)
            room_type_ids = {room_type_id}
        if not room_type_ids:
            return StayCalendarResponse(propertyId=property_id, entries=[])

        entries_by_type = self._load_calendar_entries(property_id, room_type_ids, start_date, end_date)
        missing_spans = self._find_missing_calendar_spans(room_type_ids, start_date, end_date, entries_by_type)
        for missing_room_type_id, spans in missing_spans.items():
            for span_start, span_end in spans:
                self.refresh_calendar(property_id, {missing_room_type_id}, span_start, span_end)

        if missing_spans:
            entries_by_type = self._load_calendar_entries(property_id, room_type_ids, start_date, end_date)

        entries = [
            StayAvailabilityNightResponse(
                date=entry.stay_date,
                totalUnits=entry.total_units,
                bookedUnits=entry.booked_units,
                blockedUnits=entry.blocked_units,
                availableUnits=entry.available_units,
                nightlyPrice=None,
            )
            for room_entries in entries_by_type.values()
            for entry in room_entries
        ]
        logger.info(
            "stay_inventory.get_calendar_timing property_id=%s room_type_count=%s start_date=%s end_date=%s missing_span_count=%s result_count=%s elapsed_ms=%.2f",
            property_id,
            len(room_type_ids),
            start_date,
            end_date,
            sum(len(spans) for spans in missing_spans.values()),
            len(entries),
            (time.perf_counter() - started_at) * 1000,
        )
        return StayCalendarResponse(propertyId=property_id, entries=entries)

    def search_availability(self, payload: StayAvailabilitySearchRequest) -> StayAvailabilitySearchResponse:
        property_record = self._require_property(payload.property_id)
        room_types = sorted(property_record.room_types or [], key=lambda item: item.name.lower())
        if payload.room_type_id is not None:
            room_types = [room_type for room_type in room_types if room_type.id == payload.room_type_id]

        room_type_ids = {room_type.id for room_type in room_types}
        if room_type_ids:
            self.refresh_calendar(payload.property_id, room_type_ids, payload.check_in_date, payload.check_out_date - timedelta(days=1))

        grouped_entries: dict[UUID, list[StayRoomTypeCalendar]] = defaultdict(list)
        if room_type_ids:
            calendar_entries = (
                self.db.query(StayRoomTypeCalendar)
                .filter(
                    StayRoomTypeCalendar.property_id == payload.property_id,
                    StayRoomTypeCalendar.room_type_id.in_(list(room_type_ids)),
                    StayRoomTypeCalendar.stay_date >= payload.check_in_date,
                    StayRoomTypeCalendar.stay_date < payload.check_out_date,
                )
                .order_by(StayRoomTypeCalendar.stay_date.asc())
                .all()
            )
            for entry in calendar_entries:
                grouped_entries[entry.room_type_id].append(entry)

        results: list[StayAvailabilityRoomTypeResponse] = []
        nights = (payload.check_out_date - payload.check_in_date).days
        for room_type in room_types:
            max_guests = self._safe_int(room_type.max_guests)
            if max_guests is not None and payload.guests > max_guests:
                continue

            nightly_rate = Decimal(room_type.base_price or 0)
            room_entries = grouped_entries.get(room_type.id, [])
            if len(room_entries) != nights:
                continue
            available_count = min(entry.available_units for entry in room_entries) if room_entries else 0
            nightly_prices = [
                StayAvailabilityNightResponse(
                    date=entry.stay_date,
                    totalUnits=entry.total_units,
                    bookedUnits=entry.booked_units,
                    blockedUnits=entry.blocked_units,
                    availableUnits=entry.available_units,
                    nightlyPrice=nightly_rate,
                )
                for entry in room_entries
            ]
            total_price = nightly_rate * nights
            results.append(
                StayAvailabilityRoomTypeResponse(
                    roomTypeId=room_type.id,
                    roomTypeName=room_type.name,
                    availableCount=available_count,
                    nightlyPrices=nightly_prices,
                    totalPrice=total_price,
                    cancellationInfo=(property_record.policies or {}).get("ratePlans"),
                    maxGuests=max_guests,
                )
            )

        return StayAvailabilitySearchResponse(
            propertyId=payload.property_id,
            checkInDate=payload.check_in_date,
            checkOutDate=payload.check_out_date,
            roomTypes=results,
        )

    def create_booking(self, payload: StayBookingCreate, *, confirm: bool = False) -> StayBooking:
        property_record = self._require_property(payload.property_id)
        if payload.check_out_date <= payload.check_in_date:
            raise ValueError("check-out date must be after check-in date")

        user = self.db.get(User, payload.user_id)
        if user is None:
            raise ValueError("Booking user not found")

        room_type_map = {room_type.id: room_type for room_type in property_record.room_types or []}
        requested_room_type_ids = {item.room_type_id for item in payload.items}
        missing_room_type_ids = requested_room_type_ids - set(room_type_map.keys())
        if missing_room_type_ids:
            raise ValueError("One or more requested room types do not belong to the property")

        nights = (payload.check_out_date - payload.check_in_date).days
        if nights <= 0:
            raise ValueError("Booking must include at least one night")

        self.refresh_calendar(payload.property_id, requested_room_type_ids, payload.check_in_date, payload.check_out_date - timedelta(days=1))

        booking_reference = self._generate_booking_reference()
        booking_status = BookingStatus.CONFIRMED if confirm else BookingStatus.PENDING
        stay_status = StayBookingStatus.CONFIRMED if confirm else StayBookingStatus.PENDING
        total_amount = Decimal("0")
        booking = Booking(
            booking_reference=booking_reference,
            user_id=user.id,
            status=booking_status,
            total_amount=Decimal("0"),
            currency=CurrencyCode.LKR,
            payment_status=PaymentTransactionStatus.PENDING,
            booked_at=datetime.utcnow(),
        )
        self.db.add(booking)
        self.db.flush()

        stay_booking = StayBooking(
            booking_id=booking.id,
            property_id=payload.property_id,
            status=stay_status,
            check_in_date=payload.check_in_date,
            check_out_date=payload.check_out_date,
            guest_name=payload.guest_name,
            guest_email=payload.guest_email,
            guest_phone=payload.guest_phone,
            special_requests=payload.special_requests,
            metadata_json={},
        )
        self.db.add(stay_booking)
        self.db.flush()

        for item in payload.items:
            room_type = room_type_map[item.room_type_id]
            max_guests = self._safe_int(room_type.max_guests)
            if max_guests is not None and item.guests > max_guests:
                raise ValueError(f"Requested guests exceed max guests for room type {room_type.name}")

            nightly_rate = Decimal(room_type.base_price or 0)
            selected_units = self._allocate_room_units(
                property_id=payload.property_id,
                room_type_id=item.room_type_id,
                requested_count=item.room_count,
                check_in_date=payload.check_in_date,
                check_out_date=payload.check_out_date,
            )

            line_total = nightly_rate * nights * item.room_count
            total_amount += line_total

            booking_item = self._build_booking_item(
                booking=booking,
                property_record=property_record,
                room_type=room_type,
                quantity=item.room_count,
                travel_date=payload.check_in_date,
                unit_price=float(nightly_rate),
                total_price=float(line_total),
            )
            if booking_item is not None:
                self.db.add(booking_item)

            for room_unit in selected_units:
                self.db.add(
                    StayBookingRoom(
                        stay_booking_id=stay_booking.id,
                        room_unit_id=room_unit.id,
                        room_type_id=room_type.id,
                        check_in_date=payload.check_in_date,
                        check_out_date=payload.check_out_date,
                        nightly_rate=nightly_rate,
                        guests=item.guests,
                        metadata_json={"travelers": item.travelers},
                    )
                )

        booking.total_amount = total_amount
        self.refresh_calendar(payload.property_id, requested_room_type_ids, payload.check_in_date, payload.check_out_date - timedelta(days=1))
        self.db.commit()
        return self.get_booking(stay_booking.id)

    def list_property_bookings(self, property_id: UUID) -> StayBookingListResponse:
        self._require_property(property_id)
        bookings = (
            self.db.query(StayBooking)
            .options(joinedload(StayBooking.rooms))
            .filter(StayBooking.property_id == property_id)
            .order_by(StayBooking.created_at.desc())
            .all()
        )
        return StayBookingListResponse(
            bookings=[StayBookingResponse.model_validate(booking) for booking in bookings],
            total=len(bookings),
        )

    def list_property_blocks(
        self,
        property_id: UUID,
        *,
        room_type_id: UUID | None = None,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> StayRoomBlockListResponse:
        self._require_property(property_id)
        query = (
            self.db.query(StayRoomBlock)
            .join(StayRoomUnit, StayRoomBlock.room_unit_id == StayRoomUnit.id)
            .filter(
                StayRoomBlock.property_id == property_id,
                StayRoomBlock.status == StayRoomBlockStatus.ACTIVE,
            )
        )

        if room_type_id is not None:
            self._require_room_type(property_id, room_type_id)
            query = query.filter(StayRoomUnit.room_type_id == room_type_id)

        if start_date is not None:
            query = query.filter(StayRoomBlock.end_date > start_date)

        if end_date is not None:
            query = query.filter(StayRoomBlock.start_date < end_date)

        blocks = (
            query.order_by(StayRoomBlock.start_date.asc(), StayRoomBlock.created_at.desc())
            .all()
        )
        return StayRoomBlockListResponse(
            blocks=[StayRoomBlockResponse.model_validate(block) for block in blocks],
            total=len(blocks),
        )

    def get_booking(self, stay_booking_id: UUID) -> StayBooking:
        booking = (
            self.db.query(StayBooking)
            .options(joinedload(StayBooking.rooms))
            .filter(StayBooking.id == stay_booking_id)
            .first()
        )
        if booking is None:
            raise ValueError("Stay booking not found")
        return booking

    def refresh_calendar(
        self,
        property_id: UUID,
        room_type_ids: set[UUID],
        start_date: date,
        end_date: date,
    ) -> None:
        if not room_type_ids or end_date < start_date:
            return
        started_at = time.perf_counter()
        room_type_id_list = list(room_type_ids)
        nights = self._night_dates(start_date, end_date + timedelta(days=1))

        total_units_by_type = {room_type_id: 0 for room_type_id in room_type_id_list}
        for room_type_id, total_units in (
            self.db.query(StayRoomUnit.room_type_id, func.count(StayRoomUnit.id))
            .filter(
                StayRoomUnit.property_id == property_id,
                StayRoomUnit.room_type_id.in_(room_type_id_list),
            )
            .group_by(StayRoomUnit.room_type_id)
            .all()
        ):
            total_units_by_type[room_type_id] = total_units or 0

        existing_entries = (
            self.db.query(StayRoomTypeCalendar)
            .filter(
                StayRoomTypeCalendar.property_id == property_id,
                StayRoomTypeCalendar.room_type_id.in_(room_type_id_list),
                StayRoomTypeCalendar.stay_date >= start_date,
                StayRoomTypeCalendar.stay_date <= end_date,
            )
            .all()
        )
        existing_entries_by_key = {
            (entry.room_type_id, entry.stay_date): entry
            for entry in existing_entries
        }

        booked_counts: dict[tuple[UUID, date], int] = defaultdict(int)
        booking_rows = (
            self.db.query(
                StayBookingRoom.room_type_id,
                StayBookingRoom.check_in_date,
                StayBookingRoom.check_out_date,
            )
            .join(StayBooking, StayBookingRoom.stay_booking_id == StayBooking.id)
            .join(Booking, StayBooking.booking_id == Booking.id)
            .filter(
                StayBooking.property_id == property_id,
                StayBookingRoom.room_type_id.in_(room_type_id_list),
                StayBookingRoom.check_in_date <= end_date,
                StayBookingRoom.check_out_date > start_date,
                StayBooking.status != StayBookingStatus.CANCELLED,
                Booking.status.in_(list(ACTIVE_PARENT_BOOKING_STATUSES)),
            )
            .all()
        )
        for room_type_id, check_in_date, check_out_date in booking_rows:
            overlap_start = max(start_date, check_in_date)
            overlap_end = min(end_date + timedelta(days=1), check_out_date)
            for night in self._night_dates(overlap_start, overlap_end):
                booked_counts[(room_type_id, night)] += 1

        blocked_units_by_day: dict[tuple[UUID, date], set[UUID]] = defaultdict(set)
        block_rows = (
            self.db.query(
                StayRoomUnit.room_type_id,
                StayRoomBlock.room_unit_id,
                StayRoomBlock.start_date,
                StayRoomBlock.end_date,
            )
            .join(StayRoomUnit, StayRoomBlock.room_unit_id == StayRoomUnit.id)
            .filter(
                StayRoomBlock.property_id == property_id,
                StayRoomUnit.room_type_id.in_(room_type_id_list),
                StayRoomBlock.status == StayRoomBlockStatus.ACTIVE,
                StayRoomBlock.start_date <= end_date,
                StayRoomBlock.end_date > start_date,
            )
            .all()
        )
        for room_type_id, room_unit_id, block_start_date, block_end_date in block_rows:
            overlap_start = max(start_date, block_start_date)
            overlap_end = min(end_date + timedelta(days=1), block_end_date)
            for night in self._night_dates(overlap_start, overlap_end):
                blocked_units_by_day[(room_type_id, night)].add(room_unit_id)

        touched_entry_count = 0
        for room_type_id in room_type_id_list:
            total_units = total_units_by_type.get(room_type_id, 0)
            for night in nights:
                entry = existing_entries_by_key.get((room_type_id, night))
                if entry is None:
                    entry = StayRoomTypeCalendar(
                        property_id=property_id,
                        room_type_id=room_type_id,
                        stay_date=night,
                    )
                    self.db.add(entry)
                    existing_entries_by_key[(room_type_id, night)] = entry

                booked_units = booked_counts.get((room_type_id, night), 0)
                blocked_units = len(blocked_units_by_day.get((room_type_id, night), set()))
                entry.total_units = total_units
                entry.booked_units = booked_units
                entry.blocked_units = blocked_units
                entry.available_units = max(total_units - booked_units - blocked_units, 0)
                touched_entry_count += 1
        self.db.flush()
        logger.info(
            "stay_inventory.refresh_calendar_timing property_id=%s room_type_count=%s start_date=%s end_date=%s booking_row_count=%s block_row_count=%s touched_entry_count=%s elapsed_ms=%.2f",
            property_id,
            len(room_type_id_list),
            start_date,
            end_date,
            len(booking_rows),
            len(block_rows),
            touched_entry_count,
            (time.perf_counter() - started_at) * 1000,
        )

    def _allocate_room_units(
        self,
        property_id: UUID,
        room_type_id: UUID,
        requested_count: int,
        check_in_date: date,
        check_out_date: date,
    ) -> list[StayRoomUnit]:
        query = (
            self.db.query(StayRoomUnit)
            .filter(
                StayRoomUnit.property_id == property_id,
                StayRoomUnit.room_type_id == room_type_id,
            )
            .order_by(StayRoomUnit.room_number.asc())
        )
        try:
            query = query.with_for_update()
        except Exception:
            pass
        room_units = query.all()

        available_units = [
            room_unit
            for room_unit in room_units
            if room_unit.status.lower() not in INACTIVE_UNIT_STATUSES
            and not self._room_unit_has_overlap(room_unit.id, check_in_date, check_out_date)
        ]
        if len(available_units) < requested_count:
            raise ValueError("Insufficient room availability for the requested stay")
        return available_units[:requested_count]

    def _room_unit_has_overlap(self, room_unit_id: UUID, check_in_date: date, check_out_date: date) -> bool:
        has_booking_overlap = (
            self.db.query(StayBookingRoom.id)
            .join(StayBooking, StayBookingRoom.stay_booking_id == StayBooking.id)
            .join(Booking, StayBooking.booking_id == Booking.id)
            .filter(
                StayBookingRoom.room_unit_id == room_unit_id,
                StayBookingRoom.check_in_date < check_out_date,
                StayBookingRoom.check_out_date > check_in_date,
                StayBooking.status != StayBookingStatus.CANCELLED,
                Booking.status.in_(list(ACTIVE_PARENT_BOOKING_STATUSES)),
            )
            .first()
            is not None
        )
        if has_booking_overlap:
            return True

        return (
            self.db.query(StayRoomBlock.id)
            .filter(
                StayRoomBlock.room_unit_id == room_unit_id,
                StayRoomBlock.status == StayRoomBlockStatus.ACTIVE,
                StayRoomBlock.start_date < check_out_date,
                StayRoomBlock.end_date > check_in_date,
            )
            .first()
            is not None
        )

    def _booked_unit_count(self, property_id: UUID, room_type_id: UUID, stay_date: date) -> int:
        return (
            self.db.query(func.count(StayBookingRoom.id))
            .join(StayBooking, StayBookingRoom.stay_booking_id == StayBooking.id)
            .join(Booking, StayBooking.booking_id == Booking.id)
            .filter(
                StayBooking.property_id == property_id,
                StayBookingRoom.room_type_id == room_type_id,
                StayBookingRoom.check_in_date <= stay_date,
                StayBookingRoom.check_out_date > stay_date,
                StayBooking.status != StayBookingStatus.CANCELLED,
                Booking.status.in_(list(ACTIVE_PARENT_BOOKING_STATUSES)),
            )
            .scalar()
            or 0
        )

    def _blocked_unit_count(self, property_id: UUID, room_type_id: UUID, stay_date: date) -> int:
        return (
            self.db.query(func.count(func.distinct(StayRoomBlock.room_unit_id)))
            .join(StayRoomUnit, StayRoomBlock.room_unit_id == StayRoomUnit.id)
            .filter(
                StayRoomBlock.property_id == property_id,
                StayRoomUnit.room_type_id == room_type_id,
                StayRoomBlock.status == StayRoomBlockStatus.ACTIVE,
                StayRoomBlock.start_date <= stay_date,
                StayRoomBlock.end_date > stay_date,
            )
            .scalar()
            or 0
        )

    def _build_booking_item(
        self,
        booking: Booking,
        property_record: StayProperty,
        room_type: StayRoomType,
        quantity: int,
        travel_date: date,
        unit_price: float,
        total_price: float,
    ) -> BookingItem | None:
        if property_record.listing_id is None:
            return None
        variant = (
            self.db.query(ListingVariant)
            .filter(ListingVariant.listing_id == property_record.listing_id, ListingVariant.name == room_type.name)
            .first()
        )
        if variant is None:
            variant = (
                self.db.query(ListingVariant)
                .filter(ListingVariant.listing_id == property_record.listing_id)
                .order_by(ListingVariant.created_at.asc())
                .first()
            )
        if variant is None:
            return None
        return BookingItem(
            booking_id=booking.id,
            listing_id=property_record.listing_id,
            variant_id=variant.id,
            travel_date=travel_date,
            quantity=quantity,
            unit_price=unit_price,
            total_price=total_price,
        )

    @staticmethod
    def _night_dates(check_in_date: date, check_out_date: date) -> list[date]:
        nights: list[date] = []
        current = check_in_date
        while current < check_out_date:
            nights.append(current)
            current += timedelta(days=1)
        return nights

    @staticmethod
    def _safe_int(value) -> int | None:
        if value in (None, ""):
            return None
        return int(value)

    @staticmethod
    def _generate_booking_reference() -> str:
        return f"STAY-{uuid4().hex[:10].upper()}"

    @staticmethod
    def _room_type_payload(room_type: StayRoomType) -> dict:
        return {
            "id": room_type.id,
            "name": room_type.name,
            "description": room_type.description,
            "size": room_type.size,
            "sizeUnit": room_type.size_unit,
            "maxGuests": room_type.max_guests,
            "basePrice": room_type.base_price,
            "currency": room_type.currency,
            "bedConfiguration": room_type.bed_configuration,
            "bathroom": room_type.bathroom,
            "discounts": room_type.discounts,
            "roomUnits": [StayRoomUnitResponse.model_validate(room).model_dump(by_alias=True) for room in room_type.room_units or []],
        }

    def _load_calendar_entries(
        self,
        property_id: UUID,
        room_type_ids: set[UUID],
        start_date: date,
        end_date: date,
    ) -> dict[UUID, list[StayRoomTypeCalendar]]:
        grouped_entries: dict[UUID, list[StayRoomTypeCalendar]] = defaultdict(list)
        entries = (
            self.db.query(StayRoomTypeCalendar)
            .filter(
                StayRoomTypeCalendar.property_id == property_id,
                StayRoomTypeCalendar.room_type_id.in_(list(room_type_ids)),
                StayRoomTypeCalendar.stay_date >= start_date,
                StayRoomTypeCalendar.stay_date <= end_date,
            )
            .order_by(StayRoomTypeCalendar.room_type_id.asc(), StayRoomTypeCalendar.stay_date.asc())
            .all()
        )
        for entry in entries:
            grouped_entries[entry.room_type_id].append(entry)
        return grouped_entries

    def _find_missing_calendar_spans(
        self,
        room_type_ids: set[UUID],
        start_date: date,
        end_date: date,
        entries_by_type: dict[UUID, list[StayRoomTypeCalendar]],
    ) -> dict[UUID, list[tuple[date, date]]]:
        expected_dates = self._night_dates(start_date, end_date + timedelta(days=1))
        missing_spans: dict[UUID, list[tuple[date, date]]] = {}

        for room_type_id in room_type_ids:
            existing_dates = {entry.stay_date for entry in entries_by_type.get(room_type_id, [])}
            span_start: date | None = None
            spans: list[tuple[date, date]] = []

            for night in expected_dates:
                if night not in existing_dates:
                    if span_start is None:
                        span_start = night
                    continue

                if span_start is not None:
                    spans.append((span_start, night - timedelta(days=1)))
                    span_start = None

            if span_start is not None:
                spans.append((span_start, expected_dates[-1]))

            if spans:
                missing_spans[room_type_id] = spans

        return missing_spans

    def _require_property(self, property_id: UUID) -> StayProperty:
        property_record = self.get_property(property_id)
        if property_record is None:
            raise ValueError("Stay property not found")
        return property_record

    def _require_room_type(self, property_id: UUID, room_type_id: UUID) -> StayRoomType:
        room_type = (
            self.db.query(StayRoomType)
            .options(joinedload(StayRoomType.room_units), joinedload(StayRoomType.booking_rooms))
            .filter(StayRoomType.id == room_type_id, StayRoomType.property_id == property_id)
            .first()
        )
        if room_type is None:
            raise ValueError("Room type not found")
        return room_type

    def _require_room_unit(self, property_id: UUID, room_unit_id: UUID) -> StayRoomUnit:
        room_unit = (
            self.db.query(StayRoomUnit)
            .options(joinedload(StayRoomUnit.booking_rooms))
            .filter(StayRoomUnit.id == room_unit_id, StayRoomUnit.property_id == property_id)
            .first()
        )
        if room_unit is None:
            raise ValueError("Room unit not found")
        return room_unit
