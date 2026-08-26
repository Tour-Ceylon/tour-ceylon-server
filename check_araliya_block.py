from datetime import date, timedelta
from app.config.database import SessionLocal
from app.services.stay_inventory_service import StayInventoryService
from app.models.stay import StayProperty
from app.models.listing import Listing

db = SessionLocal()
try:
    service = StayInventoryService(db)
    
    # Find Araliya Green Hills
    prop = db.query(StayProperty).filter(StayProperty.name.ilike("%araliya%")).first()
    if not prop:
        listing = db.query(Listing).filter(Listing.title.ilike("%araliya%")).first()
        if listing:
            prop = service.get_property(listing.id)
            
    if not prop:
        print("Araliya property not found!")
    else:
        print(f"FOUND PROPERTY: '{prop.name}' (ID={prop.id}, listing_id={prop.listing_id})")
        inv = service.list_inventory(prop.id)
        print(f"Room types count: {len(inv.room_types)}, Room units count: {len(inv.room_units)}")
        for rt in inv.room_types:
            print(f"  RoomType '{rt.name}' (ID={rt.id}): total_units={rt.total_units}")
            
        blocks = service.list_property_blocks(prop.id)
        print(f"Active room blocks count: {len(blocks.blocks)}")
        for b in blocks.blocks:
            print(f"  Block ID={b.id}: unit_id={b.room_unit_id}, start={b.start_date}, end={b.end_date}, status={b.status}")
            
        # Test availability for 2026-08-26 -> 2026-08-28
        start_d = date(2026, 8, 26)
        end_d = date(2026, 8, 28)
        
        print(f"\nChecking calendar for date range {start_d} to {end_d}...")
        for rt in inv.room_types:
            cal = service.get_calendar(prop.id, start_d, end_d, rt.id)
            for e in cal.entries:
                print(f"  Date={e.date} | Available={e.available_units} | Blocked={e.blocked_units} | Total={e.total_units}")
                
        # Test get_available_stay_property_ids
        avail_ids = service.get_available_stay_property_ids(start_d, end_d)
        is_avail = (prop.id in avail_ids) or (prop.listing_id in avail_ids)
        print(f"\nIs Araliya in get_available_stay_property_ids({start_d}, {end_d})? -> {is_avail}")

finally:
    db.close()
