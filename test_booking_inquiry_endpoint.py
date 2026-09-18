import requests
import json

url = "http://localhost:8000/api/v1/booking-inquiries/"

payload = {
    "firstName": "John",
    "lastName": "Doe",
    "email": "john.doe@example.com",
    "phone": "+1234567890",
    "nationality": "American",
    "numberOfTravelers": 2,
    "cartItems": [
        {
            "listingId": "013b5155-bf0e-4b2a-99e3-bbd95e106573",
            "title": "Araliya Green Hills",
            "travelDate": "2026-08-27 to 2026-08-28",
            "travelCount": 2,
            "price": 340.0,
            "baseCurrency": "USD"
        }
    ],
    "subtotal": 340.0,
    "total": 381.0,
    "currency": "USD"
}

print("==================================================")
print("TESTING POST /api/v1/booking-inquiries/")
print("==================================================")

try:
    res = requests.post(url, json=payload)
    print(f"Status Code: {res.status_code}")
    print("Response JSON:")
    print(json.dumps(res.json(), indent=2))
except Exception as e:
    print(f"Error: {e}")
