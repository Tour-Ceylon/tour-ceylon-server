"""Check the property that has active bookings (013b5155...)."""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))

from app.config.database import SessionLocal
from app.models.stay import StayProperty, StayRoomType, StayRoomUnit, StayBooking, StayBookingRoom, StayRoomTypeCalendar
from sqlalchemy.orm import joinedload
from datetime import date

db = SessionLocal()
try:
    # Focus on property with known bookings
    prop = db.query(StayProperty).options(
        joinedload(StayProperty.room_types).joinedload(StayRoomType.room_units)
    ).filter(StayProperty.id == '013b5155-bf0e-4b2a-99e3-bbd95e106573').first()

    if not prop:
        # Fallback: find any property with bookings
        booking = db.query(StayBooking).first()
        if booking:
            prop = db.query(StayProperty).options(
                joinedload(StayProperty.room_types).joinedload(StayRoomType.room_units)
            ).filter(StayProperty.id == booking.property_id).first()

    if not prop:
        print("No property found")
        sys.exit(1)

    print(f"Property: {prop.name} (ID: {prop.id})")
    print(f"  vendor_id: {prop.vendor_id}")
    print(f"  listing_id: {prop.listing_id}")
    print(f"  status: {prop.status}")
    print(f"  metadata: {prop.metadata_json}")

    for rt in (prop.room_types or []):
        units = rt.room_units or []
        print(f"\n  RoomType: {rt.name} (ID: {rt.id})")
        print(f"    base_price: {rt.base_price}, currency: {rt.currency}")
        print(f"    max_guests: {rt.max_guests}")
        print(f"    metadata: {rt.metadata_json}")
        print(f"    Units ({len(units)}):")
        for u in units:
            print(f"      - {u.room_number} (ID: {u.id}, status: {u.status})")
        
        # Check calendar entries for this room type
        cal = db.query(StayRoomTypeCalendar).filter(
            StayRoomTypeCalendar.property_id == prop.id,
            StayRoomTypeCalendar.room_type_id == rt.id,
        ).order_by(StayRoomTypeCalendar.stay_date).all()
        
        booked_dates = [c for c in cal if c.booked_units > 0]
        print(f"    Calendar entries with bookings ({len(booked_dates)}):")
        for c in booked_dates:
            print(f"      {c.stay_date}: total={c.total_units} booked={c.booked_units} avail={c.available_units}")

    # Check all active bookings
    bookings = (
        db.query(StayBooking)
        .options(joinedload(StayBooking.rooms))
        .filter(StayBooking.property_id == prop.id)
        .all()
    )
    print(f"\n  ALL Bookings ({len(bookings)}):")
    for bk in bookings:
        bk_status = getattr(bk.status, 'value', str(bk.status))
        print(f"    Booking ID={bk.id} status={bk_status} {bk.check_in_date} to {bk.check_out_date} guest={bk.guest_name}")
        for r in (bk.rooms or []):
            # Find room type name
            rt_name = "?"
            for rt in (prop.room_types or []):
                if rt.id == r.room_type_id:
                    rt_name = rt.name
                    break
            print(f"      Room: unit={r.room_unit_id} type={rt_name}({r.room_type_id}) {r.check_in_date}-{r.check_out_date}")

finally:
    db.close()
