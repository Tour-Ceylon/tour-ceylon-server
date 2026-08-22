import psycopg2
import os
from dotenv import load_dotenv

load_dotenv()
db_url = os.getenv("DATABASE_URL")
conn = psycopg2.connect(db_url)
cur = conn.cursor()

cur.execute("SELECT id, title, status FROM listings;")
rows = cur.fetchall()
print("Raw statuses in listings:")
for r in rows:
    print(f"- ID: {r[0]}, Title: '{r[1]}', Status: '{r[2]}'")

conn.close()
