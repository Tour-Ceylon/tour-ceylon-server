import httpx

url = "https://tour-ceylon-server.vercel.app/api/v1/listings/"
print(f"Testing remote backend URL: {url}")

try:
    response = httpx.get(url, timeout=10.0)
    print(f"Status Code: {response.status_code}")
    print(f"Response: {response.text[:300]}")
except Exception as e:
    print(f"Error: {e}")
