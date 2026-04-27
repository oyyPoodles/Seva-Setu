"""
SevaSetu — System Routes
Health, urgency decay trigger, briefings, and admin endpoints.
"""

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.services.urgency_service import run_urgency_decay, check_disaster_mode
from app.middleware.rate_limit import limiter, RATE_SYSTEM

router = APIRouter()


@router.post("/system/urgency-decay")
@limiter.limit(RATE_SYSTEM)
async def trigger_urgency_decay(request: Request, db: AsyncSession = Depends(get_db)):
    """
    Manually trigger urgency decay calculation.
    In production, called by Cloud Scheduler every hour.
    """
    stats = await run_urgency_decay(db)
    return stats


@router.get("/system/disaster-check")
async def disaster_check(db: AsyncSession = Depends(get_db)):
    """Check if disaster mode should be activated based on critical need density."""
    return await check_disaster_mode(db)


@router.post("/system/cluster-needs")
@limiter.limit(RATE_SYSTEM)
async def trigger_clustering(request: Request, db: AsyncSession = Depends(get_db)):
    """Run DBSCAN clustering on open needs to group semantic/geographic hotspots."""
    from app.services.clustering_service import clustering_service
    result = await clustering_service.cluster_existing_needs(db)
    return result


# ─── PROACTIVE REGIONAL BRIEFING ─────────────────────────────

@router.post("/system/regional-briefing")
@limiter.limit(RATE_SYSTEM)
async def generate_regional_briefing(request: Request, db: AsyncSession = Depends(get_db)):
    """
    Generate a proactive coordinator briefing by analyzing the full need corpus.
    Detects: skill gaps, geographic hotspots, predicted escalations, trend observations.
    Cached for 6h — Gemini Pro called at most once per snapshot change.
    """
    from app.services.briefing_service import briefing_service
    result = await briefing_service.generate_regional_briefing(db)
    return result

@router.get("/system/weight-calibration-state")
async def weight_calibration_state():
    """
    Expose the current state of the hybrid weight calibrator.
    Shows the static map (which self-updates via LLM feedback),
    adjustment history counts, and learning threshold.
    Use this to monitor if the static map is converging toward
    LLM-preferred weights over time.
    """
    from app.services.weight_calibrator import weight_calibrator
    return weight_calibrator.get_static_map_snapshot()


# ─── LLM CACHE MONITORING ─────────────────────────────────────

@router.get("/system/llm-cache-stats")
async def get_llm_cache_stats():
    """
    Return LLM cache performance metrics.
    Use to monitor hit rates and estimated token savings.
    """
    from app.services.llm_cache import llm_cache
    return {
        "cache_stats": llm_cache.stats(),
        "ttl_config": {
            "skill_synonyms_s": 86400,
            "dynamic_weights_s": 1800,
            "extraction_s": 3600,
            "validation_s": 600,
            "area_briefing_s": 21600,
            "feedback_analysis_s": 7200,
            "dispatch": "not cached (personalized)",
        },
    }


@router.delete("/system/llm-cache/{task_type}")
async def invalidate_llm_cache(task_type: str):
    """
    Manually invalidate the LLM cache for a specific task type.
    Useful when skill vocabulary is updated or weights need recalibration.
    Valid task_types: skill_synonyms, dynamic_weights, extraction, validation,
                      area_briefing, feedback_analysis
    """
    from app.services.llm_cache import llm_cache
    removed = llm_cache.invalidate(task_type)
    return {"task_type": task_type, "entries_removed": removed}


# ─── SERVICE STATUS ───────────────────────────────────────────

@router.get("/system/service-status")
async def service_status():
    """Check availability of all external services including circuit breaker state."""
    from app.services.gemini_service import gemini_service
    from app.services.embedding_service import embedding_service
    from app.services.notification_service import notification_service
    from app.services.disaster_service import disaster_service as disaster_svc
    from app.services.translation_service import translation_service as translation_svc
    from app.services.sheets_service import sheets_service as sheets_svc
    from app.services.llm_cache import llm_cache
    from app.config import get_settings as _gs
    cfg = _gs()

    return {
        "gemini_ai": {
            "available": gemini_service.is_available,
            "mode": "gemini-1.5-flash" if gemini_service.is_available else "rule-based fallback",
            "health": gemini_service.health_metrics,
        },
        "embeddings": {
            "available": embedding_service.is_available,
            "mode": "sentence-transformers" if embedding_service.is_available else "hash-based fallback",
        },
        "geocoding": {
            "available": bool(cfg.GOOGLE_MAPS_API_KEY),
            "mode": "google-maps" if cfg.GOOGLE_MAPS_API_KEY else "offline fallback (14 cities)",
        },
        "notifications": {
            "available": notification_service.is_available,
            "mode": "FCM push" if notification_service.is_available else "log-only (dev mode)",
        },
        "disaster_mode": {
            "available": True,
            "active": disaster_svc.is_active,
            "active_zones": disaster_svc.active_zones,
        },
        "translation": {
            "available": translation_svc.is_available,
            "mode": "google-cloud-translation-v3" if translation_svc.is_available else "disabled (langdetect fallback)",
        },
        "sheets_sync": {
            "available": sheets_svc.is_available,
            "mode": "google-sheets-v4" if sheets_svc.is_available else "disabled",
        },
        "llm_cache": llm_cache.stats(),
    }



def get_settings():
    from app.config import get_settings as _gs
    return _gs()
