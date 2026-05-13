#!/usr/bin/env python3
import os
import sys

# Load environment variables
from dotenv import load_dotenv
load_dotenv()

DATABASE_URL = os.getenv('DATABASE_URL')

if not DATABASE_URL:
    print("❌ DATABASE_URL not found in .env")
    sys.exit(1)

try:
    from sqlalchemy import create_engine, text

    engine = create_engine(DATABASE_URL)

    with engine.connect() as conn:
        # Delete the broken migration record
        result = conn.execute(text(
            "DELETE FROM alembic_version WHERE version_num = '20260430_refactor_wishlist_for_multi_item_support'"
        ))
        conn.commit()

        print(
            f"✅ SUCCESS: Deleted {result.rowcount} broken migration record(s)")

        # Show remaining migrations
        rows = conn.execute(
            text("SELECT version_num FROM alembic_version ORDER BY version_num")).fetchall()
        if rows:
            print("\n📋 Remaining migrations in database:")
            for row in rows:
                print(f"   - {row[0]}")
        else:
            print("\n📋 No migrations in database (clean slate)")

except Exception as e:
    print(f"❌ ERROR: {e}")
    sys.exit(1)
