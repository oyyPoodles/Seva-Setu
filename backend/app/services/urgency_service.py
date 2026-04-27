"""
SevaSetu — Urgency Decay Service
Background task that increases urgency for unaddressed needs over time.
Unresolved needs become MORE urgent, not less.
"""

import logging
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, update

from app.config import get_settings
from app.models.db_models import Need

logger = logging.getLogger(__name__)
settings = get_settings()


async def run_urgency_decay(db: AsyncSession) -> dict:
    """
    Update urgency_current for all active needs based on time elapsed.

    Formula: urgency_current = min(1.0, urgency_base + decay_rate × days_elapsed)

    This means needs that go unaddressed become MORE urgent over time,
    reflecting real-world humanitarian dynamics.

    Returns stats about the update.
    """
    now = datetime.utcnow()

    # Get all active (non-completed) needs
    result = await db.execute(
        select(Need).where(
            Need.status.in_(["new", "matched", "assigned", "in_progress"])
        )
    )
    needs = result.scalars().all()

    updated = 0
    escalated = 0  # Crossed a threshold

    for need in needs:
        if not need.created_at:
            continue

        hours_elapsed = (now - need.created_at).total_seconds() / 3600
        days_elapsed = hours_elapsed / 24

        # urgency grows linearly with time
        new_urgency = min(
            1.0,
            need.urgency_base + (settings.URGENCY_DECAY_RATE * days_elapsed),
        )

        if abs(new_urgency - (need.urgency_current or 0)) > 0.001:
            old = need.urgency_current or need.urgency_base

            need.urgency_current = round(new_urgency, 4)
            updated += 1

            # Check for threshold crossings
            if old < settings.URGENCY_TIER2_THRESHOLD <= new_urgency:
                escalated += 1
                logger.warning(
                    f"🔴 ESCALATED: Need '{need.title[:40]}' urgency "
                    f"{old:.2f} → {new_urgency:.2f} (critical threshold)"
                )
            elif old < settings.URGENCY_TIER1_THRESHOLD <= new_urgency:
                escalated += 1
                logger.info(
                    f"🟡 ELEVATED: Need '{need.title[:40]}' urgency "
                    f"{old:.2f} → {new_urgency:.2f} (high threshold)"
                )

    if updated > 0:
        await db.flush()

    stats = {
        "total_active": len(needs),
        "updated": updated,
        "escalated": escalated,
        "timestamp": now.isoformat(),
    }

    logger.info(
        f"Urgency decay: {updated}/{len(needs)} needs updated, "
        f"{escalated} escalated"
    )
    return stats


async def check_disaster_mode(db: AsyncSession) -> dict:
    """
    Check if disaster mode should be activated.
    Uses TWO thresholds:
      - DISASTER_MODE_THRESHOLD (default 10): full activation for urban areas
      - DISASTER_MODE_LOW_DENSITY_THRESHOLD (default 5): early warning for rural/tribal areas

    Returns disaster mode status, affected regions, and warning regions.
    """
    from sqlalchemy import func, cast, Numeric

    # Count critical needs by approximate region (rounded lat/lng)
    lat_region = func.round(cast(Need.latitude, Numeric), 1).label("lat_region")
    lng_region = func.round(cast(Need.longitude, Numeric), 1).label("lng_region")

    # Query with the LOWER threshold to get both tiers
    result = await db.execute(
        select(
            lat_region,
            lng_region,
            func.count(Need.id).label("count"),
        )
        .where(
            and_(
                Need.urgency_current >= settings.URGENCY_CRITICAL_THRESHOLD,
                Need.status.in_(["new", "matched"]),
                Need.latitude.isnot(None),
                Need.longitude.isnot(None),
            )
        )
        .group_by(lat_region, lng_region)
        .having(func.count(Need.id) >= settings.DISASTER_MODE_LOW_DENSITY_THRESHOLD)
    )

    hotspots = result.all()

    # Split into disaster (≥ standard threshold) and warning (≥ low density only)
    disaster_regions = []
    warning_regions = []

    for h in hotspots:
        region = {
            "latitude": float(h[0]),
            "longitude": float(h[1]),
            "critical_count": h[2],
        }
        if h[2] >= settings.DISASTER_MODE_THRESHOLD:
            disaster_regions.append(region)
        else:
            warning_regions.append(region)

    if disaster_regions:
        logger.critical(
            f"🚨 DISASTER MODE: {len(disaster_regions)} region(s) with "
            f"{sum(r['critical_count'] for r in disaster_regions)} critical needs"
        )
    if warning_regions:
        logger.warning(
            f"⚠️ DISASTER WARNING: {len(warning_regions)} low-density region(s) "
            f"with {sum(r['critical_count'] for r in warning_regions)} critical needs "
            f"(threshold: {settings.DISASTER_MODE_LOW_DENSITY_THRESHOLD})"
        )

    return {
        "disaster_mode": len(disaster_regions) > 0,
        "regions": disaster_regions,
        "warning_regions": warning_regions,
        "total_critical": sum(r["critical_count"] for r in disaster_regions + warning_regions),
        "thresholds": {
            "standard": settings.DISASTER_MODE_THRESHOLD,
            "low_density": settings.DISASTER_MODE_LOW_DENSITY_THRESHOLD,
        },
    }

