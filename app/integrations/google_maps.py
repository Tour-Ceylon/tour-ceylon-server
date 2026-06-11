import os
import httpx
from typing import Optional, Dict

class GoogleMapsService:
    def __init__(self):
        self.api_key = os.getenv("google-api")
        self.base_url = "https://maps.googleapis.com/maps/api/distancematrix/json"

    async def get_distance_matrix(self, origin: str, destination: str) -> Optional[Dict]:
        """
        Get distance and duration between two points using Google Distance Matrix API.
        origin and destination can be "lat,lng" or place names.
        """
        if not self.api_key:
            return None

        params = {
            "origins": origin,
            "destinations": destination,
            "key": self.api_key
        }

        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(self.base_url, params=params)
                data = response.json()

                if data["status"] == "OK":
                    element = data["rows"][0]["elements"][0]
                    if element["status"] == "OK":
                        return {
                            "distance_km": element["distance"]["value"] / 1000.0,
                            "distance_text": element["distance"]["text"],
                            "duration_minutes": int(element["duration"]["value"] / 60),
                            "duration_text": element["duration"]["text"]
                        }
        except Exception as e:
            # In a real app, we would log this properly
            print(f"Google Maps API error: {e}")
        
        return None

google_maps_service = GoogleMapsService()
