from app.config.database import engine
from sqlalchemy import text

with engine.connect() as conn:
    try:
        conn.execute(text('ALTER TABLE tour_details ADD COLUMN itinerary JSON, ADD COLUMN category_id VARCHAR, ADD COLUMN additional_categories JSON;'))
        conn.commit()
        print('Success!')
    except Exception as e:
        print(f"Error (maybe already exists): {e}")
