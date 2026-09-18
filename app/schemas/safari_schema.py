from pydantic import BaseModel, ConfigDict, Field
from typing import List, Optional
from datetime import date
from uuid import UUID

class SafariBlockCreate(BaseModel):
    variantIds: List[str] = []
    startDate: str
    endDate: str
    reason: str
    blockType: str

class SafariBlockResponse(BaseModel):
    id: UUID
    listing_id: UUID
    variant_id: Optional[UUID] = None
    start_date: date
    end_date: date
    reason: Optional[str] = None
    block_type: Optional[str] = None

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

class SafariBlockListResponse(BaseModel):
    blocks: List[SafariBlockResponse]

class SafariCalendarEntry(BaseModel):
    date: str
    available: bool

class SafariVariantCalendar(BaseModel):
    id: UUID
    name: str
    entries: List[SafariCalendarEntry]

class SafariCalendarResponse(BaseModel):
    entries: List[SafariVariantCalendar]
