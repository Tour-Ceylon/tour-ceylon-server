import os
from typing import Dict, Optional, Tuple

import httpx


Coordinate = Tuple[float, float]


class GeoapifyRoutingService:
    def __init__(self):
        self.api_key = os.getenv("GEOAPIFY_API_KEY") or os.getenv("geoapify-api-key")
        self.geocode_url = "https://api.geoapify.com/v1/geocode/search"
        self.autocomplete_url = "https://api.geoapify.com/v1/geocode/autocomplete"
        self.routing_url = "https://api.geoapify.com/v1/routing"

    async def get_distance_matrix(self, origin: str, destination: str) -> Optional[Dict]:
        if not self.api_key:
            return None

        try:
            async with httpx.AsyncClient(timeout=8.0) as client:
                origin_coord = await self._resolve_location(client, origin)
                destination_coord = await self._resolve_location(client, destination)
                if not origin_coord or not destination_coord:
                    return None

                return await self._request_route(client, origin_coord, destination_coord)
        except Exception as exc:
            print(f"Geoapify routing error: {exc}")

        return None

    async def get_route_by_coordinates(
        self,
        origin: Coordinate,
        destination: Coordinate,
    ) -> Optional[Dict]:
        if not self.api_key:
            return None

        try:
            async with httpx.AsyncClient(timeout=8.0) as client:
                return await self._request_route(client, origin, destination)
        except Exception as exc:
            print(f"Geoapify coordinate routing error: {exc}")

        return None

    async def search_locations(self, query: str, limit: int = 6) -> list[Dict]:
        if not self.api_key or len(query.strip()) < 3:
            return []

        try:
            async with httpx.AsyncClient(timeout=6.0) as client:
                place_features = await self._autocomplete(client, query, "amenity", limit)
                city_features = await self._autocomplete(client, query, "city", 3)
                locality_features = await self._autocomplete(client, query, "locality", 3)

                features = self._dedupe_features(
                    place_features + city_features + locality_features
                )
                if len(features) < 3:
                    features = self._dedupe_features(
                        features + await self._autocomplete(client, query, None, limit)
                    )
        except Exception as exc:
            print(f"Geoapify location search error: {exc}")
            return []

        suggestions = []
        for feature in features:
            properties = feature.get("properties") or {}
            lat = properties.get("lat")
            lon = properties.get("lon")
            if lat is None or lon is None:
                continue

            result_type = properties.get("result_type")
            if result_type in {"street", "postcode"} and len(suggestions) >= 3:
                continue

            label = self._format_location_label(properties, query)
            if not label:
                continue

            suggestions.append(
                {
                    "label": label,
                    "lat": float(lat),
                    "lng": float(lon),
                    "place_id": properties.get("place_id"),
                    "city": properties.get("city") or properties.get("town") or properties.get("village"),
                    "district": properties.get("county") or properties.get("district") or result_type,
                    "country": properties.get("country"),
                }
            )
            if len(suggestions) >= limit:
                break

        return suggestions

    async def _autocomplete(
        self,
        client: httpx.AsyncClient,
        query: str,
        result_type: Optional[str],
        limit: int,
    ) -> list[Dict]:
        params = {
            "text": query,
            "filter": "countrycode:lk",
            "limit": limit,
            "apiKey": self.api_key,
        }
        if result_type:
            params["type"] = result_type

        response = await client.get(self.autocomplete_url, params=params)
        response.raise_for_status()
        data = response.json()
        return data.get("features") or []

    @staticmethod
    def _dedupe_features(features: list[Dict]) -> list[Dict]:
        seen = set()
        deduped = []
        for feature in features:
            properties = feature.get("properties") or {}
            key = (
                properties.get("place_id")
                or f"{properties.get('formatted')}|{properties.get('lat')}|{properties.get('lon')}"
            )
            if key in seen:
                continue
            seen.add(key)
            deduped.append(feature)
        return deduped

    @staticmethod
    def _format_location_label(properties: Dict, fallback: str) -> str:
        name = properties.get("name") or properties.get("address_line1")
        formatted = properties.get("formatted")
        result_type = properties.get("result_type")

        if name and result_type not in {"street", "postcode"}:
            return str(name).strip()

        if formatted:
            first_part = str(formatted).split(",", 1)[0].strip()
            if first_part and first_part.lower() != "unnamed road":
                return first_part

        return fallback.strip()

    async def _resolve_location(self, client: httpx.AsyncClient, value: str) -> Optional[Coordinate]:
        coordinate = self._parse_lat_lng(value)
        if coordinate:
            return coordinate

        response = await client.get(
            self.geocode_url,
            params={
                "text": value,
                "filter": "countrycode:lk",
                "limit": 1,
                "apiKey": self.api_key,
            },
        )
        response.raise_for_status()
        data = response.json()
        features = data.get("features") or []
        if not features:
            return None

        properties = features[0].get("properties") or {}
        lat = properties.get("lat")
        lon = properties.get("lon")
        if lat is None or lon is None:
            return None

        return float(lat), float(lon)

    async def _request_route(
        self,
        client: httpx.AsyncClient,
        origin: Coordinate,
        destination: Coordinate,
    ) -> Optional[Dict]:
        response = await client.get(
            self.routing_url,
            params={
                "waypoints": f"{origin[0]},{origin[1]}|{destination[0]},{destination[1]}",
                "mode": "drive",
                "apiKey": self.api_key,
            },
        )
        response.raise_for_status()
        data = response.json()
        features = data.get("features") or []
        if not features:
            return None

        properties = features[0].get("properties") or {}
        distance_meters = properties.get("distance")
        duration_seconds = properties.get("time")
        if distance_meters is None or duration_seconds is None:
            return None

        distance_km = float(distance_meters) / 1000.0
        duration_minutes = max(1, round(float(duration_seconds) / 60.0))

        return {
            "distance_km": round(distance_km, 3),
            "distance_text": f"{round(distance_km, 1)} km",
            "duration_minutes": duration_minutes,
            "duration_text": self._format_duration(duration_minutes),
        }

    @staticmethod
    def _parse_lat_lng(value: str) -> Optional[Coordinate]:
        parts = [part.strip() for part in value.split(",")]
        if len(parts) != 2:
            return None

        try:
            lat = float(parts[0])
            lng = float(parts[1])
        except ValueError:
            return None

        if -90 <= lat <= 90 and -180 <= lng <= 180:
            return lat, lng
        return None

    @staticmethod
    def _format_duration(minutes: int) -> str:
        hours = minutes // 60
        remaining = minutes % 60
        if hours and remaining:
            return f"{hours} hour {remaining} mins"
        if hours:
            return f"{hours} hour"
        return f"{remaining} mins"


geoapify_routing_service = GeoapifyRoutingService()
