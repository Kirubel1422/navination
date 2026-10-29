"""Find physical service centres (Amer, Tasheel, Tadbeer, typing centres, customer happiness
centres...) near a person, from OpenStreetMap data via the public Photon geocoder (no key).

The person's location is used only for this request: it biases the search and ranks results by
straight-line distance. It is never stored. Results carry coordinates so the browser can open
Google Maps directions; the agent may only return centres that came from this tool.
"""

import math
import threading
import time
from dataclasses import dataclass

import httpx

from app.agent.web import USER_AGENT

PHOTON_URL = "https://photon.komoot.io/api/"
CACHE_TTL_SECONDS = 6 * 3600
MAX_RESULTS = 8
# Emirate capitals: the search bias when the person has not shared their location.
EMIRATE_CENTRES = {
    "abu_dhabi": (24.4539, 54.3773),
    "dubai": (25.2048, 55.2708),
    "sharjah": (25.3463, 55.4209),
    "ajman": (25.4052, 55.5136),
    "umm_al_quwain": (25.5647, 55.5552),
    "ras_al_khaimah": (25.8007, 55.9762),
    "fujairah": (25.1288, 56.3265),
}
# OSM categories that are never a government service counter.
_SKIP_VALUES = {"bus_stop", "bakery", "restaurant", "cafe", "fast_food", "dentist", "parking"}


class PlacesError(Exception):
    pass


@dataclass(frozen=True)
class Place:
    id: str
    name: str
    kind: str
    address: str
    lat: float
    lng: float
    distance_km: float | None


def distance_km(a: tuple[float, float], b: tuple[float, float]) -> float:
    lat1, lon1, lat2, lon2 = map(math.radians, (*a, *b))
    h = (
        math.sin((lat2 - lat1) / 2) ** 2
        + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2
    )
    return 6371.0 * 2 * math.asin(math.sqrt(h))


def _address(props: dict[str, object]) -> str:
    parts = [
        props.get(k) for k in ("housenumber", "street", "district", "locality", "city", "state")
    ]
    seen: list[str] = []
    for part in parts:
        if isinstance(part, str) and part and part not in seen:
            seen.append(part)
    return ", ".join(seen)


class Places:
    def __init__(self, timeout_seconds: float, client: httpx.Client | None = None) -> None:
        self.client = client or httpx.Client(
            timeout=timeout_seconds,
            headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
        )
        self._cache: dict[str, tuple[float, list[dict[str, object]]]] = {}
        self._lock = threading.Lock()

    def _features(self, query: str, near: tuple[float, float]) -> list[dict[str, object]]:
        # Round the bias point (~1 km) so the exact position never leaves the server.
        lat, lng = round(near[0], 2), round(near[1], 2)
        key = f"{query.lower()}|{lat}|{lng}"
        with self._lock:
            cached = self._cache.get(key)
        if cached and time.monotonic() - cached[0] < CACHE_TTL_SECONDS:
            return cached[1]
        try:
            response = self.client.get(
                PHOTON_URL, params={"q": query, "lat": lat, "lon": lng, "limit": 15}
            )
            response.raise_for_status()
            features = response.json().get("features", [])
        except (httpx.HTTPError, ValueError) as exc:
            raise PlacesError(f"Place search failed: {type(exc).__name__}") from exc
        with self._lock:
            self._cache[key] = (time.monotonic(), features)
        return features

    def search(
        self, query: str, near: tuple[float, float], person: tuple[float, float] | None
    ) -> list[Place]:
        query = " ".join(query.split())[:100]
        if not query:
            raise PlacesError("Give a short place query, e.g. 'Tasheel' or 'Emirates ID'.")
        places: list[Place] = []
        for feature in self._features(query, near):
            props = feature.get("properties") or {}
            geometry = feature.get("geometry") or {}
            coords = geometry.get("coordinates") if isinstance(geometry, dict) else None
            if not isinstance(props, dict) or not isinstance(coords, list) or len(coords) != 2:
                continue
            if props.get("countrycode") != "AE" or not props.get("name"):
                continue
            if props.get("osm_value") in _SKIP_VALUES:
                continue
            lat, lng = float(coords[1]), float(coords[0])
            places.append(
                Place(
                    id=f"osm-{props.get('osm_type', 'x')}{props.get('osm_id', len(places))}",
                    name=str(props["name"])[:120],
                    kind=f"{props.get('osm_key', '')}:{props.get('osm_value', '')}",
                    address=_address(props)[:200],
                    lat=lat,
                    lng=lng,
                    distance_km=round(distance_km(person, (lat, lng)), 1) if person else None,
                )
            )
        if person:
            places.sort(key=lambda p: p.distance_km or 0.0)
        return places[:MAX_RESULTS]


_instance: Places | None = None


def get_places(timeout_seconds: float) -> Places:
    global _instance
    if _instance is None:
        _instance = Places(timeout_seconds)
    return _instance
