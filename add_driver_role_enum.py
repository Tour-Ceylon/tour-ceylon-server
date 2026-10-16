"""Add the DRIVER value to the user_role_enum Postgres type.

The application's UserRole enum has DRIVER, but databases created before the driver
module shipped only have TOURIST / ADMIN / SUPPORT / VENDOR, so saving a user with
role DRIVER fails with: invalid input value for enum user_role_enum: "DRIVER".

Safe to run more than once. Postgres cannot remove an enum value afterwards, so run it
against the database you actually mean to change (it prints the host first).

    python add_driver_role_enum.py
"""
from urllib.parse import urlparse

from sqlalchemy import text

from app.config.database import engine

host = urlparse(str(engine.url)).hostname
print(f"Target database host: {host}")

# ALTER TYPE ... ADD VALUE cannot run inside a transaction block on older Postgres versions.
with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as conn:
    conn.execute(text("ALTER TYPE user_role_enum ADD VALUE IF NOT EXISTS 'DRIVER'"))
    values = [
        row[0]
        for row in conn.execute(
            text(
                "SELECT e.enumlabel FROM pg_enum e JOIN pg_type t ON t.oid = e.enumtypid "
                "WHERE t.typname = 'user_role_enum' ORDER BY e.enumsortorder"
            )
        )
    ]

print(f"user_role_enum now contains: {values}")
