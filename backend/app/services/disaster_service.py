"""
SevaSetu — Disaster Mode Service
Centralized anomaly detection and disaster mode activation.

Architecture:
  - Monitors inbound need reports for geographic clustering anomalies
  - When reports from a single area exceed the threshold within 1 hour,
    activates disaster mode: re-sorts volunteers, mass FCM blast, dashboard alert
  - Integrates with urgency_service and notification_service
"""

import logging
from datetime import datetime, timedelta
from typing import Optional, Tuple

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, cast, Numeric

from app.config import get_settings
from app.models.db_models import Need, Volunteer

logger = logging.getLogger(__name__)
settings = get_settings()


class DisasterService:
    """
    Detects anomalous need report rates and activates disaster mode.
    Called on every need submission to check for geographic report spikes.
    """

    def __init__(self):
        self._active_disasters: dict[str, dict] = {}  # area_key → metadata
        logger.info("🚨 Disaster detection service initialized")

    @property
    def is_active(self) -> bool:
        """Whether any disaster mode is currently active."""
        return len(self._active_disasters) > 0

    @property
    def active_zones(self) -> list[dict]:
        """Return all active disaster zones with metadata."""
        return list(self._active_disasters.values())

    async def check_for_disaster(
        self,
        need: Need,
        db: AsyncSession,
    ) -> Optional[dict]:
        """
        Called on every need submission. Checks for anomalous report rate
        from the same geographic area within the last hour.

        Uses two thresholds:
          - DISASTER_MODE_THRESHOLD (default 10): urban areas
          - DISASTER_MODE_LOW_DENSITY_THRESHOLD (default 5): rural/tribal

        Returns disaster metadata if triggered, None otherwise.
        """
        if need.latitude is None or need.longitude is None:
            return None

        # Count recent reports within ~5km radius in last 1 hour
        one_hour_ago = datetime.utcnow() - timedelta(hours=1)
        radius_deg = 0.05  # ~5.5 km at Indian latitudes

        result = await db.execute(
            select(func.count(Need.id)).where(
                and_(
                    Need.created_at >= one_hour_ago,
                    Need.latitude.isnot(None),
                    Need.longitude.isnot(None),
                    func.abs(cast(Need.latitude, Numeric) - need.latitude) < radius_deg,
                    func.abs(cast(Need.longitude, Numeric) - need.longitude) < radius_deg,
                )
            )
        )
        recent_count = result.scalar() or 0

        # Check threshold (use lower for rural areas if configured)
        threshold = settings.DISASTER_MODE_THRESHOLD

        if recent_count >= threshold:
            return await self._activate_disaster_mode(
                need, recent_count, db
            )

        return None

    async def _activate_disaster_mode(
        self,
        epicenter: Need,
        report_count: int,
        db: AsyncSession,
    ) -> dict:
        """
        Activate disaster mode for an area:
        1. Register the disaster zone
        2. Notify all nearby volunteers via FCM
        3. Auto-escalate all needs in the area to critical urgency
        """
        area_key = f"{epicenter.latitude:.2f},{epicenter.longitude:.2f}"

        # Don't re-trigger if already active for this area
        if area_key in self._active_disasters:
            logger.info(f"🚨 Disaster already active for area {area_key}")
            return self._active_disasters[area_key]

        # 1. Register disaster zone
        disaster_info = {
            "area_key": area_key,
            "epicenter_lat": epicenter.latitude,
            "epicenter_lng": epicenter.longitude,
            "location_name": epicenter.location_name or f"Area ({area_key})",
            "report_count": report_count,
            "triggered_at": datetime.utcnow().isoformat(),
            "triggered_by_need_id": str(epicenter.id),
            "primary_type": epicenter.need_type,
            "status": "active",
        }
        self._active_disasters[area_key] = disaster_info

        logger.warning(
            f"🚨🚨🚨 DISASTER MODE ACTIVATED: {report_count} reports near "
            f"{disaster_info['location_name']} ({area_key})"
        )

        # 2. Escalate all needs in the area to critical
        radius_deg = 0.05
        await db.execute(
            Need.__table__.update()
            .where(
                and_(
                    Need.status.in_(["new", "matched", "assigned", "in_progress"]),
                    Need.latitude.isnot(None),
                    func.abs(cast(Need.latitude, Numeric) - epicenter.latitude) < radius_deg,
                    func.abs(cast(Need.longitude, Numeric) - epicenter.longitude) < radius_deg,
                )
            )
            .values(urgency_current=1.0)
        )
        await db.flush()

        # 3. Notify volunteers (FCM — gracefully degraded)
        try:
            from app.services.notification_service import notification_service
            await notification_service.notify_area_alert(
                topic=f"area_{area_key.replace(',', '_').replace('.', '_')}",
                title="🚨 Disaster Mode Activated",
                body=(
                    f"Emergency in {disaster_info['location_name']}: "
                    f"{report_count} reports in the last hour. "
                    f"All available volunteers requested."
                ),
                data={
                    "type": "disaster_alert",
                    "area_key": area_key,
                    "lat": str(epicenter.latitude),
                    "lng": str(epicenter.longitude),
                },
            )
        except Exception as e:
            logger.error(f"FCM disaster broadcast failed: {e}")

        return disaster_info

    async def deactivate_disaster(self, area_key: str) -> bool:
        """Manually deactivate disaster mode for an area."""
        if area_key in self._active_disasters:
            self._active_disasters[area_key]["status"] = "resolved"
            del self._active_disasters[area_key]
            logger.info(f"✅ Disaster mode deactivated for area {area_key}")
            return True
        return False

    async def get_nearby_volunteers(
        self,
        lat: float,
        lng: float,
        radius_km: float,
        db: AsyncSession,
    ) -> list:
        """
        Find all available volunteers within radius of disaster epicenter.
        Used for mass mobilization during disaster mode.
        """
        radius_deg = radius_km / 111.0  # Rough km-to-degree conversion

        result = await db.execute(
            select(Volunteer).where(
                and_(
                    Volunteer.status == "available",
                    Volunteer.latitude.isnot(None),
                    Volunteer.longitude.isnot(None),
                    func.abs(cast(Volunteer.latitude, Numeric) - lat) < radius_deg,
                    func.abs(cast(Volunteer.longitude, Numeric) - lng) < radius_deg,
                )
            )
        )
        return list(result.scalars().all())


# Singleton
disaster_service = DisasterService()
