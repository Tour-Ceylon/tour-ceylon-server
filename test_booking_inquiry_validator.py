from datetime import datetime
from pydantic import BaseModel, Field, field_validator, ConfigDict
from decimal import Decimal
from typing import Any

class CartItemSchemaTest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    
    listing_id: str = Field(..., alias="listingId")
    title: str
    travel_date: datetime = Field(..., alias="travelDate")
    travel_count: int = Field(ge=1, alias="travelCount")
    price: Decimal = Field(ge=0)

    @field_validator("travel_date", mode="before")
    @classmethod
    def parse_travel_date(cls, value: Any) -> datetime:
        if isinstance(value, datetime):
            return value
        if isinstance(value, str):
            val = value.strip()
            if " to " in val:
                val = val.split(" to ")[0].strip()
            try:
                return datetime.fromisoformat(val.replace("Z", "+00:00"))
            except ValueError:
                pass
            try:
                return datetime.strptime(val[:10], "%Y-%m-%d")
            except ValueError:
                pass
        return datetime.utcnow()

print("==================================================")
print("TESTING BOOKING INQUIRY DATE VALIDATOR")
print("==================================================")

inputs = [
    "2026-08-27 to 2026-08-28",
    "2026-08-27",
    "2026-08-27T09:00:00",
    "2026-05-20T00:00:00.000Z",
    "invalid date string test",
]

for inp in inputs:
    item = CartItemSchemaTest(
        listingId="listing_123",
        title="Araliya Green Hills",
        travelDate=inp,
        travelCount=2,
        price=100.0
    )
    print(f"Input: '{inp}' -> Parsed travel_date: {item.travel_date} (Type: {type(item.travel_date)})")

print("\nSUCCESS!")
