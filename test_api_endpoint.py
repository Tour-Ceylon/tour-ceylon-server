#!/usr/bin/env python3

import asyncio
import sys
from pathlib import Path

# Add the project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from sqlalchemy.orm import Session
from fastapi import HTTPException
from app.config.database import get_db
from app.repositories.stay_repo import StayRepository
from app.api.v1.vendor_stays import list_stay_properties, require_stay_vendor
from app.models.user import User
from app.models.enum import UserRole
from uuid import uuid4

def test_api_endpoint():
    """Test the actual API endpoint logic to identify 422 error source"""
    print("🔧 Testing Stay Properties API Endpoint Logic...")
    
    # Get database session
    db_gen = get_db()
    db: Session = next(db_gen)
    
    try:
        # Create repository
        repo = StayRepository(db)
        
        # Test without authentication (should fail appropriately)
        print("🧪 Testing endpoint without authentication...")
        try:
            # This should fail with 401/403, not 422
            result = repo.list_all()
            print(f"   📊 Raw query succeeded, found {len(result)} properties")
        except Exception as e:
            print(f"   ❌ Repository error: {str(e)}")
        
        # Test repository methods individually
        print("🧪 Testing repository methods...")
        try:
            properties = repo.list_all()
            print(f"   ✅ list_all() succeeded: {len(properties)} properties")
            
            # Test serialization of first property if exists
            if properties:
                prop = properties[0]
                print(f"   🧪 Testing first property: {prop.name}")
                print(f"      - Status: {prop.status}")
                print(f"      - Archived at: {prop.archived_at}")
                print(f"      - Is active: {prop.is_active}")
                print(f"      - Amenities count: {len(prop.amenities) if prop.amenities else 0}")
                print(f"      - Room types count: {len(prop.room_types) if prop.room_types else 0}")
            
        except Exception as e:
            print(f"   ❌ Repository method error: {str(e)}")
            import traceback
            traceback.print_exc()
        
        # Test with mock authenticated user
        print("🧪 Testing with mock vendor user...")
        try:
            # Create a mock vendor user
            mock_vendor = type('MockUser', (), {
                'id': uuid4(),
                'role': UserRole.VENDOR,
                'approved_categories': ['Stay']
            })()
            
            # Test list_for_vendor
            vendor_properties = repo.list_for_vendor(mock_vendor.id)
            print(f"   ✅ list_for_vendor() succeeded: {len(vendor_properties)} properties")
            
        except Exception as e:
            print(f"   ❌ Vendor-specific query error: {str(e)}")
            import traceback
            traceback.print_exc()
            
        # Check if there are any schema validation issues
        print("🧪 Testing response schema validation...")
        try:
            from app.schemas.stay_schema import StayPropertyListResponse
            properties = repo.list_all()
            
            # Try to create the response model
            response = StayPropertyListResponse(
                properties=properties,
                total=len(properties)
            )
            
            # Try to serialize to dict
            response_dict = response.model_dump()
            print(f"   ✅ Response serialization succeeded")
            print(f"   📊 Serialized {len(response_dict.get('properties', []))} properties")
            
        except Exception as e:
            print(f"   ❌ Response schema validation error: {str(e)}")
            import traceback
            traceback.print_exc()
            
    except Exception as e:
        print(f"💥 General error: {str(e)}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()

if __name__ == "__main__":
    test_api_endpoint()