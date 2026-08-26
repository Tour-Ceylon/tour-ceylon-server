from app.config.database import SessionLocal
from app.models.stay import StayProperty, StayRoomTypeCalendar, StayRoomBlock, StayRoomUnit
from app.models.listing import Listing

db = SessionLocal()
try:
    print("Checking database for property_id vs listing_id alignment...")
    properties = db.query(StayProperty).all()
    prop_by_listing = {p.listing_id: p.id for p in properties if p.listing_id}
    prop_ids = {p.id for p in properties}

    # 1. Clean StayRoomTypeCalendar
    cal_entries = db.query(StayRoomTypeCalendar).all()
    remapped_cal = 0
    deleted_orphans_cal = 0
    for entry in cal_entries:
        if entry.property_id in prop_by_listing:
            entry.property_id = prop_by_listing[entry.property_id]
            remapped_cal += 1
        elif entry.property_id not in prop_ids:
            db.delete(entry)
            deleted_orphans_cal += 1

    # 2. Clean StayRoomBlock
    block_entries = db.query(StayRoomBlock).all()
    remapped_blocks = 0
    deleted_orphans_blocks = 0
    for block in block_entries:
        if block.property_id in prop_by_listing:
            block.property_id = prop_by_listing[block.property_id]
            remapped_blocks += 1
        elif block.property_id not in prop_ids:
            db.delete(block)
            deleted_orphans_blocks += 1

    db.commit()
    print(f"Cleaned Calendar Entries: Remapped={remapped_cal}, Deleted Orphans={deleted_orphans_cal}")
    print(f"Cleaned Room Blocks: Remapped={remapped_blocks}, Deleted Orphans={deleted_orphans_blocks}")
finally:
    db.close()
