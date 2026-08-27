from datetime import date, timedelta
from app.config.database import SessionLocal
from app.services.stay_inventory_service import StayInventoryService
from app.models.stay import StayProperty, StayRoomType, StayRoomUnit, StayRoomBlock, StayBooking, StayBookingRoom, StayRoomTypeCalendar
from app.schemas.stay_schema import StayAvailabilitySearchRequest

db = SessionLocal()
try:
    service = StayInventoryService(db)
    print("==================================================")
    print("INSPECTING ARALIYA AVAILABILITY FOR AUG 26 & AUG 27")
    print("==================================================")
    
    # Find property
    prop = db.query(StayProperty).filter(StayProperty.name.ilike("%Araliya%")).first()
    if not prop:
        print("Araliya property not found!")
    else:
        print(f"PROPERTY: '{prop.name}' (ID={prop.id}, listing_id={prop.listing_id})")
        
        room_types = db.query(StayRoomType).filter(StayRoomType.property_id == prop.id).all()
        print(f"Room Types count: {len(room_types)}")
        for rt in room_types:
            units = db.query(StayRoomUnit).filter(StayRoomUnit.room_type_id == rt.id).all()
            print(f"  RoomType '{rt.name}' (ID={rt.id}): physical_units_in_db={len(units)}")
            for u in units:
                blocks = db.query(StayRoomBlock).filter(StayRoomBlock.room_unit_id == u.id, StayRoomBlock.status == "ACTIVE").all()
                print(f"    Unit '{u.room_number}' (ID={u.id}) | Active Blocks={len(blocks)}")
                for b in blocks:
                    print(f"      Block ID={b.id}: {b.start_date} to {b.end_date}")
        
        # Check Aug 26
        check_date_26 = date(2026, 8, 26)
        print(f"\n--- Nightly Availability for Date {check_date_26} ---")
        rt_ids = {rt.id for rt in room_types}
        avail_map_26 = service._compute_nightly_availability(prop.id, rt_ids, check_date_26, check_date_26)
        for (rt_id, d), entry in avail_map_26.items():
            print(f"  RoomType ID={rt_id} | Date={d} | Total={entry.total_units} | Booked={entry.booked_units} | Blocked={entry.blocked_units} | Available={entry.available_units}")

        # Check Aug 27
        check_date_27 = date(2026, 8, 27)
        print(f"\n--- Nightly Availability for Date {check_date_27} ---")
        avail_map_27 = service._compute_nightly_availability(prop.id, rt_ids, check_date_27, check_date_27)
        for (rt_id, d), entry in avail_map_27.items():
            print(f"  RoomType ID={rt_id} | Date={d} | Total={entry.total_units} | Booked={entry.booked_units} | Blocked={entry.blocked_units} | Available={entry.available_units}")

        # Check search_availability API request
        req = StayAvailabilitySearchRequest(
            propertyId=prop.id,
            checkInDate=check_date_26,
            checkOutDate=check_date_27,
            guests=1
        )
        search_res = service.search_availability(req)
        print(f"\nsearch_availability API result for Aug 26 -> Aug 27:")
        for rt_res in search_res.room_types:
            print(f"  RoomType '{rt_res.room_type_name}' | AvailableCount={rt_res.available_count}")

finally:
    db.close()
