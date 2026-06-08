#!/usr/bin/env python3

import sys
from pathlib import Path

# Add the project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from sqlalchemy.orm import Session
from sqlalchemy import text
from app.config.database import get_db

def fix_stay_columns():
    """Fix missing stay property columns by adding them manually if they don't exist"""
    print("🔧 Checking and fixing stay_properties table columns...")
    
    # Get database session
    db_gen = get_db()
    db: Session = next(db_gen)
    
    try:
        # Check which columns exist in stay_properties table
        result = db.execute(text("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'stay_properties' 
            ORDER BY ordinal_position;
        """))
        
        existing_columns = [row[0] for row in result.fetchall()]
        print(f"📊 Existing columns in stay_properties: {existing_columns}")
        
        # Define required columns that might be missing
        required_columns = {
            'archived_at': "ADD COLUMN archived_at TIMESTAMP WITH TIME ZONE",
            'archived_by_id': "ADD COLUMN archived_by_id UUID",
            'archive_reason': "ADD COLUMN archive_reason TEXT",
            'is_active': "ADD COLUMN is_active BOOLEAN DEFAULT TRUE NOT NULL"
        }
        
        # Check which columns are missing and add them
        missing_columns = []
        for column_name, alter_sql in required_columns.items():
            if column_name not in existing_columns:
                missing_columns.append(column_name)
                print(f"➕ Adding missing column: {column_name}")
                try:
                    db.execute(text(f"ALTER TABLE stay_properties {alter_sql}"))
                    print(f"   ✅ Successfully added {column_name}")
                except Exception as e:
                    print(f"   ❌ Failed to add {column_name}: {str(e)}")
        
        # Add foreign key constraint for archived_by_id if it was missing
        if 'archived_by_id' in missing_columns:
            print("➕ Adding foreign key constraint for archived_by_id...")
            try:
                db.execute(text("""
                    ALTER TABLE stay_properties 
                    ADD CONSTRAINT fk_stay_properties_archived_by_id 
                    FOREIGN KEY (archived_by_id) REFERENCES users (id) ON DELETE SET NULL
                """))
                print("   ✅ Successfully added foreign key constraint")
            except Exception as e:
                print(f"   ⚠️  Foreign key constraint may already exist or failed: {str(e)}")
        
        # Create stay_status_enum if it doesn't exist
        print("🔧 Checking stay_status_enum...")
        try:
            result = db.execute(text("""
                SELECT 1 FROM pg_type WHERE typname = 'stay_status_enum'
            """))
            if not result.fetchone():
                print("➕ Creating stay_status_enum...")
                db.execute(text("""
                    CREATE TYPE stay_status_enum AS ENUM (
                        'draft', 'submitted', 'approved', 'rejected', 'archived'
                    )
                """))
                print("   ✅ Successfully created stay_status_enum")
            else:
                print("   ℹ️  stay_status_enum already exists")
        except Exception as e:
            print(f"   ❌ Error with stay_status_enum: {str(e)}")
        
        # Update is_active for existing records if column was added
        if 'is_active' in missing_columns:
            print("🔧 Setting is_active = TRUE for existing records...")
            try:
                result = db.execute(text("UPDATE stay_properties SET is_active = TRUE WHERE is_active IS NULL"))
                print(f"   ✅ Updated {result.rowcount} records")
            except Exception as e:
                print(f"   ❌ Failed to update is_active: {str(e)}")
        
        # Commit all changes
        db.commit()
        
        if missing_columns:
            print(f"\n✅ Successfully added missing columns: {missing_columns}")
        else:
            print("\n✅ All required columns already exist")
        
        # Test the fix by fetching columns again
        result = db.execute(text("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'stay_properties' 
            ORDER BY ordinal_position;
        """))
        
        final_columns = [row[0] for row in result.fetchall()]
        print(f"📊 Final columns in stay_properties: {final_columns}")
        
    except Exception as e:
        print(f"💥 Database error: {str(e)}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    fix_stay_columns()