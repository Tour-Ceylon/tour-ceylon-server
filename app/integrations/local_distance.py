import math
import re
from typing import Dict, Optional, Tuple


Location = Tuple[float, float]

KNOWN_LOCATIONS: Dict[str, Location] = {
    "colombo bandaranaike airport": (7.1808, 79.8841),
    "cmb": (7.1808, 79.8841),
    "bandaranaike international airport": (7.1808, 79.8841),
    "colombo fort": (6.9344, 79.8428),
    "colombo city centre": (6.9170, 79.8636),
    "colombo": (6.9271, 79.8612),
    "kandy city": (7.2906, 80.6337),
    "kandy": (7.2906, 80.6337),
    "galle fort": (6.0269, 80.2170),
    "galle": (6.0535, 80.2210),
    "ella town": (6.8667, 81.0466),
    "ella": (6.8667, 81.0466),
    "negombo beach": (7.2083, 79.8358),
    "negombo": (7.2083, 79.8358),
    "bentota": (6.4214, 79.9950),
    "hikkaduwa": (6.1395, 80.1063),
    "mirissa": (5.9483, 80.4716),
    "weligama": (5.9750, 80.4297),
    "sigiriya": (7.9570, 80.7603),
    "dambulla": (7.8731, 80.6511),
    "nuwara eliya": (6.9497, 80.7891),
    "yala national park": (6.3725, 81.5207),
}


def _normalize(value: str) -> str:
    normalized = value.lower()
    normalized = re.sub(r"\([^)]*\)", " ", normalized)
    normalized = normalized.replace("/", " ")
    normalized = re.sub(r"[^a-z0-9\s.-]", " ", normalized)
    return re.sub(r"\s+", " ", normalized).strip()


def _parse_lat_lng(value: str) -> Optional[Location]:
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


def resolve_location(value: str) -> Optional[Location]:
    coordinate = _parse_lat_lng(value)
    if coordinate:
        return coordinate

    normalized = _normalize(value)
    if normalized in KNOWN_LOCATIONS:
        return KNOWN_LOCATIONS[normalized]

    for key, location in KNOWN_LOCATIONS.items():
        if key in normalized or normalized in key:
            return location

    return None


def estimate_distance_matrix(origin: str, destination: str) -> Optional[dict]:
    origin_location = resolve_location(origin)
    destination_location = resolve_location(destination)
    if not origin_location or not destination_location:
        return None

    straight_km = _haversine_km(origin_location, destination_location)
    road_km = max(3.0, straight_km * 1.28)
    duration_minutes = max(10, round((road_km / 42.0) * 60))

    return {
        "distance_km": round(road_km, 1),
        "distance_text": f"{round(road_km, 1)} km",
        "duration_minutes": duration_minutes,
        "duration_text": _format_duration(duration_minutes),
    }


def _haversine_km(origin: Location, destination: Location) -> float:
    lat1, lon1 = origin
    lat2, lon2 = destination
    radius_km = 6371.0

    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(math.radians(lat1))
        * math.cos(math.radians(lat2))
        * math.sin(dlon / 2) ** 2
    )
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return radius_km * c


def _format_duration(minutes: int) -> str:
    hours = minutes // 60
    remaining = minutes % 60
    if hours and remaining:
        return f"{hours} hour {remaining} mins"
    if hours:
        return f"{hours} hour"
    return f"{remaining} mins"
