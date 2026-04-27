"""
SevaSetu — Match Explanation Cache
In-memory TTL cache for LLM match explanations.
No Redis dependency — works standalone.

Cache key: "{need_id}:{volunteer_id}"
TTL: 30 minutes (configurable)
"""

import logging
import time
from typing import Dict, Any, Optional, Tuple

logger = logging.getLogger(__name__)

# Default TTL: 30 minutes
DEFAULT_TTL_SECONDS = 1800


class MatchCache:
    """Thread-safe in-memory cache with TTL expiry for match explanations."""

    def __init__(self, ttl: int = DEFAULT_TTL_SECONDS, max_size: int = 500):
        self._cache: Dict[str, Tuple[float, Dict[str, Any]]] = {}  # key → (expiry_ts, data)
        self._ttl = ttl
        self._max_size = max_size

    def _key(self, need_id: str, volunteer_id: str) -> str:
        return f"{need_id}:{volunteer_id}"

    def get(self, need_id: str, volunteer_id: str) -> Optional[Dict[str, Any]]:
        """Get cached explanation. Returns None if expired or missing."""
        key = self._key(need_id, volunteer_id)
        entry = self._cache.get(key)
        if entry is None:
            return None
        expiry, data = entry
        if time.time() > expiry:
            del self._cache[key]
            return None
        return data

    def set(self, need_id: str, volunteer_id: str, data: Dict[str, Any]) -> None:
        """Cache an explanation with TTL."""
        # Evict expired entries if cache is getting large
        if len(self._cache) >= self._max_size:
            self._evict_expired()
        # If still too large, evict oldest
        if len(self._cache) >= self._max_size:
            oldest_key = min(self._cache, key=lambda k: self._cache[k][0])
            del self._cache[oldest_key]

        key = self._key(need_id, volunteer_id)
        self._cache[key] = (time.time() + self._ttl, data)

    def invalidate(self, need_id: str, volunteer_id: str) -> None:
        """Remove a specific cache entry."""
        key = self._key(need_id, volunteer_id)
        self._cache.pop(key, None)

    def invalidate_need(self, need_id: str) -> None:
        """Remove all cached entries for a specific need."""
        prefix = f"{need_id}:"
        keys_to_remove = [k for k in self._cache if k.startswith(prefix)]
        for k in keys_to_remove:
            del self._cache[k]

    def clear(self) -> None:
        """Clear entire cache."""
        self._cache.clear()

    def _evict_expired(self) -> None:
        """Remove all expired entries."""
        now = time.time()
        expired = [k for k, (exp, _) in self._cache.items() if now > exp]
        for k in expired:
            del self._cache[k]

    @property
    def size(self) -> int:
        return len(self._cache)


# ── Singleton ────────────────────────────────────────────────
match_cache = MatchCache()
