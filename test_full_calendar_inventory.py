from datetime import date, timedelta
from app.config.database import SessionLocal
from app.services.stay_inventory_service import StayInventoryService
from app.models.stay import StayProperty, StayRoomType, StayRoomUnit, StayRoomBlock, StayBooking, StayBookingRoom
from app.models.user import User

db = SessionLocal()
try:
    service = StayInventoryService(db)
    
    print("==================================================")
    print("CALENDAR, BLOCKING & BOOKING INVENTORY VERIFICATION")
    print("==================================================")
    
    properties = db.query(StayProperty).all()
    print(f"Total Stay Properties in Database: {len(properties)}")
    
    for prop in properties[:5]:
        print(f"\n--- Checking Property: '{prop.name}' (ID={prop.id}, listing_id={prop.listing_id}) ---")
        inv = service.list_inventory(prop.id)
        print(f"  Room Types: {len(inv.room_types)} | Physical Units: {len(inv.room_units)}")
        
        for rt in inv.room_types:
            units = db.query(StayRoomUnit).filter(StayRoomUnit.room_type_id == rt.id).all()
            print(f"  -> RoomType: '{rt.name}' (ID={rt.id}) | Listed Count={rt.total_units} | Physical DB Units={len(units)}")
            for u in units:
                blocks = db.query(StayRoomBlock).filter(StayRoomBlock.room_unit_id == u.id, StayRoomBlock.status == "ACTIVE").all()
                print(f"     Unit '{u.room_number}' (ID={u.id}) | Active Blocks={len(blocks)}")
                for b in blocks:
                    print(f"       Block ID={b.id} ({b.start_date} to {b.end_date})")

        # Test availability computation for next 7 days
        today = date.today()
        end_7d = today + timedelta(days=7)
        print(f"\n  Checking Availability for Next 7 Days ({today} to {end_7d}):")
        for rt in inv.room_types:
            avail_map = service._compute_nightly_availability(prop.id, {rt.id}, today, end_7d - timedelta(days=1))
            for (rt_id, d), entry in sorted(avail_map.items(), key=lambda x: x[0][1]):
                print(f"    Date={d} | Total={entry.total_units} | Booked={entry.booked_units} | Blocked={entry.blocked_units} | Available={entry.available_units}")

    print("\n==================================================")
    print("VERIFICATION COMPLETED SUCCESSFULLY")
    print("==================================================")

finally:
    db.close()
