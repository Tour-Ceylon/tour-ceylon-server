import sys, json
sys.path.append('.')
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.models.stay import StayProperty, StayRoomType
from app.models.bookingInquiry import BookingInquiry

engine = create_engine('postgresql://postgres.pwmdvqunyapirtbdptxq:hEyzG8JlSViw61uO@aws-1-ap-southeast-1.pooler.supabase.com:6543/postgres?sslmode=require')
Session = sessionmaker(bind=engine)
session = Session()

inq = session.query(BookingInquiry).filter_by(reference='INQ-HQVW6X7B').first()
prop = session.query(StayProperty).filter_by(name='ultimate').first()
rts = session.query(StayRoomType).filter_by(property_id=prop.id).all()

print('DB Room Types:')
for rt in rts:
    print(f' - "{rt.name}" (ID: {rt.id})')

print('\nCart Items:')
for item in inq.cart_items:
    for sr in item.get('selected_rooms', []):
        print(f' - "{sr.get("roomName")}" (ID: {sr.get("roomId")})')
