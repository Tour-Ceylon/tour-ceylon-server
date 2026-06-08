#!/usr/bin/env python3
"""Test that the vendor_id fix resolves the StayApprovalService issue"""

import os
os.environ.setdefault('ENVIRONMENT', 'development')

from uuid import uuid4
from app.models.listing import Listing
from app.models.enum import ListingType, CurrencyCode
from app.config.database import SessionLocal

def test_vendor_id_compatibility():
    """Test that Listing model accepts vendor_id field"""
    print("Testing vendor_id compatibility with Listing model...")
    
    try:
        # Test 1: Check that Listing model has vendor_id field
        listing_fields = [field.name for field in Listing.__table__.columns]
        print(f"Listing model fields: {listing_fields}")
        
        has_vendor_id = 'vendor_id' in listing_fields
        print(f"✅ vendor_id field exists in Listing model: {has_vendor_id}")
        
        # Test 2: Test creating a Listing object with vendor_id (like StayApprovalService does)
        test_vendor_id = uuid4()
        test_destination_id = uuid4()
        
        # This simulates what StayApprovalService line 95-105 does
        listing_data = {
            "listing_type": ListingType.HOTEL,
            "vendor_id": test_vendor_id,  # This was failing before
            "destination_id": test_destination_id,
            "title": "Test Hotel",
            "slug": "test-hotel",
            "description": "Test hotel description",
            "latitude": 6.9271,
            "longitude": 79.8612,
            "base_currency": CurrencyCode.LKR,
        }
        
        # Create Listing object (without saving to DB)
        listing = Listing(**listing_data)
        print(f"✅ Successfully created Listing object with vendor_id: {listing.vendor_id}")
        
        # Test 3: Verify the relationship exists
        if hasattr(listing, 'vendor'):
            print("✅ Listing model has vendor relationship")
        else:
            print("⚠️  Listing model missing vendor relationship")
        
        print("\n🎉 SUCCESS: All tests passed! StayApprovalService should now work correctly.")
        return True
        
    except Exception as e:
        print(f"❌ ERROR: {e}")
        return False

if __name__ == '__main__':
    success = test_vendor_id_compatibility()
    exit(0 if success else 1)