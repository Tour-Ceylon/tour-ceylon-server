#!/usr/bin/env python3
"""Mark the vendor_id migration as complete since the column already exists"""

import os
os.environ.setdefault('ENVIRONMENT', 'development')

from app.config.database import SessionLocal
from sqlalchemy import text

def mark_migration_complete():
    db = SessionLocal()
    try:
        # Check if vendor_id column exists
        result = db.execute(text("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'listings' AND column_name = 'vendor_id';
        """))
        vendor_id_exists = result.fetchone()
        print(f'vendor_id column exists: {bool(vendor_id_exists)}')
        
        if vendor_id_exists:
            # Mark the migration as complete since the column already exists
            db.execute(text("UPDATE alembic_version SET version_num = '20260604_add_vendor_id_to_listings';"))
            db.commit()
            print('Marked migration 20260604_add_vendor_id_to_listings as complete')
            
            # Verify the update
            result = db.execute(text('SELECT version_num FROM alembic_version;'))
            updated = result.fetchone()
            print(f'Current DB version: {updated[0] if updated else "None"}')
        else:
            print('vendor_id column does not exist - migration needed')
        
    except Exception as e:
        print(f'Error: {e}')
        db.rollback()
    finally:
        db.close()

if __name__ == '__main__':
    mark_migration_complete()