#!/usr/bin/env python3

import sys
from pathlib import Path

# Add the project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from sqlalchemy.orm import Session
from sqlalchemy import text
from app.config.database import get_db

def fix_stay_enum_uppercase():
    """Fix the stay_status_enum values to use uppercase values"""
    print("🔧 Fixing stay_status_enum to use uppercase values...")
    
    # Get database session
    db_gen = get_db()
    db: Session = next(db_gen)
    
    try:
        # Check current enum values
        result = db.execute(text("""
            SELECT unnest(enum_range(NULL::stay_status_enum))::text as enum_value;
        """))
        
        current_values = [row[0] for row in result.fetchall()]
        print(f"📊 Current enum values: {current_values}")
        
        expected_values = ['DRAFT', 'SUBMITTED', 'APPROVED', 'REJECTED', 'ARCHIVED']
        print(f"📊 Expected enum values: {expected_values}")
        
        if set(current_values) != set(expected_values):
            print("🔧 Enum values don't match. Recreating enum with uppercase values...")
            
            # Get current status values from the table
            result = db.execute(text("SELECT DISTINCT status FROM stay_properties"))
            existing_statuses = [row[0] for row in result.fetchall()]
            print(f"📊 Existing status values in table: {existing_statuses}")
            
            # Step 1: Add a temporary column with string type
            print("➕ Adding temporary status column...")
            try:
                db.execute(text("ALTER TABLE stay_properties ADD COLUMN status_temp VARCHAR(50)"))
            except Exception as e:
                if "already exists" in str(e).lower():
                    print("   ℹ️  Temporary column already exists, continuing...")
                else:
                    raise e
            
            # Step 2: Copy current status values to temp column (convert to uppercase)
            print("📋 Copying status values to temporary column...")
            db.execute(text("UPDATE stay_properties SET status_temp = UPPER(status::text)"))
            
            # Step 3: Drop the old status column
            print("🗑️  Dropping old status column...")
            db.execute(text("ALTER TABLE stay_properties DROP COLUMN status"))
            
            # Step 4: Drop and recreate the enum type with uppercase values
            print("🔄 Recreating stay_status_enum with uppercase values...")
            db.execute(text("DROP TYPE IF EXISTS stay_status_enum CASCADE"))
            db.execute(text("""
                CREATE TYPE stay_status_enum AS ENUM (
                    'DRAFT', 'SUBMITTED', 'APPROVED', 'REJECTED', 'ARCHIVED'
                )
            """))
            
            # Step 5: Add status column back with proper enum type
            print("➕ Adding status column with correct enum type...")
            db.execute(text("""
                ALTER TABLE stay_properties 
                ADD COLUMN status stay_status_enum DEFAULT 'DRAFT'::stay_status_enum NOT NULL
            """))
            
            # Step 6: Migrate data from temp column to status column
            print("📋 Migrating data back to status column...")
            db.execute(text("""
                UPDATE stay_properties 
                SET status = CASE 
                    WHEN status_temp = 'DRAFT' THEN 'DRAFT'::stay_status_enum
                    WHEN status_temp = 'SUBMITTED' THEN 'SUBMITTED'::stay_status_enum
                    WHEN status_temp = 'APPROVED' THEN 'APPROVED'::stay_status_enum
                    WHEN status_temp = 'REJECTED' THEN 'REJECTED'::stay_status_enum
                    WHEN status_temp = 'ARCHIVED' THEN 'ARCHIVED'::stay_status_enum
                    ELSE 'DRAFT'::stay_status_enum
                END
            """))
            
            # Step 7: Drop temporary column
            print("🗑️  Dropping temporary column...")
            db.execute(text("ALTER TABLE stay_properties DROP COLUMN status_temp"))
            
            # Step 8: Create index on status column
            print("🔍 Creating index on status column...")
            try:
                db.execute(text("CREATE INDEX IF NOT EXISTS idx_stay_properties_status ON stay_properties (status)"))
                print("   ✅ Successfully created index")
            except Exception as e:
                print(f"   ⚠️  Could not create index: {str(e)}")
            
            # Commit all changes
            db.commit()
            print("✅ Successfully fixed stay_status_enum to use uppercase values")
        else:
            print("✅ Enum values are already correct")
        
        # Verify the fix
        result = db.execute(text("""
            SELECT unnest(enum_range(NULL::stay_status_enum))::text as enum_value;
        """))
        
        final_values = [row[0] for row in result.fetchall()]
        print(f"📊 Final enum values: {final_values}")
        
        # Check data in the table
        result = db.execute(text("SELECT DISTINCT status FROM stay_properties"))
        table_statuses = [row[0] for row in result.fetchall()]
        print(f"📊 Status values in table: {table_statuses}")
        
    except Exception as e:
        print(f"💥 Database error: {str(e)}")
        db.rollback()
        raise e
    finally:
        db.close()

if __name__ == "__main__":
    fix_stay_enum_uppercase()