from datetime import date, timedelta
from app.config.database import SessionLocal
from app.services.stay_inventory_service import StayInventoryService
from app.models.stay import StayProperty, StayRoomType, StayRoomUnit, StayRoomBlock, StayBooking, StayBookingRoom
from app.schemas.stay_schema import StayAvailabilitySearchRequest

db = SessionLocal()
try:
    service = StayInventoryService(db)
    print("==================================================")
    print("INSPECTING ARALIYA GREEN HILLS FOR MAY 27, 2026")
    print("==================================================")
    
    prop = db.query(StayProperty).filter(StayProperty.name.ilike("%Araliya%")).first()
    if not prop:
        print("Property not found!")
    else:
        print(f"PROPERTY: '{prop.name}' (ID={prop.id}, listing_id={prop.listing_id})")
        
        # 1. List all blocks on this property across all time
        all_blocks = db.query(StayRoomBlock).filter(StayRoomBlock.property_id == prop.id).all()
        print(f"\nTotal Blocks in DB for Araliya: {len(all_blocks)}")
        for b in all_blocks:
            unit = db.query(StayRoomUnit).get(b.room_unit_id)
            u_name = unit.room_number if unit else "Unknown"
            print(f"  Block ID={b.id} | Unit='{u_name}' | Dates: {b.start_date} to {b.end_date} | Status={b.status} | Reason={b.reason}")

        # 2. Check May 27, 2026 (1 night stay: May 27 -> May 28)
        may_27_in = date(2026, 5, 27)
        may_27_out = date(2026, 5, 28)
        
        req_may = StayAvailabilitySearchRequest(
            propertyId=prop.id,
            checkInDate=may_27_in,
            checkOutDate=may_27_out,
            guests=1
        )
        res_may = service.search_availability(req_may)
        print(f"\nAvailable rooms for May 27, 2026 -> May 28, 2026 (1 night):")
        for rt in res_may.room_types:
            print(f"  RoomType '{rt.room_type_name}' | AvailableCount={rt.available_count}")

        # 3. Check May 27, 2026 (same day: May 27 -> May 27)
        req_may_sameday = StayAvailabilitySearchRequest(
            propertyId=prop.id,
            checkInDate=may_27_in,
            checkOutDate=may_27_in,
            guests=1
        )
        res_may_sameday = service.search_availability(req_may_sameday)
        print(f"\nAvailable rooms for May 27, 2026 -> May 27, 2026 (Same Day Check-In/Out):")
        for rt in res_may_sameday.room_types:
            print(f"  RoomType '{rt.room_type_name}' | AvailableCount={rt.available_count}")

        # 4. Check August 27, 2026 (1 night stay: Aug 27 -> Aug 28)
        aug_27_in = date(2026, 8, 27)
        aug_27_out = date(2026, 8, 28)
        req_aug = StayAvailabilitySearchRequest(
            propertyId=prop.id,
            checkInDate=aug_27_in,
            checkOutDate=aug_27_out,
            guests=1
        )
        res_aug = service.search_availability(req_aug)
        print(f"\nAvailable rooms for Aug 27, 2026 -> Aug 28, 2026 (1 night):")
        for rt in res_aug.room_types:
            print(f"  RoomType '{rt.room_type_name}' | AvailableCount={rt.available_count}")

finally:
    db.close()
