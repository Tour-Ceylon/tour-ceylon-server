import psycopg2
import os
from uuid import uuid4
from dotenv import load_dotenv

load_dotenv()
db_url = os.getenv("DATABASE_URL")
conn = psycopg2.connect(db_url)
cur = conn.cursor()

# 1. Update all draft listings to PUBLISHED and active
cur.execute("""
    UPDATE listings 
    SET status = 'PUBLISHED', is_active = true 
    WHERE status != 'PUBLISHED';
""")
print(f"Published {cur.rowcount} listings.")

# 2. Find listings that have 0 variants
cur.execute("""
    SELECT l.id, l.title, l.listing_type 
    FROM listings l
    LEFT JOIN listing_variants lv ON l.id = lv.listing_id
    WHERE lv.id IS NULL;
""")
listings_without_variants = cur.fetchall()
print(f"Found {len(listings_without_variants)} listings with 0 variants. Creating default variants for them...")

for listing_id, title, listing_type in listings_without_variants:
    variant_id = str(uuid4())
    # Insert default variant
    cur.execute("""
        INSERT INTO listing_variants (id, listing_id, name, booking_unit, capacity_min, capacity_max, is_default, created_at, updated_at)
        VALUES (%s, %s, 'Default Option', 'PER_PERSON', 1, 10, true, now(), now());
    """, (variant_id, listing_id))
    
    # Insert pricing rule for the variant
    rule_id = str(uuid4())
    cur.execute("""
        INSERT INTO pricing_rules (id, variant_id, amount, currency, priority, pricing_rule_type, min_guest, max_guest, created_at, updated_at)
        VALUES (%s, %s, 100.00, 'USD', 0, 'FIXED', 1, 999999, now(), now());
    """, (rule_id, variant_id))

print("Default variants and pricing rules created successfully.")
conn.commit()
conn.close()
