"""
SevaSetu — Rate Limiting
Configurable per-endpoint rate limiting to prevent abuse.

Strategy:
  - Default: 100 requests/minute per IP (general endpoints)
  - Ingestion endpoints: 30 requests/minute (heavier processing)
  - System admin: 10 requests/minute (expensive operations like briefings)
  - Health/docs: unlimited (monitoring probes)

Storage:
  - If REDIS_URL is set → Redis-backed (survives restarts, works across instances)
  - Otherwise → in-memory (resets on restart, fine for single-instance dev)
"""

import logging

from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from fastapi import Request
from fastapi.responses import JSONResponse

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


def _key_func(request: Request) -> str:
    """Use client IP as rate limit key."""
    return get_remote_address(request)


# ─── Storage backend ─────────────────────────────────────────────────────────
if settings.REDIS_URL:
    _storage_uri = settings.REDIS_URL
    logger.info(f"🔒 Rate limiter: Redis-backed ({settings.REDIS_URL[:30]}...)")
else:
    _storage_uri = "memory://"
    logger.info("🔒 Rate limiter: in-memory (set REDIS_URL for persistence)")


# ─── Limiter instance ────────────────────────────────────────────────────────
limiter = Limiter(
    key_func=_key_func,
    default_limits=["100/minute"],
    storage_uri=_storage_uri,
)

# ─── Rate limit tiers (import these in route files) ──────────────────────────
RATE_DEFAULT = "100/minute"
RATE_INGESTION = "30/minute"
RATE_SYSTEM = "10/minute"
RATE_CHAT = "20/minute"


async def rate_limit_exceeded_handler(request: Request, exc: RateLimitExceeded):
    """Custom handler for rate limit exceeded responses."""
    return JSONResponse(
        status_code=429,
        content={
            "error": "Rate limit exceeded",
            "detail": str(exc.detail),
            "retry_after_seconds": 60,
        },
    )
