import psycopg2

conn = psycopg2.connect("postgresql://postgres.pwmdvqunyapirtbdptxq:hEyzG8JlSViw61uO@aws-1-ap-southeast-1.pooler.supabase.com:5432/postgres")
cur = conn.cursor()
cur.execute("UPDATE alembic_version SET version_num = '20260423_fix_wishlist_schema_mismatch'")
conn.commit()
cur.close()
conn.close()
print("Updated alembic_version table")
