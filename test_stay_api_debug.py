#!/usr/bin/env python3

import asyncio
import sys
from pathlib import Path

# Add the project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from sqlalchemy.orm import Session
from app.config.database import get_db
from app.repositories.stay_repo import StayRepository
from app.schemas.stay_schema import StayPropertyResponse, StayPropertyListResponse
from pydantic import ValidationError

def test_stay_serialization():
    """Test stay property serialization to identify the 422 error source"""
    print("🔧 Testing Stay Property Serialization...")
    
    # Get database session
    db_gen = get_db()
    db: Session = next(db_gen)
    
    try:
        # Create repository
        repo = StayRepository(db)
        
        # Get all stays to test serialization
        print("📋 Fetching all stay properties...")
        raw_properties = repo.list_all()
        print(f"📊 Found {len(raw_properties)} stay properties")
        
        if not raw_properties:
            print("⚠️  No stay properties found in database")
            return
            
        # Test individual property serialization
        failed_properties = []
        for i, prop in enumerate(raw_properties):
            try:
                print(f"🧪 Testing property {i+1}: {prop.name} (ID: {prop.id})")
                
                # Test raw attributes
                print(f"   - Has metadata_json: {hasattr(prop, 'metadata_json')}")
                print(f"   - metadata_json value: {getattr(prop, 'metadata_json', 'NOT FOUND')}")
                print(f"   - Has amenities: {len(prop.amenities) if prop.amenities else 0}")
                print(f"   - Has room_types: {len(prop.room_types) if prop.room_types else 0}")
                
                # Try to serialize this property
                response = StayPropertyResponse.model_validate(prop)
                print(f"   ✅ Property serialized successfully")
                
            except ValidationError as e:
                print(f"   ❌ Validation error for property {prop.id}:")
                print(f"      Error: {str(e)}")
                failed_properties.append((prop, str(e)))
            except Exception as e:
                print(f"   💥 Unexpected error for property {prop.id}: {str(e)}")
                failed_properties.append((prop, str(e)))
        
        # Test list response serialization
        if not failed_properties:
            try:
                print("🧪 Testing StayPropertyListResponse...")
                list_response = StayPropertyListResponse(
                    properties=raw_properties,
                    total=len(raw_properties)
                )
                print("✅ StayPropertyListResponse serialized successfully")
            except ValidationError as e:
                print(f"❌ StayPropertyListResponse validation error: {str(e)}")
            except Exception as e:
                print(f"💥 StayPropertyListResponse unexpected error: {str(e)}")
        
        # Report results
        if failed_properties:
            print(f"\n📊 Summary: {len(failed_properties)} properties failed serialization")
            for prop, error in failed_properties:
                print(f"   - {prop.name} (ID: {prop.id}): {error}")
        else:
            print("\n✅ All properties serialized successfully")
            
    except Exception as e:
        print(f"💥 Database error: {str(e)}")
    finally:
        db.close()

if __name__ == "__main__":
    test_stay_serialization()