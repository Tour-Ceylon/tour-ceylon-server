from datetime import datetime
from app.schemas.booking_inquiry_schema import CartItemSchema

print("==================================================")
print("TESTING BOOKING INQUIRY DATE VALIDATOR")
print("==================================================")

inputs = [
    "2026-09-22 to 2026-09-29",
    "2026-08-27",
    "2026-08-27T09:00:00",
    "2026-05-20T00:00:00.000Z",
]

for inp in inputs:
    item = CartItemSchema(
        listingId="57d51ef6-b752-4952-8126-5743fb112857",
        title="sound",
        travelDate=inp,
        travelCount=1,
        price=5000.0
    )
    print(f"Input: '{inp}'")
    print(f"  travel_date:     {item.travel_date}")
    print(f"  travel_date_end: {item.travel_date_end}")
    print(f"  travel_date_raw: {item.travel_date_raw}")

# Test explicit travelDateEnd or checkOutDate
item_explicit = CartItemSchema(
    listingId="57d51ef6-b752-4952-8126-5743fb112857",
    title="sound",
    travelDate="2026-09-22",
    checkOutDate="2026-09-29",
    travelCount=1,
    price=5000.0
)
print("\nExplicit checkOutDate:")
print(f"  travel_date:     {item_explicit.travel_date}")
print(f"  travel_date_end: {item_explicit.travel_date_end}")
print(f"  travel_date_raw: {item_explicit.travel_date_raw}")

print("\nSUCCESS!")
