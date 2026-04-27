"""
SevaSetu — FastAPI Application
Main entry point with lifespan management, middleware, scheduled jobs, and route registration.
"""

import logging
from contextlib import asynccontextmanager
from datetime import datetime

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from slowapi.errors import RateLimitExceeded

from app.config import get_settings
from app.database import init_db, close_db
from app.models.schemas import HealthResponse
from app.middleware.rate_limit import limiter, rate_limit_exceeded_handler
from app.middleware.auth import FirebaseAuthMiddleware

# ─── Logging Setup ───────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s │ %(levelname)-8s │ %(name)s │ %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("sevasetu")

settings = get_settings()


# ─── Scheduled Job Wrappers ─────────────────────────────────
# These wrap async service calls so APScheduler can execute them.
# Each job creates its own DB session (scheduler runs in a separate thread).

async def _run_urgency_decay():
    """Scheduled: run urgency decay for all open needs."""
    try:
        from app.database import AsyncSessionLocal
        from app.services.urgency_service import run_urgency_decay
        async with AsyncSessionLocal() as session:
            async with session.begin():
                result = await run_urgency_decay(session)
                logger.info(f"⏰ Scheduled urgency decay: {result}")
    except Exception as e:
        logger.error(f"Scheduled urgency decay failed: {e}")


async def _run_clustering():
    """Scheduled: DBSCAN clustering on open needs."""
    try:
        from app.database import AsyncSessionLocal
        from app.services.clustering_service import clustering_service
        async with AsyncSessionLocal() as session:
            async with session.begin():
                result = await clustering_service.cluster_existing_needs(session)
                logger.info(f"⏰ Scheduled clustering: {result}")
    except Exception as e:
        logger.error(f"Scheduled clustering failed: {e}")


async def _run_briefing():
    """Scheduled: proactive regional briefing."""
    try:
        from app.database import AsyncSessionLocal
        from app.services.briefing_service import briefing_service
        async with AsyncSessionLocal() as session:
            result = await briefing_service.generate_briefing(session)
            logger.info(f"⏰ Scheduled briefing: {len(result.get('sections', []))} sections")
    except Exception as e:
        logger.error(f"Scheduled briefing failed: {e}")


def _sync_job_wrapper(async_fn):
    """Wrap an async function so APScheduler (sync) can run it."""
    import asyncio
    def wrapper():
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                asyncio.ensure_future(async_fn())
            else:
                loop.run_until_complete(async_fn())
        except RuntimeError:
            asyncio.run(async_fn())
    return wrapper


# ─── Lifespan ────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown logic for the FastAPI application."""
    # ── Startup ──
    logger.info("═" * 60)
    logger.info("🚀 SevaSetu Backend starting...")
    logger.info(f"   Environment: {settings.APP_ENV}")
    logger.info(f"   Version: {settings.APP_VERSION}")
    logger.info(f"   Auth: {'Firebase' if settings.FIREBASE_CREDENTIALS_PATH else 'disabled (dev)'}")
    logger.info(f"   Rate Limiting: 100/min default")
    logger.info("═" * 60)

    # Initialize database and create tables
    await init_db()
    logger.info("✅ Database initialized")

    # Start offline queue background sync worker
    from app.services.offline_queue import offline_queue
    offline_queue.start_background_sync()
    logger.info(f"✅ Offline queue started ({offline_queue.depth} reports from previous session)")

    # Log Gemma availability (lazy — won't actually load yet)
    from app.services.gemma_service import gemma_service
    logger.info("ℹ️  Gemma 4 available on first use (lazy load)")

    # ── Start APScheduler ──
    from apscheduler.schedulers.background import BackgroundScheduler
    scheduler = BackgroundScheduler()

    # Urgency decay: every 1 hour
    scheduler.add_job(
        _sync_job_wrapper(_run_urgency_decay),
        'interval', hours=1, id='urgency_decay',
        next_run_time=None,  # Don't run immediately on startup
    )

    # Need clustering: every 6 hours
    scheduler.add_job(
        _sync_job_wrapper(_run_clustering),
        'interval', hours=6, id='need_clustering',
        next_run_time=None,
    )

    # Regional briefing: every 6 hours
    scheduler.add_job(
        _sync_job_wrapper(_run_briefing),
        'interval', hours=6, id='regional_briefing',
        next_run_time=None,
    )

    scheduler.start()
    logger.info(
        "⏰ Scheduler started: urgency_decay(1h), clustering(6h), briefing(6h)"
    )

    yield

    # ── Shutdown ──
    scheduler.shutdown(wait=False)
    logger.info("⏰ Scheduler stopped")
    offline_queue.stop_background_sync()
    logger.info("📥 Offline queue worker stopped")
    await close_db()
    logger.info("👋 SevaSetu Backend shutting down")


# ─── Application Factory ────────────────────────────────────
app = FastAPI(
    title="SevaSetu API",
    description=(
        "Smart Resource Allocation Platform for NGOs — "
        "AI-powered volunteer matching, need intelligence, and community coordination."
    ),
    version=settings.APP_VERSION,
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)


# ─── Rate Limiting ──────────────────────────────────────────
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)


# ─── Firebase Auth Middleware ────────────────────────────────
# Enforces Bearer token on POST/PATCH/DELETE when FIREBASE_CREDENTIALS_PATH is set.
# Completely skipped in dev mode (no credentials configured).
# NOTE: Must be added BEFORE CORSMiddleware so CORS is the outermost wrapper.
app.add_middleware(FirebaseAuthMiddleware)


# ─── CORS Middleware ─────────────────────────────────────────
# Added LAST = outermost = runs first on requests, last on responses.
# This ensures Access-Control-Allow-Origin is set on ALL responses,
# including 401 auth errors from FirebaseAuthMiddleware.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        settings.FRONTEND_URL,
        "http://localhost:3000",
        "http://localhost:3001",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)


# ─── Request Logging Middleware ──────────────────────────────
@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Log every incoming request with timing."""
    start = datetime.utcnow()
    response: Response = await call_next(request)
    duration_ms = (datetime.utcnow() - start).total_seconds() * 1000

    logger.info(
        f"{request.method} {request.url.path} → {response.status_code} ({duration_ms:.0f}ms)"
    )
    return response


# ─── Request Size Limit Middleware ───────────────────────────
MAX_REQUEST_BODY_BYTES = 2 * 1024 * 1024  # 2MB

@app.middleware("http")
async def limit_request_size(request: Request, call_next):
    """Reject requests with bodies larger than 2MB to prevent DoS."""
    content_length = request.headers.get("content-length")
    if content_length and int(content_length) > MAX_REQUEST_BODY_BYTES:
        from fastapi.responses import JSONResponse
        return JSONResponse(
            status_code=413,
            content={"error": "Request body too large", "max_bytes": MAX_REQUEST_BODY_BYTES},
        )
    return await call_next(request)


# ─── Expanded Health Check ───────────────────────────────────
@app.get("/health", tags=["System"])
async def health_check():
    """
    Comprehensive health check for Cloud Run readiness probes.
    Checks: database, Gemini API, embedding model, Google Maps.
    Returns degraded status if any non-critical dependency is down.
    """
    from sqlalchemy import text
    from app.database import AsyncSessionLocal

    checks = {}
    overall = "ok"

    # 1. Database (critical — if down, everything is broken)
    try:
        async with AsyncSessionLocal() as session:
            result = await session.execute(text("SELECT 1"))
            if result.scalar() == 1:
                checks["database"] = "connected"
            else:
                checks["database"] = "error: unexpected result"
                overall = "degraded"
    except Exception as e:
        checks["database"] = f"error: {str(e)[:80]}"
        overall = "unhealthy"  # DB down = full failure

    # 2. Gemini API (non-critical — system falls back to rule-based)
    try:
        from app.services.gemini_service import gemini_service
        if gemini_service.is_available:
            checks["gemini"] = "available"
        else:
            checks["gemini"] = "unavailable (rule-based fallback active)"
            if overall == "ok":
                overall = "degraded"
    except Exception as e:
        checks["gemini"] = f"error: {str(e)[:80]}"
        if overall == "ok":
            overall = "degraded"

    # 3. Embedding model (non-critical — falls back to hash vectors)
    try:
        from app.services.embedding_service import embedding_service
        if hasattr(embedding_service, '_model') and embedding_service._model is not None:
            checks["embedding_model"] = "loaded"
        else:
            checks["embedding_model"] = "fallback (hash-based)"
            if overall == "ok":
                overall = "degraded"
    except Exception as e:
        checks["embedding_model"] = f"error: {str(e)[:80]}"
        if overall == "ok":
            overall = "degraded"

    # 4. Google Maps (non-critical — geo scoring disabled without it)
    try:
        from app.services.geocoding_service import geocoding_service
        if geocoding_service.is_available:
            checks["google_maps"] = "available"
        else:
            checks["google_maps"] = "unavailable (geo scoring disabled)"
            if overall == "ok":
                overall = "degraded"
    except Exception as e:
        checks["google_maps"] = f"error: {str(e)[:80]}"
        if overall == "ok":
            overall = "degraded"

    # 5. Gemma 4 local (non-critical — optional AI tier)
    try:
        from app.services.gemma_service import gemma_service
        if gemma_service._load_attempted:
            checks["gemma_local"] = "loaded" if gemma_service.is_available else "unavailable"
        else:
            checks["gemma_local"] = "standby (lazy load on first use)"
    except Exception as e:
        checks["gemma_local"] = f"error: {str(e)[:80]}"

    # 6. Offline queue status
    try:
        from app.services.offline_queue import offline_queue
        q_stats = offline_queue.stats
        checks["offline_queue"] = {
            "depth": q_stats["current_depth"],
            "pending_sync": q_stats["pending_sync"],
            "total_synced": q_stats["total_synced"],
            "gemma_triaged": q_stats["gemma_triaged"],
        }
    except Exception as e:
        checks["offline_queue"] = f"error: {str(e)[:80]}"

    # 7. Scheduler status
    checks["scheduler"] = "running"  # If we got here, the app is up = scheduler is up

    return {
        "status": overall,
        "version": settings.APP_VERSION,
        "environment": settings.APP_ENV,
        "checks": checks,
        "timestamp": datetime.utcnow().isoformat(),
    }


@app.get("/", tags=["System"])
async def root():
    """Root endpoint with API information."""
    return {
        "name": "SevaSetu API",
        "tagline": "Right volunteer. Right place. Right time.",
        "version": settings.APP_VERSION,
        "docs": "/docs",
        "health": "/health",
    }


# ─── Route Registration ─────────────────────────────────────
from app.routes import (
    need_routes, volunteer_routes, match_routes,
    dashboard_routes, ingestion_routes, system_routes, chat_routes
)

app.include_router(need_routes.router, prefix="/api", tags=["Needs"])
app.include_router(volunteer_routes.router, prefix="/api", tags=["Volunteers"])
app.include_router(match_routes.router, prefix="/api", tags=["Matching"])
app.include_router(dashboard_routes.router, prefix="/api", tags=["Dashboard"])
app.include_router(ingestion_routes.router, prefix="/api", tags=["Ingestion"])
app.include_router(system_routes.router, prefix="/api", tags=["System"])
app.include_router(chat_routes.router, tags=["Chat"])


