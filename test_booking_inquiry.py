#!/usr/bin/env python3
"""
Test script for booking inquiry endpoint to debug 422 errors
"""
import json
import requests
from datetime import datetime

# Test payload matching the exact format from requirements
test_payload = {
    "firstName": "John",
    "lastName": "Doe",
    "email": "john@example.com", 
    "phone": "+1234567890",
    "nationality": "American",
    "emergencyContact": "Jane Doe +9876543210",
    "numberOfTravelers": 2,
    "specialRequests": "Vegetarian meals preferred",
    "cartItems": [
        {
            "listingId": "listing-123",
            "title": "Sigiriya Rock Fortress Tour",
            "travelDate": "2024-06-15T09:00:00",
            "travelCount": 2,
            "price": 150.00,
            "baseCurrency": "USD"
        }
    ],
    "subtotal": 300.00,
    "total": 336.00,
    "currency": "USD"
}

def test_booking_inquiry():
    """Test the booking inquiry endpoint"""
    url = "http://localhost:8000/api/v1/booking-inquiries/"
    
    headers = {
        "Content-Type": "application/json"
    }
    
    print("Testing booking inquiry endpoint...")
    print(f"URL: {url}")
    print(f"Payload: {json.dumps(test_payload, indent=2)}")
    print("-" * 50)
    
    try:
        response = requests.post(url, json=test_payload, headers=headers)
        
        print(f"Status Code: {response.status_code}")
        print(f"Response Headers: {dict(response.headers)}")
        print(f"Response Body: {response.text}")
        
        if response.status_code == 201:
            print("✅ SUCCESS: Booking inquiry created successfully!")
            data = response.json()
            print(f"Inquiry Reference: {data.get('reference')}")
            print(f"Inquiry ID: {data.get('id')}")
            print(f"Status: {data.get('status')}")
        elif response.status_code == 422:
            print("❌ VALIDATION ERROR (422):")
            try:
                error_data = response.json()
                if isinstance(error_data.get('detail'), dict) and 'errors' in error_data['detail']:
                    print("Validation errors:")
                    for error in error_data['detail']['errors']:
                        print(f"  - Field: {error.get('loc', ['unknown'])}")
                        print(f"    Message: {error.get('msg', 'Unknown error')}")
                        print(f"    Input: {error.get('input', 'N/A')}")
                        print()
                else:
                    print(f"Error detail: {error_data}")
            except Exception as e:
                print(f"Could not parse error response: {e}")
        else:
            print(f"❌ ERROR {response.status_code}:")
            print(response.text)
            
    except requests.exceptions.ConnectionError:
        print("❌ CONNECTION ERROR: Could not connect to server.")
        print("Make sure the server is running on http://localhost:8000")
    except Exception as e:
        print(f"❌ UNEXPECTED ERROR: {e}")

if __name__ == "__main__":
    test_booking_inquiry()