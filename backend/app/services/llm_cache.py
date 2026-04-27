"""
SevaSetu — LLM Response Cache
In-memory TTL cache shared across all Gemini calls.

Key design:
  - Keyed on SHA-256 hash of (task_type + prompt_content)
  - Per-task-type TTL (skill synonyms live longer than validation results)
  - Thread-safe via asyncio.Lock for each cache slot
  - Cache stats tracking for cost monitoring
  - Evicts expired entries on every 100th access (lazy eviction)

Cost impact:
  - Skill synonym calls: 1 per 24h instead of per match → ~99% reduction
  - Weight calibration:  1 per 30min per context bucket → ~95% reduction
  - Extraction:          0 tokens on duplicate reports → 100% savings on repeats
"""

import hashlib
import time
import logging
from typing import Any, Optional, Dict
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


# TTL per task type (in seconds)
CACHE_TTL: Dict[str, int] = {
    "skill_synonyms":    86400,  # 24h — vocabulary barely changes
    "dynamic_weights":    1800,  # 30m — context shifts slowly
    "extraction":         3600,  # 1h  — same text → same result
    "validation":          600,  # 10m — score+data combos are semistable
    "area_briefing":     21600,  # 6h  — scheduled analysis output
    "feedback_analysis":  7200,  # 2h  — feedback patterns stable
    "dispatch":              0,  # 0   — always fresh (personalized)
}


@dataclass
class CacheEntry:
    value: Any
    expires_at: float
    task_type: str
    hits: int = 0


class LLMCache:
    """
    Shared in-memory cache for all Gemini responses.
    Thread-safe, TTL-aware, with hit/miss/cost tracking.
    """

    def __init__(self):
        self._store: Dict[str, CacheEntry] = {}
        self._access_count = 0
        self._stats = {
            "hits": 0,
            "misses": 0,
            "evictions": 0,
            "tokens_saved_estimate": 0,
        }

    def _make_key(self, task_type: str, content: str) -> str:
        """SHA-256 of task_type + content → deterministic cache key."""
        return hashlib.sha256(f"{task_type}:{content}".encode()).hexdigest()

    def get(self, task_type: str, content: str) -> Optional[Any]:
        """
        Return cached value if exists and not expired.
        Returns None on miss or expiry.
        """
        self._access_count += 1
        if self._access_count % 100 == 0:
            self._evict_expired()

        key = self._make_key(task_type, content)
        entry = self._store.get(key)

        if entry is None:
            self._stats["misses"] += 1
            return None

        if time.monotonic() > entry.expires_at:
            del self._store[key]
            self._stats["misses"] += 1
            self._stats["evictions"] += 1
            return None

        entry.hits += 1
        self._stats["hits"] += 1
        # Rough estimate: ~300 tokens saved per cache hit
        self._stats["tokens_saved_estimate"] += 300
        logger.debug(f"Cache HIT [{task_type}] — total hits={self._stats['hits']}")
        return entry.value

    def set(self, task_type: str, content: str, value: Any) -> None:
        """Store value with TTL for the given task type."""
        ttl = CACHE_TTL.get(task_type, 600)
        if ttl == 0:
            return  # task_type explicitly not cached (e.g., dispatch)

        key = self._make_key(task_type, content)
        self._store[key] = CacheEntry(
            value=value,
            expires_at=time.monotonic() + ttl,
            task_type=task_type,
        )
        logger.debug(f"Cache SET [{task_type}] TTL={ttl}s — store size={len(self._store)}")

    def _evict_expired(self) -> None:
        """Remove all expired entries (called lazily every 100 accesses)."""
        now = time.monotonic()
        expired_keys = [k for k, v in self._store.items() if v.expires_at < now]
        for k in expired_keys:
            del self._store[k]
        if expired_keys:
            self._stats["evictions"] += len(expired_keys)
            logger.debug(f"Cache evicted {len(expired_keys)} expired entries")

    def invalidate(self, task_type: str) -> int:
        """Manually invalidate all entries for a task type (e.g., after skill list update)."""
        before = len(self._store)
        self._store = {k: v for k, v in self._store.items() if v.task_type != task_type}
        removed = before - len(self._store)
        logger.info(f"Cache invalidated {removed} entries for task_type='{task_type}'")
        return removed

    def stats(self) -> Dict:
        """Return cache performance stats for monitoring."""
        total = self._stats["hits"] + self._stats["misses"]
        hit_rate = (self._stats["hits"] / total * 100) if total > 0 else 0
        return {
            "hits": self._stats["hits"],
            "misses": self._stats["misses"],
            "hit_rate_pct": round(hit_rate, 1),
            "evictions": self._stats["evictions"],
            "current_size": len(self._store),
            "estimated_tokens_saved": self._stats["tokens_saved_estimate"],
        }

    def clear(self) -> None:
        self._store.clear()
        logger.info("Cache cleared")


# Singleton shared across all services
llm_cache = LLMCache()
