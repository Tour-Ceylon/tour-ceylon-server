from app.config.database import SessionLocal
from app.models.stay import StayProperty, StayRoomType, StayRoomUnit, StayRoomBlock

db = SessionLocal()
try:
    print("==================================================")
    print("INSPECTING ALL BLOCKS FOR ARALIYA MASTER BEDROOM")
    print("==================================================")
    
    prop = db.query(StayProperty).filter(StayProperty.name.ilike("%Araliya%")).first()
    if not prop:
        print("Property not found!")
    else:
        print(f"PROPERTY: '{prop.name}' (ID={prop.id})")
        rt = db.query(StayRoomType).filter(StayRoomType.property_id == prop.id, StayRoomType.name.ilike("%Master%")).first()
        if not rt:
            print("Master Bedroom room type not found!")
        else:
            print(f"RoomType '{rt.name}' (ID={rt.id})")
            units = db.query(StayRoomUnit).filter(StayRoomUnit.room_type_id == rt.id).all()
            print(f"Units in Master Bedroom ({len(units)}):")
            for u in units:
                print(f"  Unit '{u.room_number}' (ID={u.id}, status='{u.status}')")
            
            blocks = db.query(StayRoomBlock).filter(StayRoomBlock.property_id == prop.id).all()
            print(f"\nAll Room Blocks for Property ({len(blocks)}):")
            for b in blocks:
                unit = db.query(StayRoomUnit).filter(StayRoomUnit.id == b.room_unit_id).first()
                u_num = unit.room_number if unit else str(b.room_unit_id)
                print(f"  Block ID={b.id} | Unit='{u_num}' | Start={b.start_date} | End={b.end_date} | Status={b.status} | Reason={b.reason}")

finally:
    db.close()
