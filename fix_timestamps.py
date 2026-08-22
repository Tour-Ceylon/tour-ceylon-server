import psycopg2
import os
from dotenv import load_dotenv

load_dotenv()
db_url = os.getenv("DATABASE_URL")
conn = psycopg2.connect(db_url)
cur = conn.cursor()

# Find tables with created_at or updated_at columns
cur.execute("""
    SELECT table_name, column_name 
    FROM information_schema.columns 
    WHERE table_schema = 'public' AND column_name IN ('created_at', 'updated_at');
""")
columns = cur.fetchall()

updates = {}
for table, col in columns:
    updates.setdefault(table, []).append(col)

for table, cols in updates.items():
    # Update rows where timestamp is null
    conditions = " OR ".join([f"\"{col}\" IS NULL" for col in cols])
    set_clause = ", ".join([f"\"{col}\" = now()" for col in cols])
    
    # Check if there are any nulls
    cur.execute(f"SELECT COUNT(*) FROM \"{table}\" WHERE {conditions};")
    count = cur.fetchone()[0]
    if count > 0:
        print(f"Table '{table}': Found {count} rows with null timestamps. Updating...")
        cur.execute(f"UPDATE \"{table}\" SET {set_clause} WHERE {conditions};")
        print(f"Table '{table}': Updated {cur.rowcount} rows.")

conn.commit()
conn.close()
print("Timestamp cleanup complete!")
