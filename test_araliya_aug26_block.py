from datetime import date
from app.config.database import SessionLocal
from app.services.stay_inventory_service import StayInventoryService
from app.models.stay import StayProperty
from app.schemas.stay_schema import StayAvailabilitySearchRequest

db = SessionLocal()
try:
    service = StayInventoryService(db)
    prop = db.query(StayProperty).filter(StayProperty.name.ilike("%Araliya%")).first()
    
    print("==================================================")
    print("TESTING ARALIYA AVAILABILITY FOR AUGUST 26 -> 27, 2026")
    print("==================================================")
    
    # Search Aug 26 -> Aug 27 (Month 08)
    req_aug = StayAvailabilitySearchRequest(
        propertyId=prop.id,
        checkInDate=date(2026, 8, 26),
        checkOutDate=date(2026, 8, 27),
        guests=1
    )
    res_aug = service.search_availability(req_aug)
    print(f"\nAvailability results for Check-In Aug 26, 2026 -> Check-Out Aug 27, 2026:")
    for rt in res_aug.room_types:
        print(f"  RoomType '{rt.room_type_name}' | AvailableCount={rt.available_count}")

    # Search May 26 -> May 27 (Month 05)
    req_may = StayAvailabilitySearchRequest(
        propertyId=prop.id,
        checkInDate=date(2026, 5, 26),
        checkOutDate=date(2026, 5, 27),
        guests=1
    )
    res_may = service.search_availability(req_may)
    print(f"\nAvailability results for Check-In May 26, 2026 -> Check-Out May 27, 2026:")
    for rt in res_may.room_types:
        print(f"  RoomType '{rt.room_type_name}' | AvailableCount={rt.available_count}")

finally:
    db.close()
