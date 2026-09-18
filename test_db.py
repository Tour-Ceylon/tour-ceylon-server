import sys, json
sys.path.append('.')
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.models.stay import StayRoomType, StayProperty

engine = create_engine('postgresql://postgres.pwmdvqunyapirtbdptxq:hEyzG8JlSViw61uO@aws-1-ap-southeast-1.pooler.supabase.com:6543/postgres?sslmode=require')
Session = sessionmaker(bind=engine)
session = Session()

prop = session.query(StayProperty).filter(StayProperty.name.ilike('%Araliya Green Hills%')).first()
if prop:
    for rt in session.query(StayRoomType).filter_by(property_id=prop.id).all():
        print(f'Room: "{rt.name}"')
