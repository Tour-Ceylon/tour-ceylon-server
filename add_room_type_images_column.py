"""Add the `images` column to stay_room_types and give every existing room type a temporary photo.

The room card on the client shows the photos stored on each room type. The column is NOT NULL (default '[]'),
so the column must exist before the new code runs. Rooms that have no photo yet get a temporary placeholder
URL so listings do not render empty; replace it from the vendor portal (Room photos) whenever real photos exist.

It only adds the column and fills rooms whose list is empty. It never overwrites photos a vendor has set,
and it is safe to run again.

    python add_room_type_images_column.py
"""
import json
from urllib.parse import urlparse

from sqlalchemy import text

from app.config.database import engine

TEMP_ROOM_IMAGE_URL = (
    "https://images.unsplash.com/photo-1631049307264-da0ec9d70304?auto=format&fit=crop&w=1200&q=80"
)
TEMP_IMAGE = [
    {
        "url": TEMP_ROOM_IMAGE_URL,
        "alt": "Room photo (temporary)",
        "sortOrder": 0,
        "isPrimary": True,
        "temporary": True,
    }
]

print(f"Target database host: {urlparse(str(engine.url)).hostname}")

with engine.begin() as conn:
    conn.execute(text("ALTER TABLE stay_room_types ADD COLUMN IF NOT EXISTS images JSONB NOT NULL DEFAULT '[]'::jsonb"))
    result = conn.execute(
        text("UPDATE stay_room_types SET images = CAST(:images AS JSONB) WHERE images IS NULL OR images = '[]'::jsonb"),
        {"images": json.dumps(TEMP_IMAGE)},
    )
    print(f"Column ready. Temporary photo added to {result.rowcount} room type(s).")
