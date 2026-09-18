from sqlalchemy import text
from app.config.database import engine

print("Adding payment_method_enum type and payment_method column to bookings table...")
with engine.connect() as conn:
    conn.execute(text("""
        DO $$ 
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'payment_method_enum') THEN
                CREATE TYPE payment_method_enum AS ENUM ('PAY_AT_PROPERTY', 'BANK_TRANSFER', 'ONLINE', 'pay_at_property', 'bank_transfer', 'online');
            END IF;
        END $$;
    """))
    conn.execute(text("""
        ALTER TABLE bookings 
        ADD COLUMN IF NOT EXISTS payment_method payment_method_enum DEFAULT 'PAY_AT_PROPERTY';
    """))
    conn.commit()
print("Migration completed successfully! Column 'payment_method' added to 'bookings'.")
