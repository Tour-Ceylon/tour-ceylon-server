import psycopg2
import time

url_5432 = "postgresql://postgres.pwmdvqunyapirtbdptxq:hEyzG8JlSViw61uO@aws-1-ap-southeast-1.pooler.supabase.com:5432/postgres?sslmode=require"
url_6543 = "postgresql://postgres.pwmdvqunyapirtbdptxq:hEyzG8JlSViw61uO@aws-1-ap-southeast-1.pooler.supabase.com:6543/postgres?sslmode=require"

print("Testing Port 5432 with sslmode=require...")
t0 = time.time()
try:
    conn = psycopg2.connect(url_5432, connect_timeout=5)
    print(f"Port 5432 Success in {time.time()-t0:.2f}s")
    conn.close()
except Exception as e:
    print(f"Port 5432 Failed: {e}")

print("\nTesting Port 6543 (Transaction Pooler) with sslmode=require...")
t0 = time.time()
try:
    conn = psycopg2.connect(url_6543, connect_timeout=5)
    print(f"Port 6543 Success in {time.time()-t0:.2f}s")
    conn.close()
except Exception as e:
    print(f"Port 6543 Failed: {e}")
