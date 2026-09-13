from app.config.database import SessionLocal
from app.models.stay import StayProperty, StayRoomTypeCalendar, StayRoomBlock, StayRoomUnit

db = SessionLocal()
try:
    prop = db.query(StayProperty).filter(StayProperty.name.ilike("%Araliya%")).first()
    print(f"PROPERTY: '{prop.name}' (ID={prop.id})")
    
    blocks = db.query(StayRoomBlock).filter(StayRoomBlock.property_id == prop.id).all()
    print(f"\nAll Room Blocks for Araliya (Count={len(blocks)}):")
    for b in blocks:
        unit = db.query(StayRoomUnit).get(b.room_unit_id)
        u_name = unit.room_number if unit else "Unknown"
        print(f"  Block ID={b.id} | Unit='{u_name}' ({b.room_unit_id}) | Dates={b.start_date} to {b.end_date} | Status={b.status}")
        
    cal_rows = db.query(StayRoomTypeCalendar).filter(StayRoomTypeCalendar.property_id == prop.id).order_by(StayRoomTypeCalendar.stay_date).all()
    print(f"\nAll DB Calendar Entries in StayRoomTypeCalendar (Count={len(cal_rows)}):")
    for c in cal_rows:
        print(f"  CalID={c.id} | RT={c.room_type_id} | Date={c.stay_date} | Avail={c.available_units} | Blocked={c.blocked_units} | Booked={c.booked_units} | Total={c.total_units} | Closed={c.is_closed}")

finally:
    db.close()
