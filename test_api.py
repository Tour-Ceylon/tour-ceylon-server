import requests
import json

url = "http://127.0.0.1:8000/api/v1/packages/88888888-8888-8888-8888-888888888808"
response = requests.get(url)

print("Status Code:", response.status_code)
if response.status_code == 200:
    print(json.dumps(response.json(), indent=2))
else:
    print(response.text)
