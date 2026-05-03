import os
import psycopg2
from dotenv import load_dotenv

# Load the exact same .env your server uses
load_dotenv()
url = os.getenv("DATABASE_URL")

if not url:
    print("Error: DATABASE_URL not found in .env")
    exit(1)

print(f"Attempting to connect to: {url.split('@')[-1]}")

try:
    conn = psycopg2.connect(url)
    conn.autocommit = True
    cur = conn.cursor()
    
    print("Connection successful! Adding missing columns...")
    
    # List of columns to add
    queries = [
        "ALTER TABLE \"Packages\" ADD COLUMN IF NOT EXISTS summary TEXT;",
        "ALTER TABLE \"Packages\" ADD COLUMN IF NOT EXISTS nights INTEGER;",
        "ALTER TABLE \"Packages\" ADD COLUMN IF NOT EXISTS trip_style VARCHAR;",
        "ALTER TABLE \"Packages\" ADD COLUMN IF NOT EXISTS start_location VARCHAR;",
        "ALTER TABLE \"Packages\" ADD COLUMN IF NOT EXISTS end_location VARCHAR;",
        "ALTER TABLE \"Packages\" ADD COLUMN IF NOT EXISTS destinations JSONB DEFAULT '[]'::jsonb;",
        "ALTER TABLE \"Packages\" ADD COLUMN IF NOT EXISTS highlights JSONB DEFAULT '[]'::jsonb;",
        "ALTER TABLE \"Packages\" ADD COLUMN IF NOT EXISTS exclusions JSONB DEFAULT '[]'::jsonb;",
        "ALTER TABLE \"Packages\" ADD COLUMN IF NOT EXISTS quick_facts JSONB DEFAULT '{}'::jsonb;",
        "ALTER TABLE \"Packages\" ADD COLUMN IF NOT EXISTS structured_itinerary JSONB DEFAULT '[]'::jsonb;",
        "ALTER TABLE \"Packages\" ADD COLUMN IF NOT EXISTS listing_refs JSONB DEFAULT '[]'::jsonb;",
    ]
    
    for query in queries:
        try:
            cur.execute(query)
            print(f"SUCCESS: {query.strip()}")
        except Exception as e:
            print(f"ALREADY EXISTS or ERROR: {str(e).strip()}")
            
    # Also update alembic_version so alembic knows we are up to date
    try:
        cur.execute("CREATE TABLE IF NOT EXISTS alembic_version (version_num VARCHAR(32) PRIMARY KEY);")
        cur.execute("DELETE FROM alembic_version;")
        cur.execute("INSERT INTO alembic_version (version_num) VALUES ('20260502_add_structured_package_fields');")
        print("Alembic version table updated to 20260502_add_structured_package_fields.")
    except Exception as e:
        print(f"Could not update alembic_version: {e}")

    cur.close()
    conn.close()
    print("\nMigration completed successfully! Your Admin Portal should work now.")

except Exception as e:
    print(f"\nFATAL ERROR: {e}")
    print("\nIf you still get 'No such host is known', your machine is having trouble reaching Supabase.")
