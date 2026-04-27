"""
SevaSetu — Notification Service
FCM push notifications to volunteers via Firebase Admin SDK.

Architecture:
  - If FIREBASE_CREDENTIALS_PATH is set → real FCM push notifications
  - If not set → log-only mode (dev). No notifications sent, but the calling
    code doesn't need to care.

Usage:
  await notification_service.notify_assignment(volunteer, need, assignment)
  await notification_service.notify_area_alert(lat, lng, radius_km, message)
"""

import logging
from typing import Optional

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

# ─── Firebase Messaging Setup ────────────────────────────────────────────────
_messaging = None

try:
    if settings.FIREBASE_CREDENTIALS_PATH:
        from firebase_admin import messaging
        _messaging = messaging
        logger.info("🔔 FCM notifications enabled")
    else:
        logger.info("🔕 FCM notifications disabled (no Firebase credentials)")
except Exception as e:
    logger.warning(f"⚠️ FCM init failed: {e} — notifications disabled")


class NotificationService:
    """
    Sends push notifications to volunteers.
    Degrades gracefully: logs instead of sending when Firebase is unavailable.
    """

    @property
    def is_available(self) -> bool:
        return _messaging is not None

    async def notify_assignment(
        self,
        volunteer_fcm_token: Optional[str],
        volunteer_name: str,
        need_title: str,
        need_type: str,
        assignment_id: str,
        dispatch_brief: Optional[str] = None,
    ) -> bool:
        """
        Notify a volunteer that they've been assigned to a need.
        Returns True if notification was sent (or would have been in dev mode).
        """
        title = f"🆕 New Assignment: {need_type}"
        body = f"You've been matched to: {need_title}"
        data = {
            "type": "assignment",
            "assignment_id": assignment_id,
            "need_title": need_title,
            "need_type": need_type,
        }
        if dispatch_brief:
            data["dispatch_brief"] = dispatch_brief[:500]  # FCM data limit

        if not _messaging or not volunteer_fcm_token:
            logger.info(
                f"🔕 [DEV] Would notify {volunteer_name}: {title} — {body}"
            )
            return True  # Report success in dev mode

        try:
            message = _messaging.Message(
                notification=_messaging.Notification(
                    title=title,
                    body=body,
                ),
                data=data,
                token=volunteer_fcm_token,
            )
            response = _messaging.send(message)
            logger.info(
                f"🔔 Notified {volunteer_name} (assignment {assignment_id[:8]}): {response}"
            )
            return True
        except _messaging.UnregisteredError:
            logger.warning(
                f"FCM token expired for {volunteer_name} — clearing token"
            )
            return False
        except Exception as e:
            logger.error(f"FCM send failed for {volunteer_name}: {e}")
            return False

    async def notify_status_update(
        self,
        volunteer_fcm_token: Optional[str],
        volunteer_name: str,
        assignment_id: str,
        new_status: str,
    ) -> bool:
        """Notify volunteer of assignment status change (accepted, completed, etc.)."""
        status_labels = {
            "accepted": "✅ Assignment Confirmed",
            "in_progress": "🔄 Assignment In Progress",
            "completed": "🎉 Assignment Completed",
            "declined": "❌ Assignment Declined",
            "cancelled": "⚠️ Assignment Cancelled",
        }
        title = status_labels.get(new_status, f"Assignment Update: {new_status}")
        body = f"Your assignment status has been updated to: {new_status}"

        if not _messaging or not volunteer_fcm_token:
            logger.info(f"🔕 [DEV] Would notify {volunteer_name}: {title}")
            return True

        try:
            message = _messaging.Message(
                notification=_messaging.Notification(title=title, body=body),
                data={"type": "status_update", "assignment_id": assignment_id, "status": new_status},
                token=volunteer_fcm_token,
            )
            _messaging.send(message)
            return True
        except Exception as e:
            logger.error(f"FCM status update failed: {e}")
            return False

    async def notify_area_alert(
        self,
        topic: str,
        title: str,
        body: str,
        data: Optional[dict] = None,
    ) -> bool:
        """
        Broadcast alert to all subscribers of a geographic topic.
        Topics can be: 'area_mumbai', 'disaster_active', etc.
        """
        if not _messaging:
            logger.info(f"🔕 [DEV] Would broadcast to topic '{topic}': {title}")
            return True

        try:
            message = _messaging.Message(
                notification=_messaging.Notification(title=title, body=body),
                data=data or {},
                topic=topic,
            )
            response = _messaging.send(message)
            logger.info(f"🔔 Broadcast to topic '{topic}': {response}")
            return True
        except Exception as e:
            logger.error(f"FCM topic broadcast failed: {e}")
            return False


# Singleton
notification_service = NotificationService()
