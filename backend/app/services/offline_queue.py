"""
SevaSetu — Offline Field Triage Queue
Buffers need reports during network/API outages and processes them
using Gemma 4 local inference. Syncs to the database when connectivity returns.

Architecture:
  Report arrives → connectivity check → if offline: queue locally with Gemma triage
                                      → if online: normal Gemini pipeline

  Background worker polls queue every 60s:
    - If DB reachable: flush queue to database
    - Gemma-triaged reports have urgency/type already set → fast insert

Use cases:
  1. Disaster mode: field device loses internet but keeps receiving WhatsApp reports
  2. Gemini API down: reports still triaged locally, flushed when API recovers
  3. Cost saving: batch-process low-urgency reports offline during off-hours
"""

import asyncio
import json
import logging
import time
import uuid
from collections import deque
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)

# Persist queue to disk so reports survive server restarts
QUEUE_FILE = Path(__file__).parent.parent.parent / "data" / "offline_queue.jsonl"


class OfflineReport:
    """A single report buffered in the offline queue."""

    def __init__(
        self,
        raw_text: str,
        source_channel: str,
        location_hint: Optional[Dict] = None,
        language: str = "auto",
        media_type: str = "text",  # text | audio_transcription | image_analysis
    ):
        self.id = str(uuid.uuid4())
        self.raw_text = raw_text
        self.source_channel = source_channel
        self.location_hint = location_hint
        self.language = language
        self.media_type = media_type
        self.queued_at = datetime.now(timezone.utc).isoformat()

        # Filled by Gemma triage
        self.gemma_extraction: Optional[Dict[str, Any]] = None
        self.triage_status: str = "pending"  # pending | triaged | synced | failed
        self.sync_attempts: int = 0

    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "raw_text": self.raw_text,
            "source_channel": self.source_channel,
            "location_hint": self.location_hint,
            "language": self.language,
            "media_type": self.media_type,
            "queued_at": self.queued_at,
            "gemma_extraction": self.gemma_extraction,
            "triage_status": self.triage_status,
            "sync_attempts": self.sync_attempts,
        }

    @classmethod
    def from_dict(cls, d: Dict) -> "OfflineReport":
        r = cls(
            raw_text=d["raw_text"],
            source_channel=d.get("source_channel", "offline"),
            location_hint=d.get("location_hint"),
            language=d.get("language", "auto"),
            media_type=d.get("media_type", "text"),
        )
        r.id = d["id"]
        r.queued_at = d["queued_at"]
        r.gemma_extraction = d.get("gemma_extraction")
        r.triage_status = d.get("triage_status", "pending")
        r.sync_attempts = d.get("sync_attempts", 0)
        return r


class OfflineQueue:
    """
    In-memory + disk-backed queue for offline/degraded-mode operation.

    Flow:
      1. Field worker sends report → enqueue() called
      2. Gemma 4 immediately triages it locally (type, urgency, skills)
      3. Report waits in queue (memory + JSONL file)
      4. Background worker tries sync every 60s
      5. On sync: full pipeline runs with dedup + embedding + DB write
    """

    MAX_QUEUE_SIZE = 500        # Max buffered reports
    MAX_SYNC_ATTEMPTS = 5       # Give up after 5 failed sync attempts
    SYNC_INTERVAL_SECONDS = 60  # Check for sync opportunity every 60s

    def __init__(self):
        self._queue: deque[OfflineReport] = deque(maxlen=self.MAX_QUEUE_SIZE)
        self._syncing = False
        self._sync_task: Optional[asyncio.Task] = None
        self._stats = {
            "total_queued": 0,
            "total_synced": 0,
            "total_failed": 0,
            "gemma_triaged": 0,
        }
        # Load persisted queue from disk on startup
        self._load_from_disk()
        logger.info(
            f"📥 OfflineQueue initialized — {len(self._queue)} reports loaded from disk"
        )

    # ─── Public API ──────────────────────────────────────────

    async def enqueue(
        self,
        raw_text: str,
        source_channel: str,
        location_hint: Optional[Dict] = None,
        language: str = "auto",
        media_type: str = "text",
    ) -> OfflineReport:
        """
        Buffer a report and immediately triage it with Gemma 4.
        Returns the report with triage results attached.
        """
        report = OfflineReport(
            raw_text=raw_text,
            source_channel=source_channel,
            location_hint=location_hint,
            language=language,
            media_type=media_type,
        )

        # Immediate Gemma triage — run synchronously so caller gets urgency back
        report.gemma_extraction = await self._triage_with_gemma(report)
        if report.gemma_extraction:
            report.triage_status = "triaged"
            self._stats["gemma_triaged"] += 1
        else:
            report.triage_status = "pending"

        self._queue.append(report)
        self._stats["total_queued"] += 1
        self._persist_report(report)

        urgency = (report.gemma_extraction or {}).get("urgency", "unknown")
        need_type = (report.gemma_extraction or {}).get("need_type", "unknown")
        logger.info(
            f"📥 Queued [{report.triage_status}] report {report.id[:8]} | "
            f"type={need_type} urgency={urgency} | "
            f"queue_depth={len(self._queue)}"
        )

        # If critical urgency (≥0.95), trigger immediate sync attempt
        if isinstance(urgency, float) and urgency >= 0.95:
            logger.warning(
                f"🚨 Critical urgency report queued — attempting immediate sync"
            )
            asyncio.create_task(self._attempt_sync())

        return report

    def start_background_sync(self):
        """Start the background worker that periodically flushes the queue."""
        if self._sync_task is None or self._sync_task.done():
            self._sync_task = asyncio.create_task(self._sync_loop())
            logger.info(f"🔄 Offline queue sync worker started (every {self.SYNC_INTERVAL_SECONDS}s)")

    def stop_background_sync(self):
        """Stop the background sync worker (called on server shutdown)."""
        if self._sync_task and not self._sync_task.done():
            self._sync_task.cancel()
            logger.info("⏹️ Offline queue sync worker stopped")

    @property
    def depth(self) -> int:
        """Number of reports currently waiting in queue."""
        return len(self._queue)

    @property
    def stats(self) -> Dict[str, Any]:
        """Stats for the /health and monitoring endpoints."""
        pending = sum(1 for r in self._queue if r.triage_status != "synced")
        triaged = sum(1 for r in self._queue if r.triage_status == "triaged")
        return {
            **self._stats,
            "current_depth": len(self._queue),
            "pending_sync": pending,
            "triaged_by_gemma": triaged,
        }

    def get_pending(self, limit: int = 50) -> List[Dict]:
        """Return pending reports for the dashboard offline viewer."""
        return [
            r.to_dict()
            for r in list(self._queue)
            if r.triage_status in ("pending", "triaged")
        ][:limit]

    # ─── Gemma Triage ────────────────────────────────────────

    async def _triage_with_gemma(self, report: OfflineReport) -> Optional[Dict]:
        """Run Gemma 4 extraction on the buffered report."""
        try:
            from app.services.gemma_service import gemma_service
            result = await gemma_service.extract_need(report.raw_text)
            return result
        except Exception as e:
            logger.error(f"Gemma triage failed for {report.id[:8]}: {e}")
            return None

    # ─── Sync Worker ─────────────────────────────────────────

    async def _sync_loop(self):
        """Background loop that attempts to flush the queue periodically."""
        while True:
            try:
                await asyncio.sleep(self.SYNC_INTERVAL_SECONDS)
                await self._attempt_sync()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Sync loop error: {e}")

    async def _attempt_sync(self):
        """Try to sync all triaged reports to the database."""
        if self._syncing or not self._queue:
            return

        pending = [
            r for r in self._queue
            if r.triage_status in ("pending", "triaged")
            and r.sync_attempts < self.MAX_SYNC_ATTEMPTS
        ]
        if not pending:
            return

        self._syncing = True
        synced = 0
        failed = 0

        try:
            # Test DB connectivity first
            from app.database import AsyncSessionLocal
            async with AsyncSessionLocal() as db:
                for report in pending:
                    try:
                        await self._sync_report(report, db)
                        report.triage_status = "synced"
                        synced += 1
                        self._stats["total_synced"] += 1
                    except Exception as e:
                        report.sync_attempts += 1
                        failed += 1
                        self._stats["total_failed"] += 1
                        logger.warning(
                            f"Sync failed for {report.id[:8]} "
                            f"(attempt {report.sync_attempts}): {e}"
                        )
                await db.commit()

            # Evict synced reports from queue
            self._queue = deque(
                (r for r in self._queue if r.triage_status != "synced"),
                maxlen=self.MAX_QUEUE_SIZE,
            )

            if synced:
                logger.info(
                    f"✅ Offline sync complete: {synced} synced, {failed} failed | "
                    f"queue_depth={len(self._queue)}"
                )

        except Exception as e:
            logger.error(f"DB unreachable during sync attempt: {e}")
        finally:
            self._syncing = False

    async def _sync_report(self, report: OfflineReport, db):
        """
        Sync a single buffered report to the database.
        Uses Gemma extraction if available, else runs full Gemini pipeline.
        """
        from app.routes.ingestion_routes import _ingest_text
        await _ingest_text(
            raw_text=report.raw_text,
            source_channel=f"{report.source_channel}_offline",
            language=report.language,
            location_hint=report.location_hint,
            db=db,
        )

    # ─── Disk Persistence ────────────────────────────────────

    def _persist_report(self, report: OfflineReport):
        """Append report to JSONL file for crash recovery."""
        try:
            QUEUE_FILE.parent.mkdir(parents=True, exist_ok=True)
            with open(QUEUE_FILE, "a", encoding="utf-8") as f:
                f.write(json.dumps(report.to_dict()) + "\n")
        except Exception as e:
            logger.warning(f"Failed to persist report to disk: {e}")

    def _load_from_disk(self):
        """Load unsynced reports from disk on startup."""
        if not QUEUE_FILE.exists():
            return
        try:
            with open(QUEUE_FILE, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    d = json.loads(line)
                    if d.get("triage_status") != "synced":
                        self._queue.append(OfflineReport.from_dict(d))
            # Rewrite file without synced entries
            self._flush_disk()
        except Exception as e:
            logger.error(f"Failed to load offline queue from disk: {e}")

    def _flush_disk(self):
        """Rewrite disk file with only unsynced reports."""
        try:
            with open(QUEUE_FILE, "w", encoding="utf-8") as f:
                for r in self._queue:
                    if r.triage_status != "synced":
                        f.write(json.dumps(r.to_dict()) + "\n")
        except Exception as e:
            logger.warning(f"Failed to flush queue to disk: {e}")


# Singleton
offline_queue = OfflineQueue()
