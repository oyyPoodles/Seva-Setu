"""
SevaSetu — Database Layer
Async SQLAlchemy engine with asyncpg + pgvector support.
"""

import logging
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy import text

from app.config import get_settings

logger = logging.getLogger(__name__)

settings = get_settings()

# ─── Async Engine ────────────────────────────────────────────
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.is_development,
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True,
    pool_recycle=300,
)

# ─── Session Factory ────────────────────────────────────────
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


# ─── Base Model ─────────────────────────────────────────────
class Base(DeclarativeBase):
    """Base class for all SQLAlchemy ORM models."""
    pass


# ─── Dependency Injection ───────────────────────────────────
async def get_db() -> AsyncSession:
    """FastAPI dependency that provides an async DB session."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


# ─── Initialization ─────────────────────────────────────────
async def init_db():
    """
    Initialize the database:
    1. Ensure pgvector extension exists
    2. Create all tables from ORM models
    """
    async with engine.begin() as conn:
        # Enable pgvector extension
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        await conn.execute(text('CREATE EXTENSION IF NOT EXISTS "uuid-ossp"'))
        logger.info("✅ pgvector + uuid-ossp extensions enabled")

        # Import models so they register with Base.metadata
        from app.models import db_models  # noqa: F401

        # Create all tables
        await conn.run_sync(Base.metadata.create_all)
        logger.info("✅ All database tables created")


async def close_db():
    """Dispose the engine connection pool."""
    await engine.dispose()
    logger.info("🔌 Database connection pool closed")
