#!/usr/bin/env python3
"""
Manually create the client_notifications table to bypass the enum duplicate issue.
"""
import os
import sys
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

# Add the app directory to the Python path
sys.path.append(os.path.join(os.path.dirname(__file__)))

from app.config.database import database_url

def create_notifications_table():
    """Create the client_notifications table manually"""
    engine = create_engine(database_url)
    
    # SQL to create the table with proper constraints
    create_table_sql = """
    CREATE TABLE IF NOT EXISTS client_notifications (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        user_id UUID REFERENCES users(id),
        recipient_email VARCHAR NOT NULL,
        type notification_type_enum NOT NULL,
        title VARCHAR NOT NULL,
        message TEXT NOT NULL,
        booking_inquiry_id UUID REFERENCES booking_inquiries(id),
        reference VARCHAR,
        payload JSONB NOT NULL DEFAULT '{}',
        is_read BOOLEAN NOT NULL DEFAULT false,
        read_at TIMESTAMP,
        created_at TIMESTAMP NOT NULL DEFAULT NOW(),
        updated_at TIMESTAMP NOT NULL DEFAULT NOW()
    );
    """
    
    # Create indexes
    create_indexes_sql = """
    CREATE INDEX IF NOT EXISTS idx_client_notifications_recipient_email ON client_notifications(recipient_email);
    CREATE INDEX IF NOT EXISTS idx_client_notifications_user_id ON client_notifications(user_id);
    CREATE INDEX IF NOT EXISTS idx_client_notifications_is_read ON client_notifications(is_read);
    CREATE INDEX IF NOT EXISTS idx_client_notifications_created_at ON client_notifications(created_at);
    CREATE INDEX IF NOT EXISTS idx_client_notifications_booking_inquiry_id ON client_notifications(booking_inquiry_id);
    """
    
    with engine.connect() as conn:
        # Execute table creation
        print("Creating client_notifications table...")
        conn.execute(text(create_table_sql))
        
        # Execute index creation
        print("Creating indexes...")
        conn.execute(text(create_indexes_sql))
        
        # Commit the transaction
        conn.commit()
        
        print("✅ Successfully created client_notifications table and indexes")

def mark_migration_complete():
    """Mark the migration as complete in alembic_version table"""
    engine = create_engine(database_url)
    
    with engine.connect() as conn:
        # Update alembic version to mark migration as complete
        print("Marking migration as complete...")
        conn.execute(text(
            "INSERT INTO alembic_version (version_num) VALUES ('20261224_add_client_notifications') "
            "ON CONFLICT (version_num) DO UPDATE SET version_num = EXCLUDED.version_num"
        ))
        conn.commit()
        print("✅ Migration marked as complete")

if __name__ == "__main__":
    try:
        create_notifications_table()
        mark_migration_complete()
        print("\n🎉 Database setup complete! You can now restart the server to test notifications.")
    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)