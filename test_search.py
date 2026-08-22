from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

url = "/api/v1/listings/search?listing_type=hotel&adults=2&children=0&rooms=1&is_active=true&page=1&per_page=100&status=published"
print(f"Calling endpoint: {url}")
response = client.get(url)

print(f"Status Code: {response.status_code}")
try:
    print("Response JSON:", response.json())
except Exception:
    print("Response Text:", response.text)
