"""
SevaSetu — Configuration
Environment-based settings with Pydantic BaseSettings.
"""

from pydantic_settings import BaseSettings
from typing import Optional
from functools import lru_cache


class Settings(BaseSettings):
    """Application configuration loaded from environment variables."""

    # ─── Database ────────────────────────────────────────────
    DATABASE_URL: str = "postgresql+asyncpg://sevasetu:sevasetu_dev_2024@localhost:5433/sevasetu"

    # ─── Google AI ───────────────────────────────────────────
    GEMINI_API_KEY: Optional[str] = None
    GOOGLE_MAPS_API_KEY: Optional[str] = None

    # ─── Firebase ────────────────────────────────────────────
    FIREBASE_CREDENTIALS_PATH: Optional[str] = None
    FIREBASE_DEV_BYPASS: bool = False  # Set True in .env to skip auth in dev

    # ─── Google Cloud ────────────────────────────────────────
    GOOGLE_CLOUD_PROJECT: Optional[str] = None
    GOOGLE_APPLICATION_CREDENTIALS: Optional[str] = None

    # ─── Feature Flags ───────────────────────────────────────
    ENABLE_WHATSAPP: bool = False
    ENABLE_SHEETS_SYNC: bool = False
    DISASTER_MODE_THRESHOLD: int = 10          # Urban areas
    DISASTER_MODE_LOW_DENSITY_THRESHOLD: int = 5  # Rural/tribal areas

    # ─── App ─────────────────────────────────────────────────
    APP_ENV: str = "development"
    FRONTEND_URL: str = "http://localhost:3000"
    LOG_LEVEL: str = "INFO"
    APP_VERSION: str = "0.1.0"
    REDIS_URL: Optional[str] = None  # e.g. redis://localhost:6379/0 — for rate limiting + caching

    # ─── Embedding ───────────────────────────────────────────
    EMBEDDING_MODEL: str = "paraphrase-multilingual-MiniLM-L12-v2"
    EMBEDDING_DIM: int = 384

    # ─── Matching ────────────────────────────────────────────
    MATCH_WEIGHT_SKILL_EMBEDDING: float = 0.30
    MATCH_WEIGHT_SKILL_TAGS: float = 0.25
    MATCH_WEIGHT_GEO_PROXIMITY: float = 0.20
    MATCH_WEIGHT_URGENCY: float = 0.15
    MATCH_WEIGHT_AVAILABILITY: float = 0.10
    DEFAULT_SEARCH_RADIUS_KM: float = 25.0
    MAX_MATCH_CANDIDATES: int = 20

    # ─── Urgency Decay ───────────────────────────────────────
    URGENCY_DECAY_RATE: float = 0.15
    URGENCY_TIER1_THRESHOLD: float = 0.70
    URGENCY_TIER2_THRESHOLD: float = 0.85
    URGENCY_CRITICAL_THRESHOLD: float = 0.95

    # ─── Dedup ───────────────────────────────────────────────
    DEDUP_COSINE_THRESHOLD: float = 0.90
    DEDUP_WINDOW_DAYS: int = 7

    @property
    def is_development(self) -> bool:
        return self.APP_ENV == "development"

    @property
    def is_production(self) -> bool:
        return self.APP_ENV == "production"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True


@lru_cache()
def get_settings() -> Settings:
    """Cached settings instance — loaded once on first call."""
    return Settings()
