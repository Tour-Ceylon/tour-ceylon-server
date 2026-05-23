"""
Safe migration script: adds vendor_status, approved_categories, company_name,
and business_profile columns to the public.users table.
Runs idempotently - safe to run multiple times.
"""
import psycopg2
import os
from dotenv import load_dotenv

load_dotenv()
db_url = os.getenv("DATABASE_URL")

migrations = [
    # vendor_status: string enum (pending/approved/rejected/suspended)
    """ALTER TABLE public.users
       ADD COLUMN IF NOT EXISTS vendor_status VARCHAR(50) DEFAULT NULL;""",

    # approved_categories: JSON array of strings e.g. ["Stay", "Tour"]
    """ALTER TABLE public.users
       ADD COLUMN IF NOT EXISTS approved_categories JSONB DEFAULT '[]'::jsonb;""",

    # company_name: business name for vendors
    """ALTER TABLE public.users
       ADD COLUMN IF NOT EXISTS company_name VARCHAR(255) DEFAULT NULL;""",

    # business_profile: free-form JSON blob for vendor business details
    """ALTER TABLE public.users
       ADD COLUMN IF NOT EXISTS business_profile JSONB DEFAULT '{}'::jsonb;""",
]

print(f"Connecting to database...")
conn = psycopg2.connect(db_url)
conn.autocommit = False
cur = conn.cursor()

try:
    for migration in migrations:
        print(f"\nRunning: {migration.strip()[:80]}...")
        cur.execute(migration)
        print("  OK")
    conn.commit()
    print("\n✅ All migrations applied successfully.")
except Exception as e:
    conn.rollback()
    print(f"\n❌ Migration failed: {e}")
    raise
finally:
    cur.close()
    conn.close()

# Verify
print("\nVerifying columns in public.users...")
conn = psycopg2.connect(db_url)
cur = conn.cursor()
cur.execute("""
    SELECT column_name, data_type, column_default
    FROM information_schema.columns
    WHERE table_name = 'users' AND table_schema = 'public'
    ORDER BY ordinal_position;
""")
for col in cur.fetchall():
    print(f"  {col[0]}: {col[1]} (default: {col[2]})")
cur.close()
conn.close()
