from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Optional, List, Tuple
from uuid import UUID, uuid4

from fastapi import HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from app.core.logging import logger
from app.integrations.email_provider import email_provider
from app.models.booking import Booking
from app.models.bookingItem import BookingItem
from app.models.bookingTraveler import BookingTraveler
from app.models.enum import (
    BookingStatus,
    CurrencyCode,
    PaymentMethod,
    PaymentTransactionStatus,
    ListingType,
)
from app.models.listing import Listing
from app.models.listingBlock import ListingBlock
from app.models.listingVariant import ListingVariant
from app.models.availabilityCalendar import AvailabilityCalendar
from app.models.stay import (
    StayBooking,
    StayBookingRoom,
    StayProperty,
    StayRoomType,
    StayRoomTypeCalendar,
    StayRoomUnit,
)
from app.schemas.booking_schema import (
    BookingCreate,
    BookingReceiptCreate,
    BookingResponse,
    ListingAvailabilityResponse,
    NightlyAvailability,
)


class BookingService:
    """Service class encapsulating business logic for booking, availability, and payment reconciliation."""

    def __init__(self, db: Session):
        self.db = db

    def _generate_booking_reference(self, listing_type: ListingType) -> str:
        base = uuid4().hex[:8].upper()
        if listing_type == ListingType.STAY:
            return f"BK-STY-{base}"
        elif listing_type == ListingType.SAFARI:
            return f"BK-SAF-{base}"
        elif listing_type == ListingType.ACTIVITY:
            return f"BK-EXP-{base}"
        return f"TC-BKG-{base}"

    def get_listing_availability(
        self, listing_id: UUID, start_date: date, end_date: date
    ) -> ListingAvailabilityResponse:
        """Query real-time per-night availability for a listing between start_date and end_date."""
        if end_date <= start_date:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="end_date must be after start_date",
            )

        listing = self.db.query(Listing).filter(Listing.id == listing_id).first()
        if not listing:
            raise HTTPException(status_code=404, detail="Listing not found")

        nights_list: List[NightlyAvailability] = []

        if listing.listing_type == ListingType.STAY:
            from app.services.stay_inventory_service import StayInventoryService
            inv_service = StayInventoryService(self.db)
            property_record = inv_service.get_property(listing_id)
            if property_record:
                room_type_ids = {rt.id for rt in (property_record.room_types or [])}
                if room_type_ids:
                    inv_service.refresh_calendar(property_record.id, room_type_ids, start_date, end_date - timedelta(days=1))

            current = start_date
            while current < end_date:
                if property_record:
                    # Query aggregate calendar entry across property room types for date
                    calendar_entries = (
                        self.db.query(StayRoomTypeCalendar)
                        .filter(
                            StayRoomTypeCalendar.property_id == property_record.id,
                            StayRoomTypeCalendar.stay_date == current,
                        )
                        .all()
                    )
                    if calendar_entries:
                        total = sum(e.total_units for e in calendar_entries)
                        booked = sum(e.booked_units for e in calendar_entries)
                        blocked = sum(e.blocked_units for e in calendar_entries)
                        avail = max(sum(e.available_units for e in calendar_entries), 0)
                    else:
                        total, booked, blocked, avail = 1, 0, 0, 1
                else:
                    total, booked, blocked, avail = 1, 0, 0, 1

                day_status = "OPEN" if avail > 0 else "SOLD_OUT"
                nights_list.append(
                    NightlyAvailability(
                        date=current,
                        available_units=avail,
                        total_units=total,
                        booked_units=booked,
                        blocked_units=blocked,
                        price=None,
                        status=day_status,
                    )
                )
                current += timedelta(days=1)
        else:
            variants = self.db.query(ListingVariant).filter(ListingVariant.listing_id == listing_id).all()
            blocks = self.db.query(ListingBlock).filter(
                ListingBlock.listing_id == listing_id,
                ListingBlock.start_date <= end_date,
                ListingBlock.end_date >= start_date
            ).all()

            current = start_date
            while current < end_date:
                is_blocked = any(b.start_date <= current <= b.end_date for b in blocks if not b.variant_id)
                if is_blocked:
                    total, booked, blocked, avail = 0, 0, 1, 0
                else:
                    total, booked, blocked, avail = 0, 0, 0, 0
                    for variant in variants:
                        v_is_blocked = any(b.start_date <= current <= b.end_date for b in blocks if b.variant_id == variant.id)
                        if v_is_blocked:
                            blocked += (variant.capacity_max or 1)
                            total += (variant.capacity_max or 1)
                            continue

                        avail_cal = self.db.query(AvailabilityCalendar).filter(
                            AvailabilityCalendar.variant_id == variant.id,
                            func.date(AvailabilityCalendar.service_date) == current
                        ).first()

                        if avail_cal:
                            total += avail_cal.total_capacity
                            booked += avail_cal.reserved_capacity
                            avail += avail_cal.available_capacity
                        else:
                            total += (variant.capacity_max or 1)
                            avail += (variant.capacity_max or 1)

                day_status = "OPEN" if avail > 0 else "SOLD_OUT"
                nights_list.append(
                    NightlyAvailability(
                        date=current,
                        available_units=avail,
                        total_units=total,
                        booked_units=booked,
                        blocked_units=blocked,
                        price=None,
                        status=day_status,
                    )
                )
                current += timedelta(days=1)

        return ListingAvailabilityResponse(
            listing_id=listing_id,
            start_date=start_date,
            end_date=end_date,
            nights=nights_list,
        )

    def create_booking(self, payload: BookingCreate) -> Booking:
        """
        Create a new booking with per-night availability locking and dual payment handling.
        """
        # Reject ONLINE payment method (reserved for future gateway)
        if payload.payment_method == PaymentMethod.ONLINE:
            raise HTTPException(
                status_code=status.HTTP_501_NOT_IMPLEMENTED,
                detail="Online payment gateway is not configured yet. Please choose PAY_AT_PROPERTY or BANK_TRANSFER.",
            )

        if not payload.booking_items:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Booking must contain at least one item.",
            )

        first_item = payload.booking_items[0]
        check_in = payload.check_in_date or first_item.travel_date
        check_out = payload.check_out_date or (check_in + timedelta(days=1))
        if check_out <= check_in:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Check-out date must be after check-in date.",
            )

        listing = self.db.query(Listing).filter(Listing.id == first_item.listing_id).first()
        if not listing:
            raise HTTPException(status_code=404, detail="Listing not found")

        ref = self._generate_booking_reference(listing.listing_type)

        if payload.payment_method == PaymentMethod.PAY_AT_PROPERTY:
            booking_status = BookingStatus.CONFIRMED
            payment_status = PaymentTransactionStatus.PENDING
        else:  # BANK_TRANSFER
            booking_status = BookingStatus.PENDING
            payment_status = PaymentTransactionStatus.PENDING

        total_amount = Decimal("0")
        for item in payload.booking_items:
            total_amount += Decimal(str(item.total_price))

        booking = Booking(
            booking_reference=ref,
            user_id=payload.user_id,
            status=booking_status,
            total_amount=total_amount,
            currency=CurrencyCode.USD,
            payment_method=payload.payment_method,
            payment_status=payment_status,
            booked_at=datetime.utcnow(),
        )
        self.db.add(booking)
        self.db.flush()

        for item_data in payload.booking_items:
            item_dict = item_data.model_dump()
            travelers_data = item_dict.pop("travelers", [])
            booking_item = BookingItem(booking_id=booking.id, **item_dict)
            self.db.add(booking_item)
            self.db.flush()

            for traveler_data in travelers_data:
                traveler = BookingTraveler(booking_item_id=booking_item.id, **traveler_data)
                self.db.add(traveler)
                
        check_in = payload.check_in_date or first_item.travel_date
        check_out = payload.check_out_date or (check_in + timedelta(days=1))

        if listing.listing_type == ListingType.STAY:
            self._process_stay_booking(booking, payload, first_item, check_in, check_out)
        else:
            self._process_variant_booking(booking, payload, listing, check_in, check_out)

        self.db.commit()

        # 5. Trigger Email Notifications asynchronously/background
        booking_data = {
            "booking_reference": ref,
            "guest_name": payload.guest_name or "Valued Guest",
            "guest_email": payload.guest_email,
            "guest_phone": payload.guest_phone,
            "special_requests": payload.special_requests,
            "total_amount": float(total_amount),
            "currency": "USD",
            "payment_method": payload.payment_method.value,
            "status": booking_status.value,
        }

        try:
            if payload.payment_method == PaymentMethod.PAY_AT_PROPERTY:
                email_provider.send_booking_confirmation_pay_at_property(booking_data)
            else:
                email_provider.send_booking_bank_transfer_instructions(booking_data)
            email_provider.send_vendor_new_booking_alert(booking_data)
        except Exception as e:
            logger.error("Error dispatching booking notification emails: %s", str(e))

        return self.get_booking_by_id(booking.id)


    def _process_stay_booking(self, booking, payload, first_item, check_in, check_out):
        property_record = (
            self.db.query(StayProperty)
            .filter(StayProperty.listing_id == first_item.listing_id)
            .first()
        )
        if not property_record:
            return

        from app.services.stay_inventory_service import StayInventoryService
        inv_service = StayInventoryService(self.db)

        night_dates = []
        curr = check_in
        while curr < check_out:
            night_dates.append(curr)
            curr += timedelta(days=1)
        night_dates.sort()

        if property_record.room_types:
            room_type = property_record.room_types[0]
            for night_date in night_dates:
                calendar_row = (
                    self.db.query(StayRoomTypeCalendar)
                    .filter(
                        StayRoomTypeCalendar.property_id == property_record.id,
                        StayRoomTypeCalendar.room_type_id == room_type.id,
                        StayRoomTypeCalendar.stay_date == night_date,
                    )
                    .with_for_update()
                    .first()
                )
                if not calendar_row:
                    total_units = len(room_type.room_units or []) or 1
                    calendar_row = StayRoomTypeCalendar(
                        property_id=property_record.id,
                        room_type_id=room_type.id,
                        stay_date=night_date,
                        total_units=total_units,
                        booked_units=0,
                        blocked_units=0,
                        available_units=total_units,
                    )
                    self.db.add(calendar_row)
                    self.db.flush()

                if calendar_row.available_units < first_item.quantity:
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail=f"Selected dates are unavailable (sold out on {night_date}).",
                    )

                calendar_row.available_units -= first_item.quantity
                calendar_row.booked_units += first_item.quantity

        stay_booking = StayBooking(
            booking_id=booking.id,
            property_id=property_record.id,
            status=booking.status,
            check_in_date=check_in,
            check_out_date=check_out,
            guest_name=payload.guest_name or "Guest",
            guest_email=payload.guest_email or "guest@tourceylon.com",
            guest_phone=payload.guest_phone,
            special_requests=payload.special_requests,
            metadata_json={},
        )
        self.db.add(stay_booking)
        self.db.flush()

        if property_record.room_types:
            rooms_to_book = []
            selected_rooms = first_item.selected_rooms or []
            if selected_rooms:
                for sr in selected_rooms:
                    qty = int(sr.get("qty") or 1)
                    r_id = sr.get("roomId")
                    rt = None
                    if r_id:
                        try:
                            rt = self.db.query(StayRoomType).filter(
                                StayRoomType.property_id == property_record.id,
                                (StayRoomType.id == UUID(r_id)) | (StayRoomType.metadata_json['sourceVariantId'].astext == r_id)
                            ).first()
                        except ValueError:
                            pass
                    if not rt:
                        r_name = sr.get("roomName")
                        if r_name:
                            rt = self.db.query(StayRoomType).filter(
                                StayRoomType.property_id == property_record.id,
                                StayRoomType.name.ilike(f"%{r_name.strip()}%")
                            ).first()
                    if not rt:
                        rt = property_record.room_types[0]
                    if rt:
                        rooms_to_book.append({"room_type": rt, "qty": qty})
            else:
                rt = None
                if first_item.variant_id:
                    try:
                        rt = self.db.query(StayRoomType).filter(
                            StayRoomType.property_id == property_record.id,
                            (StayRoomType.id == first_item.variant_id) | (StayRoomType.metadata_json['sourceVariantId'].astext == str(first_item.variant_id))
                        ).first()
                    except ValueError:
                        pass
                if not rt:
                    rt = property_record.room_types[0]
                rooms_to_book.append({"room_type": rt, "qty": first_item.quantity})

            total_qty = sum(rb["qty"] for rb in rooms_to_book)
            per_unit_rate = Decimal(str(first_item.unit_price)) / Decimal(str(max(1, total_qty))) if total_qty > 0 else Decimal(0)
            if not first_item.unit_price:
                per_unit_rate = None

            for rb in rooms_to_book:
                target_room_type = rb["room_type"]
                try:
                    allocated_units = inv_service._allocate_room_units(
                        property_id=property_record.id,
                        room_type_id=target_room_type.id,
                        requested_count=rb["qty"],
                        check_in_date=check_in,
                        check_out_date=check_out,
                    )
                    nightly_rate = per_unit_rate if per_unit_rate is not None else Decimal(str(target_room_type.base_price or 0))
                    for unit in allocated_units:
                        stay_booking_room = StayBookingRoom(
                            stay_booking_id=stay_booking.id,
                            room_unit_id=unit.id,
                            room_type_id=target_room_type.id,
                            check_in_date=check_in,
                            check_out_date=check_out,
                            nightly_rate=nightly_rate,
                            guests=1,
                            metadata_json={},
                        )
                        self.db.add(stay_booking_room)
                    self.db.flush()
                except Exception as alloc_err:
                    from app.core.logging import logger
                    logger.warning(f"Could not auto-allocate physical room units for booking: {alloc_err}")

        try:
            room_type_ids = {rt.id for rt in (property_record.room_types or [])}
            if room_type_ids:
                inv_service.refresh_calendar(property_record.id, room_type_ids, check_in, check_out - timedelta(days=1))
        except Exception as cal_err:
            from app.core.logging import logger
            logger.warning(f"Could not refresh calendar after booking creation: {cal_err}")

    def _process_variant_booking(self, booking, payload, listing, check_in, check_out):
        night_dates = []
        curr = check_in
        while curr < check_out:
            night_dates.append(curr)
            curr += timedelta(days=1)
        night_dates.sort()

        for item in payload.booking_items:
            blocks = self.db.query(ListingBlock).filter(
                ListingBlock.listing_id == item.listing_id,
                ListingBlock.start_date <= check_out,
                ListingBlock.end_date >= check_in
            ).all()

            for night_date in night_dates:
                if any(b.start_date <= night_date <= b.end_date for b in blocks if not b.variant_id):
                    raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"Listing is blocked on {night_date}.")

                if item.variant_id:
                    if any(b.start_date <= night_date <= b.end_date for b in blocks if b.variant_id == item.variant_id):
                        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"Selected variant is blocked on {night_date}.")

                    avail_cal = self.db.query(AvailabilityCalendar).filter(
                        AvailabilityCalendar.variant_id == item.variant_id,
                        func.date(AvailabilityCalendar.service_date) == night_date
                    ).with_for_update().first()

                    if not avail_cal:
                        variant = self.db.query(ListingVariant).filter(ListingVariant.id == item.variant_id).first()
                        cap = variant.capacity_max or 1 if variant else 1
                        if cap < item.quantity:
                            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"Insufficient capacity on {night_date}.")
                        avail_cal = AvailabilityCalendar(
                            variant_id=item.variant_id,
                            service_date=night_date,
                            total_capacity=cap,
                            reserved_capacity=item.quantity,
                            available_capacity=cap - item.quantity,
                            available_status="OPEN" if (cap - item.quantity) > 0 else "SOLD_OUT"
                        )
                        self.db.add(avail_cal)
                        self.db.flush()
                    else:
                        if avail_cal.available_capacity < item.quantity:
                            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"Insufficient capacity on {night_date}.")
                        avail_cal.available_capacity -= item.quantity
                        avail_cal.reserved_capacity += item.quantity
                        if avail_cal.available_capacity == 0:
                            avail_cal.available_status = "SOLD_OUT"

    def get_booking_by_id(self, booking_id: UUID) -> Optional[Booking]:
        return (
            self.db.query(Booking)
            .options(joinedload(Booking.booking_items).joinedload(BookingItem.travelers))
            .filter(Booking.id == booking_id)
            .first()
        )

    def mark_as_paid(self, booking_id: UUID) -> Booking:
        """Mark a pending bank transfer booking as PAID / SUCCEEDED with pessimistic locking."""
        booking = (
            self.db.query(Booking)
            .filter(Booking.id == booking_id)
            .with_for_update()
            .first()
        )
        if not booking:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Booking not found")

        if booking.status in (BookingStatus.EXPIRED, BookingStatus.CANCELLED):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot mark {booking.status.value} booking as paid.",
            )

        booking.payment_status = PaymentTransactionStatus.SUCCEEDED
        booking.status = BookingStatus.CONFIRMED

        stay_booking = (
            self.db.query(StayBooking)
            .filter(StayBooking.booking_id == booking.id)
            .first()
        )
        if stay_booking:
            stay_booking.status = BookingStatus.CONFIRMED

        self.db.commit()
        self.db.refresh(booking)
        return booking

    def submit_receipt(self, booking_id: UUID, payload: BookingReceiptCreate) -> Booking:
        """Submit bank transfer receipt reference and alert vendor."""
        booking = self.get_booking_by_id(booking_id)
        if not booking:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Booking not found")

        booking_data = {
            "booking_reference": booking.booking_reference,
            "guest_name": "Customer",
            "guest_email": "customer@tourceylon.com",
            "total_amount": float(booking.total_amount),
            "currency": booking.currency.value,
        }

        try:
            email_provider.send_vendor_receipt_submission_alert(
                booking_data, payload.receipt_reference
            )
        except Exception as e:
            logger.error("Error sending receipt submission alert: %s", str(e))

        return booking

    def release_expired_bank_transfer_holds(self) -> int:
        """Auto-expire bank transfer holds older than 24h and re-increment per-night calendar availability."""
        cutoff_time = datetime.utcnow() - timedelta(hours=24)
        expired_bookings = (
            self.db.query(Booking)
            .filter(
                Booking.payment_method == PaymentMethod.BANK_TRANSFER,
                Booking.status == BookingStatus.PENDING,
                Booking.created_at <= cutoff_time,
            )
            .with_for_update()
            .all()
        )

        released_count = 0
        for booking in expired_bookings:
            booking.status = BookingStatus.EXPIRED
            booking.payment_status = PaymentTransactionStatus.FAILED

            for item in booking.booking_items:
                listing = self.db.query(Listing).filter(Listing.id == item.listing_id).first()
                if not listing: continue

                if listing.listing_type == ListingType.STAY:
                    stay_booking = self.db.query(StayBooking).filter(StayBooking.booking_id == booking.id).first()
                    if stay_booking:
                        curr = stay_booking.check_in_date
                        check_out = stay_booking.check_out_date
                        property_record = self.db.query(StayProperty).filter(StayProperty.listing_id == item.listing_id).first()
                        if property_record and property_record.room_types:
                            room_type = property_record.room_types[0]
                            while curr < check_out:
                                calendar_row = self.db.query(StayRoomTypeCalendar).filter(
                                    StayRoomTypeCalendar.property_id == property_record.id,
                                    StayRoomTypeCalendar.room_type_id == room_type.id,
                                    StayRoomTypeCalendar.stay_date == curr,
                                ).with_for_update().first()
                                if calendar_row:
                                    calendar_row.booked_units = max(0, calendar_row.booked_units - item.quantity)
                                    calendar_row.available_units = min(
                                        calendar_row.total_units,
                                        calendar_row.available_units + item.quantity,
                                    )
                                curr += timedelta(days=1)
                else:
                    if item.variant_id:
                        avail_cal = self.db.query(AvailabilityCalendar).filter(
                            AvailabilityCalendar.variant_id == item.variant_id,
                            func.date(AvailabilityCalendar.service_date) == item.travel_date
                        ).with_for_update().first()
                        if avail_cal:
                            avail_cal.reserved_capacity = max(0, avail_cal.reserved_capacity - item.quantity)
                            avail_cal.available_capacity = min(avail_cal.total_capacity, avail_cal.available_capacity + item.quantity)
                            if avail_cal.available_capacity > 0:
                                avail_cal.available_status = "OPEN"

            released_count += 1

        if released_count > 0:
            self.db.commit()
            logger.info("Released %d expired bank transfer booking holds.", released_count)

        return released_count


def get_booking_service(db: Session) -> BookingService:
    return BookingService(db)
