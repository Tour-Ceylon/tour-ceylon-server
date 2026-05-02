#!/usr/bin/env python3
"""
Unit test to verify the datetime serialization fix works correctly.
Tests the repository serialization logic directly.
"""

import json
import sys
import os
from datetime import datetime
from decimal import Decimal

# Add the app directory to the path so we can import modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'app'))

from app.repositories.booking_inquiry_repo import BookingInquiryRepository
from app.schemas.booking_inquiry_schema import BookingInquiryCreate, CartItemSchema
from app.models.enum import CurrencyCode

def test_datetime_serialization():
    """Test that datetime objects in cart items are properly serialized"""
    
    print("🧪 Testing datetime serialization logic...")
    
    # Create a mock repository to test the serialization method
    repo = BookingInquiryRepository(None)  # We only need the serialization method
    
    # Create test cart items with datetime objects (simulating what Pydantic creates)
    test_cart_items = [
        CartItemSchema(
            listingId="90b9ff61-57bb-4045-9bb9-7b415f43de3d",
            title="Mandarina Colombo",
            travelDate=datetime(2026, 4, 10, 9, 0, 0),
            travelCount=2,
            price=Decimal('7000'),
            baseCurrency=CurrencyCode.LKR
        ),
        CartItemSchema(
            listingId="46803504-65fe-4fda-a523-0572196385c2", 
            title="shoneeeee",
            travelDate=datetime(2026, 4, 10, 9, 0, 0),
            travelCount=2,
            price=Decimal('5000'),
            baseCurrency=CurrencyCode.LKR
        )
    ]
    
    print(f"📋 Original cart items:")
    for i, item in enumerate(test_cart_items):
        print(f"  Item {i+1}: {item.title}")
        print(f"    Travel Date: {item.travel_date} (Type: {type(item.travel_date).__name__})")
        print(f"    Price: {item.price} (Type: {type(item.price).__name__})")
    
    # Test the serialization method
    try:
        serialized_items = repo._serialize_cart_items(test_cart_items)
        print(f"\n✅ Serialization successful!")
        print(f"📄 Serialized cart items:")
        
        for i, item in enumerate(serialized_items):
            print(f"  Item {i+1}: {item['title']}")
            print(f"    Travel Date: {item['travel_date']} (Type: {type(item['travel_date']).__name__})")
            print(f"    Price: {item['price']} (Type: {type(item['price']).__name__})")
        
        # Test that the result can be JSON serialized (the key test!)
        json_str = json.dumps(serialized_items)
        print(f"\n✅ JSON serialization successful!")
        print(f"📝 JSON length: {len(json_str)} characters")
        
        # Test that we can parse it back
        parsed_items = json.loads(json_str)
        print(f"✅ JSON deserialization successful!")
        
        # Verify the datetime was properly converted to ISO string
        first_item = parsed_items[0]
        travel_date_str = first_item['travel_date']
        print(f"🕒 Travel date in JSON: {travel_date_str}")
        
        # Test that we can convert it back to datetime
        parsed_datetime = datetime.fromisoformat(travel_date_str)
        print(f"✅ Datetime parsing successful: {parsed_datetime}")
        
        return True
        
    except Exception as e:
        print(f"❌ FAILED: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

def test_full_inquiry_creation():
    """Test creating a full booking inquiry with the serialization fix"""
    
    print("\n🧪 Testing full booking inquiry creation logic...")
    
    try:
        # Create a booking inquiry data object
        inquiry_data = BookingInquiryCreate(
            firstName="Umesh",
            lastName="Rasanjana", 
            email="sshone.work@gmail.com",
            phone="+94753110462",
            nationality="daw",
            emergencyContact="dwa",
            numberOfTravelers=2,
            specialRequests="daw",
            cartItems=[
                CartItemSchema(
                    listingId="90b9ff61-57bb-4045-9bb9-7b415f43de3d",
                    title="Mandarina Colombo",
                    travelDate=datetime(2026, 4, 10, 9, 0, 0),
                    travelCount=2,
                    price=Decimal('7000'),
                    baseCurrency=CurrencyCode.LKR
                ),
                CartItemSchema(
                    listingId="46803504-65fe-4fda-a523-0572196385c2", 
                    title="shoneeeee",
                    travelDate=datetime(2026, 4, 10, 9, 0, 0),
                    travelCount=2,
                    price=Decimal('5000'),
                    baseCurrency=CurrencyCode.LKR
                )
            ],
            subtotal=Decimal('12000'),
            total=Decimal('13440'),
            currency=CurrencyCode.LKR
        )
        
        print("✅ BookingInquiryCreate object created successfully!")
        
        # Test model_dump to see what Pydantic produces
        inquiry_dict = inquiry_data.model_dump()
        print(f"📋 Pydantic model_dump keys: {list(inquiry_dict.keys())}")
        
        # Check the cart_items specifically
        cart_items = inquiry_dict['cart_items']
        print(f"🛒 Cart items type: {type(cart_items)} (length: {len(cart_items)})")
        
        for i, item in enumerate(cart_items):
            print(f"  Item {i+1}: {item['title']}")
            print(f"    Travel Date: {item['travel_date']} (Type: {type(item['travel_date']).__name__})")
        
        # Test our serialization fix
        repo = BookingInquiryRepository(None)
        serialized_cart_items = repo._serialize_cart_items(cart_items)
        
        print("✅ Cart items serialized successfully!")
        
        # Test JSON serialization of the entire object
        inquiry_dict['cart_items'] = serialized_cart_items
        json_str = json.dumps(inquiry_dict, default=str)
        print("✅ Full inquiry JSON serialization successful!")
        print(f"📝 JSON length: {len(json_str)} characters")
        
        return True
        
    except Exception as e:
        print(f"❌ FAILED: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("=" * 70)
    print("🔧 DATETIME SERIALIZATION UNIT TESTS")
    print("=" * 70)
    
    test1_passed = test_datetime_serialization()
    test2_passed = test_full_inquiry_creation()
    
    print("\n" + "=" * 70)
    print("📊 TEST RESULTS:")
    print(f"  Test 1 (Datetime Serialization): {'✅ PASSED' if test1_passed else '❌ FAILED'}")
    print(f"  Test 2 (Full Inquiry Creation): {'✅ PASSED' if test2_passed else '❌ FAILED'}")
    
    if test1_passed and test2_passed:
        print("\n🎉 ALL TESTS PASSED! The datetime serialization fix is working correctly.")
    else:
        print("\n💥 SOME TESTS FAILED! The fix needs more work.")
    
    print("=" * 70)