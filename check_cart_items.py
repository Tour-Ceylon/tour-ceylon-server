import sys, os
sys.path.insert(0, os.path.dirname(__file__))
from app.config.database import SessionLocal
from app.models.bookingInquiry import BookingInquiry

db = SessionLocal()
inquiries = db.query(BookingInquiry).order_by(BookingInquiry.created_at.desc()).limit(5).all()
for inq in inquiries:
    print(f"Inquiry ID: {inq.id}")
    for item in inq.cart_items:
        print(f"  Item: {item}")
db.close()
