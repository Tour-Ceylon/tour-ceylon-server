import psycopg2
import os
from dotenv import load_dotenv

load_dotenv()
db_url = os.getenv("DATABASE_URL")
if not db_url:
    print("DATABASE_URL is not set!")
    exit(1)

print(f"Connecting to database: {db_url.split('@')[-1]}")
try:
    conn = psycopg2.connect(db_url)
    cur = conn.cursor()
    
    # Get all tables
    cur.execute("""
        SELECT table_name 
        FROM information_schema.tables 
        WHERE table_schema = 'public';
    """)
    tables = [row[0] for row in cur.fetchall()]
    print(f"\nTables found: {len(tables)}")
    
    for table in sorted(tables):
        try:
            cur.execute(f"SELECT COUNT(*) FROM \"{table}\";")
            count = cur.fetchone()[0]
            print(f"- {table}: {count} rows")
        except Exception as e:
            print(f"- {table}: Error reading ({e})")
            conn.rollback()
            
    conn.close()
except Exception as e:
    print(f"Error: {e}")
