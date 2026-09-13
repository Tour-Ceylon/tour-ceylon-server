from sqlalchemy import text
from app.config.database import engine

print("Running DB migration to add payment_policy column to stay_properties...")
with engine.connect() as conn:
    conn.execute(text("ALTER TABLE stay_properties ADD COLUMN IF NOT EXISTS payment_policy VARCHAR(50) DEFAULT 'pay_at_property';"))
    conn.commit()
print("Migration completed successfully! Column 'payment_policy' added to 'stay_properties'.")
