import psycopg2
import os
from dotenv import load_dotenv

load_dotenv()
db_url = os.getenv("DATABASE_URL")
conn = psycopg2.connect(db_url)
cur = conn.cursor()

cur.execute("UPDATE listings SET status = 'SUBMITTED' WHERE status = 'submitted';")
conn.commit()
print("Rows updated:", cur.rowcount)

conn.close()
