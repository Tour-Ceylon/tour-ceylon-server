import psycopg2
import os
from dotenv import load_dotenv

load_dotenv()
db_url = os.getenv("DATABASE_URL")
conn = psycopg2.connect(db_url)
cur = conn.cursor()

cur.execute("SELECT enumlabel FROM pg_enum JOIN pg_type ON pg_enum.enumtypid = pg_type.oid WHERE pg_type.typname = 'stay_status_enum'")
print("StayStatus enum labels:", cur.fetchall())

cur.execute("SELECT status FROM stay_properties LIMIT 5;")
print("Existing statuses in table:", cur.fetchall())

conn.close()
