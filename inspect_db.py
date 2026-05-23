import psycopg2
import os
from dotenv import load_dotenv

load_dotenv()
db_url = os.getenv("DATABASE_URL")
conn = psycopg2.connect(db_url)
cur = conn.cursor()

# Get users table columns in 'public' schema
cur.execute("""
    SELECT column_name, data_type 
    FROM information_schema.columns 
    WHERE table_name = 'users' AND table_schema = 'public';
""")
columns = cur.fetchall()
print("\n--- Public Users Table Columns ---")
for col in columns:
    print(f"{col[0]}: {col[1]}")

conn.close()
