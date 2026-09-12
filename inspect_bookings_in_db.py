from app.config.database import SessionLocal
from app.models.stay import StayBooking, StayBookingRoom, StayProperty, StayRoomUnit, StayRoomType, StayRoomBlock
from app.models.booking import Booking
from app.models.bookingItem import BookingItem
from app.models.bookingInquiry import BookingInquiry

db = SessionLocal()

print("==================================================")
print("INSPECTING BOOKINGS IN DATABASE")
print("==================================================")

bookings = db.query(Booking).all()
print(f"Total `bookings` count: {len(bookings)}")
for b in bookings:
    print(f"  Booking ID: {b.id} | Ref: {b.booking_reference} | Status: {b.status} | Total: {b.total_amount}")

stay_bookings = db.query(StayBooking).all()
print(f"\nTotal `stay_bookings` count: {len(stay_bookings)}")
for sb in stay_bookings:
    print(f"  StayBooking ID: {sb.id} | Property ID: {sb.property_id} | CheckIn: {sb.check_in_date} | CheckOut: {sb.check_out_date} | Status: {sb.status}")

stay_booking_rooms = db.query(StayBookingRoom).all()
print(f"\nTotal `stay_booking_rooms` count: {len(stay_booking_rooms)}")
for sbr in stay_booking_rooms:
    print(f"  StayBookingRoom ID: {sbr.id} | StayBooking ID: {sbr.stay_booking_id} | RoomType: {sbr.room_type_id} | Unit: {sbr.room_unit_id} | Dates: {sbr.check_in_date} to {sbr.check_out_date}")

inquiries = db.query(BookingInquiry).all()
print(f"\nTotal `booking_inquiries` count: {len(inquiries)}")
for inq in inquiries:
    print(f"  Inquiry ID: {inq.id} | Ref: {inq.reference} | Status: {inq.status} | CartItems: {inq.cart_items}")

blocks = db.query(StayRoomBlock).all()
print(f"\nTotal `stay_room_blocks` count: {len(blocks)}")
for blk in blocks:
    print(f"  Block ID: {blk.id} | Unit ID: {blk.room_unit_id} | Dates: {blk.start_date} to {blk.end_date} | Status: {blk.status}")

db.close()
