#!/usr/bin/env python3
"""Fix Alembic version in database to correct state"""

import os
os.environ.setdefault('ENVIRONMENT', 'development')

from app.config.database import SessionLocal
from sqlalchemy import text

def fix_alembic_version():
    db = SessionLocal()
    try:
        # Check current version in database
        result = db.execute(text('SELECT version_num FROM alembic_version;'))
        current = result.fetchone()
        print(f'Current DB version: {current[0] if current else "None"}')
        
        # Update to the correct last good revision
        db.execute(text("UPDATE alembic_version SET version_num = '20260602_implement_stay_archive_system';"))
        db.commit()
        print('Updated DB version to: 20260602_implement_stay_archive_system')
        
        # Verify the update
        result = db.execute(text('SELECT version_num FROM alembic_version;'))
        updated = result.fetchone()
        print(f'Verified DB version: {updated[0] if updated else "None"}')
        
    except Exception as e:
        print(f'Error: {e}')
        db.rollback()
    finally:
        db.close()

if __name__ == '__main__':
    fix_alembic_version()