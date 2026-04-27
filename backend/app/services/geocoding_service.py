"""
SevaSetu — Geocoding Service
Google Maps Geocoding + Distance Matrix integration.
"""

import logging
import math
from typing import Optional, Tuple

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class GeocodingService:
    """Google Maps geocoding and distance calculation."""

    # In-memory cache: (origin_rounded, dest_rounded) → travel_time_minutes
    _travel_time_cache: dict = {}

    def __init__(self):
        self._client = None
        if settings.GOOGLE_MAPS_API_KEY:
            try:
                import googlemaps
                self._client = googlemaps.Client(key=settings.GOOGLE_MAPS_API_KEY)
                logger.info("✅ Google Maps client initialized")
            except Exception as e:
                logger.warning(f"⚠️ Google Maps init failed: {e}")

    @property
    def is_available(self) -> bool:
        """Whether Google Maps API is configured and usable."""
        return self._client is not None

    async def geocode(self, location_text: str) -> Optional[Tuple[float, float]]:
        """Convert a location string to lat/lng coordinates."""
        if not self._client:
            return self._fallback_geocode(location_text)

        try:
            import asyncio
            result = await asyncio.to_thread(
                self._client.geocode, location_text, region="in"
            )
            if result:
                loc = result[0]["geometry"]["location"]
                return (loc["lat"], loc["lng"])
            return None
        except Exception as e:
            logger.error(f"Geocoding failed for '{location_text}': {e}")
            return None

    async def get_travel_time(
        self, origin: Tuple[float, float], destination: Tuple[float, float]
    ) -> Optional[int]:
        """Google Distance Matrix → travel time in minutes. Cached by rounded coordinates."""
        # Cache key: round to 3 decimal places (~100m precision)
        cache_key = (
            round(origin[0], 3), round(origin[1], 3),
            round(destination[0], 3), round(destination[1], 3),
        )
        if cache_key in self._travel_time_cache:
            return self._travel_time_cache[cache_key]

        if not self._client:
            result = self._fallback_travel_time(origin, destination)
            self._travel_time_cache[cache_key] = result
            return result

        try:
            import asyncio
            result = await asyncio.to_thread(
                self._client.distance_matrix,
                origins=[origin],
                destinations=[destination],
                mode="driving",
                region="in",
            )
            element = result["rows"][0]["elements"][0]
            if element["status"] == "OK":
                minutes = element["duration"]["value"] // 60
                self._travel_time_cache[cache_key] = minutes
                return minutes
            return None
        except Exception as e:
            logger.error(f"Distance Matrix failed: {e}")
            return None

    async def reverse_geocode(self, lat: float, lng: float) -> Optional[str]:
        """Convert lat/lng → human-readable address."""
        if not self._client:
            return f"Location ({lat:.4f}, {lng:.4f})"

        try:
            import asyncio
            result = await asyncio.to_thread(
                self._client.reverse_geocode, (lat, lng)
            )
            if result:
                return result[0]["formatted_address"]
            return None
        except Exception as e:
            logger.error(f"Reverse geocoding failed: {e}")
            return None

    # ─── Fallbacks ───────────────────────────────────────────

    def _fallback_geocode(self, location_text: str) -> Optional[Tuple[float, float]]:
        """Known Indian city coordinates for dev without API key."""
        known = {
            "mumbai": (19.0760, 72.8777),
            "delhi": (28.7041, 77.1025),
            "bangalore": (12.9716, 77.5946),
            "bengaluru": (12.9716, 77.5946),
            "chennai": (13.0827, 80.2707),
            "kolkata": (22.5726, 88.3639),
            "hyderabad": (17.3850, 78.4867),
            "pune": (18.5204, 73.8567),
            "ahmedabad": (23.0225, 72.5714),
            "jaipur": (26.9124, 75.7873),
            "lucknow": (26.8467, 80.9462),
            "dharavi": (19.0432, 72.8526),
            "andheri": (19.1197, 72.8464),
            "bandra": (19.0596, 72.8295),
        }
        text_lower = location_text.lower()
        for city, coords in known.items():
            if city in text_lower:
                return coords
        return (19.0760, 72.8777)

    def _fallback_travel_time(
        self, origin: Tuple[float, float], destination: Tuple[float, float]
    ) -> int:
        """Haversine distance × city speed (20 km/h avg)."""
        lat1, lon1 = origin
        lat2, lon2 = destination
        R = 6371
        dlat = math.radians(lat2 - lat1)
        dlon = math.radians(lon2 - lon1)
        a = (
            math.sin(dlat / 2) ** 2
            + math.cos(math.radians(lat1))
            * math.cos(math.radians(lat2))
            * math.sin(dlon / 2) ** 2
        )
        c = 2 * math.asin(math.sqrt(a))
        distance_km = R * c
        return max(1, int(distance_km / 20 * 60))


# Singleton
geocoding_service = GeocodingService()
