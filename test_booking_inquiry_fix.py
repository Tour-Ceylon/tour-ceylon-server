#!/usr/bin/env python3
"""
Test script to verify the booking inquiry datetime serialization fix.
This test reproduces the exact scenario from the error log.
"""

import json
import requests
from datetime import datetime
from decimal import Decimal

def test_booking_inquiry_creation():
    """Test the exact scenario that was causing the JSON serialization error"""
    
    # This is the exact payload from your error log
    test_payload = {
        "firstName": "Umesh",
        "lastName": "Rasanjana", 
        "email": "sshone.work@gmail.com",
        "phone": "+94753110462",
        "nationality": "daw",
        "emergencyContact": "dwa",
        "numberOfTravelers": 2,
        "specialRequests": "daw",
        "cartItems": [
            {
                "listingId": "90b9ff61-57bb-4045-9bb9-7b415f43de3d",
                "title": "Mandarina Colombo",
                "travelDate": "2026-04-10T09:00:00",
                "travelCount": 2,
                "price": 7000,
                "baseCurrency": "LKR"
            },
            {
                "listingId": "46803504-65fe-4fda-a523-0572196385c2", 
                "title": "shoneeeee",
                "travelDate": "2026-04-10T09:00:00",
                "travelCount": 2,
                "price": 5000,
                "baseCurrency": "LKR"
            }
        ],
        "subtotal": 12000,
        "total": 13440,
        "currency": "LKR"
    }

    print("🧪 Testing booking inquiry creation with datetime objects...")
    print(f"📋 Payload: {json.dumps(test_payload, indent=2)}")
    
    try:
        # Test against local server
        url = "http://localhost:8000/api/v1/booking-inquiries/"
        headers = {"Content-Type": "application/json"}
        
        print(f"🚀 Sending POST request to {url}")
        response = requests.post(url, json=test_payload, headers=headers, timeout=10)
        
        print(f"📊 Response Status: {response.status_code}")
        print(f"📄 Response Headers: {dict(response.headers)}")
        
        if response.status_code == 201:
            response_data = response.json()
            print("✅ SUCCESS: Booking inquiry created successfully!")
            print(f"📝 Response: {json.dumps(response_data, indent=2, default=str)}")
            
            # Test retrieval to verify datetime deserialization works
            inquiry_id = response_data.get('id')
            if inquiry_id:
                print(f"\n🔍 Testing retrieval of inquiry {inquiry_id}...")
                get_response = requests.get(f"{url}{inquiry_id}", timeout=10)
                if get_response.status_code == 200:
                    retrieved_data = get_response.json()
                    print("✅ SUCCESS: Booking inquiry retrieved successfully!")
                    
                    # Check if cart items have proper datetime objects
                    for item in retrieved_data.get('cartItems', []):
                        travel_date = item.get('travelDate')
                        print(f"📅 Travel Date: {travel_date} (Type: {type(travel_date).__name__})")
                else:
                    print(f"❌ FAILED to retrieve inquiry: {get_response.status_code}")
                    print(get_response.text)
                    
        else:
            print("❌ FAILED: Booking inquiry creation failed!")
            print(f"Error Response: {response.text}")
            
            # Try to parse error details
            try:
                error_data = response.json()
                print(f"Error Details: {json.dumps(error_data, indent=2)}")
            except:
                pass
                
    except requests.exceptions.ConnectionError:
        print("❌ CONNECTION ERROR: Could not connect to server.")
        print("Make sure the server is running on http://localhost:8000")
        
    except Exception as e:
        print(f"❌ UNEXPECTED ERROR: {str(e)}")

if __name__ == "__main__":
    print("=" * 60)
    print("🔧 BOOKING INQUIRY DATETIME SERIALIZATION FIX TEST")
    print("=" * 60)
    test_booking_inquiry_creation()
    print("=" * 60)