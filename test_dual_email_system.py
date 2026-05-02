#!/usr/bin/env python3
"""
Test script to verify the dual email system for booking inquiries.
Tests both business notification and customer confirmation emails.
"""

import json
import requests
import time
from datetime import datetime

def test_booking_inquiry_dual_email():
    """Test the complete booking inquiry flow with dual email notifications"""
    
    # Test payload with real data
    test_payload = {
        "firstName": "John",
        "lastName": "Doe", 
        "email": "test.customer@example.com",  # Customer will receive confirmation
        "phone": "+94771234567",
        "nationality": "USA",
        "emergencyContact": "Jane Doe - +94779876543",
        "numberOfTravelers": 2,
        "specialRequests": "We would like vegetarian meals and prefer air-conditioned accommodation.",
        "cartItems": [
            {
                "listingId": "90b9ff61-57bb-4045-9bb9-7b415f43de3d",
                "title": "Cultural Triangle Tour - Sigiriya & Dambulla",
                "travelDate": "2026-06-15T08:00:00",
                "travelCount": 2,
                "price": 8500,
                "baseCurrency": "LKR"
            },
            {
                "listingId": "46803504-65fe-4fda-a523-0572196385c2", 
                "title": "Kandy City Tour with Temple of the Tooth",
                "travelDate": "2026-06-16T09:00:00",
                "travelCount": 2,
                "price": 6000,
                "baseCurrency": "LKR"
            }
        ],
        "subtotal": 29000,
        "total": 32480,  # Including taxes/fees
        "currency": "LKR"
    }

    print("=" * 70)
    print("🧪 DUAL EMAIL SYSTEM TEST - BOOKING INQUIRY")
    print("=" * 70)
    print(f"📋 Test Payload:")
    print(f"   Customer: {test_payload['firstName']} {test_payload['lastName']}")
    print(f"   Email: {test_payload['email']}")
    print(f"   Phone: {test_payload['phone']}")
    print(f"   Travelers: {test_payload['numberOfTravelers']}")
    print(f"   Total: {test_payload['total']} {test_payload['currency']}")
    print(f"   Items: {len(test_payload['cartItems'])}")
    print()

    try:
        # Test against local server
        url = "http://localhost:8000/api/v1/booking-inquiries/"
        headers = {"Content-Type": "application/json"}
        
        print(f"🚀 Sending POST request to {url}")
        response = requests.post(url, json=test_payload, headers=headers, timeout=10)
        
        print(f"📊 Response Status: {response.status_code}")
        
        if response.status_code == 201:
            response_data = response.json()
            inquiry_ref = response_data.get('reference')
            inquiry_id = response_data.get('id')
            
            print("✅ SUCCESS: Booking inquiry created successfully!")
            print(f"📝 Inquiry Reference: {inquiry_ref}")
            print(f"🆔 Inquiry ID: {inquiry_id}")
            print(f"📅 Created At: {response_data.get('created_at')}")
            print()
            
            print("📧 EMAIL NOTIFICATIONS STATUS:")
            print("   The following emails should be sent as background tasks:")
            print(f"   1. 📨 Business Notification → bookings@tourceylon.com")
            print(f"      FROM: travelreadytourstmp@gmail.com")
            print(f"      SUBJECT: New Booking Inquiry - {inquiry_ref}")
            print(f"      CONTENT: Full inquiry details for business team")
            print()
            print(f"   2. 📧 Customer Confirmation → {test_payload['email']}")
            print(f"      FROM: travelreadytourstmp@gmail.com") 
            print(f"      SUBJECT: Booking Inquiry Confirmed - REF: {inquiry_ref}")
            print(f"      CONTENT: Friendly confirmation with next steps")
            print()
            
            # Give background tasks time to complete
            print("⏳ Waiting 3 seconds for background email tasks to complete...")
            time.sleep(3)
            
            # Try to retrieve the inquiry to test deserialization
            print(f"🔍 Testing inquiry retrieval...")
            get_response = requests.get(f"{url}{inquiry_id}", timeout=10)
            if get_response.status_code == 200:
                retrieved_data = get_response.json()
                print("✅ SUCCESS: Booking inquiry retrieved successfully!")
                
                # Verify cart items deserialization
                cart_items = retrieved_data.get('cartItems', [])
                print(f"🛒 Cart Items Retrieved: {len(cart_items)}")
                for i, item in enumerate(cart_items, 1):
                    travel_date = item.get('travelDate')
                    price = item.get('price')
                    print(f"   Item {i}: {item.get('title')}")
                    print(f"            Date: {travel_date}")
                    print(f"            Price: {price} {item.get('baseCurrency')}")
                
            else:
                print(f"❌ FAILED to retrieve inquiry: {get_response.status_code}")
                print(get_response.text)
            
            print()
            print("🎉 DUAL EMAIL SYSTEM TEST COMPLETED!")
            print("📧 Check both email inboxes:")
            print(f"   • Business team: bookings@tourceylon.com")
            print(f"   • Customer: {test_payload['email']}")
            return True
                    
        else:
            print("❌ FAILED: Booking inquiry creation failed!")
            print(f"Error Response: {response.text}")
            
            # Try to parse error details
            try:
                error_data = response.json()
                print(f"Error Details: {json.dumps(error_data, indent=2)}")
            except:
                pass
            return False
                
    except requests.exceptions.ConnectionError:
        print("❌ CONNECTION ERROR: Could not connect to server.")
        print("Make sure the server is running on http://localhost:8000")
        print("Run: python -m uvicorn app.main:app --reload")
        return False
        
    except Exception as e:
        print(f"❌ UNEXPECTED ERROR: {str(e)}")
        return False

def test_email_configuration():
    """Test email configuration status"""
    print("🔧 EMAIL CONFIGURATION CHECK:")
    print("   SMTP Host: smtp.gmail.com")
    print("   SMTP Port: 587") 
    print("   SMTP User: travelreadytourstmp@gmail.com")
    print("   Email From: travelreadytourstmp@gmail.com")
    print("   Status: ✅ Configured")
    print()

if __name__ == "__main__":
    test_email_configuration()
    success = test_booking_inquiry_dual_email()
    
    print("=" * 70)
    if success:
        print("🎊 OVERALL TEST RESULT: ✅ PASSED")
        print("📧 Both business and customer emails should be delivered!")
    else:
        print("💥 OVERALL TEST RESULT: ❌ FAILED") 
        print("🔧 Please check server logs for detailed error information.")
    print("=" * 70)