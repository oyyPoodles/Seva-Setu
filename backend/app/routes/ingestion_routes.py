"""
SevaSetu — Ingestion Routes
Multi-channel need intake: WhatsApp webhook, Google Forms, CSV bulk upload.
All channels flow through Gemini extraction → Need creation.
"""

import csv
import io
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.models.db_models import Need
from app.models.schemas import (
    WhatsAppIngest,
    FormIngest,
    BulkIngest,
    NeedResponse,
)
from app.services.gemini_service import gemini_service
from app.services.embedding_service import embedding_service
from app.services.geocoding_service import geocoding_service
from app.middleware.rate_limit import limiter, RATE_INGESTION
from app.config import get_settings

logger = logging.getLogger(__name__)
router = APIRouter()
settings = get_settings()


# ─── Shared: Raw text → Structured Need ─────────────────────

async def _ingest_text(
    raw_text: str,
    source_channel: str,
    language: str = "auto",
    location_hint: Optional[dict] = None,
    db: AsyncSession = None,
) -> Need:
    """
    Universal ingestion pipeline:
    1. Gemini extracts structured fields from raw text
    2. Geocode location if hint provided
    3. Generate embedding for pgvector
    4. Create Need record
    """
    # Step 1: AI extraction
    extracted = await gemini_service.extract_need(raw_text, language)

    # Step 2: Resolve coordinates
    lat, lng = None, None
    if location_hint and "lat" in location_hint and "lng" in location_hint:
        lat, lng = location_hint["lat"], location_hint["lng"]
    elif extracted.get("location_hint"):
        coords = await geocoding_service.geocode(extracted["location_hint"])
        if coords:
            lat, lng = coords

    # Step 3: Generate embedding
    embed_text = f"{extracted.get('title', '')} {extracted.get('description', '')} {' '.join(extracted.get('required_skills', []))}"
    embedding = embedding_service.encode(embed_text)

    # Step 4: Content hash for dedup
    import hashlib
    content_hash = hashlib.sha256(raw_text.strip().lower().encode()).hexdigest()

    # ── 3-Tier Deduplication ──────────────────────────────────────
    # Tier 1: Exact text hash match (same wording)
    # Tier 2: Structural match (same type + nearby location within 7 days)
    # Tier 3: Semantic match (embedding cosine > 0.90 in same area)
    from datetime import datetime, timedelta
    from sqlalchemy import and_, func, cast, Numeric
    cutoff = datetime.utcnow() - timedelta(days=settings.DEDUP_WINDOW_DAYS)

    # Tier 1: Content hash (exact duplicate)
    existing = await db.execute(
        select(Need).where(
            and_(Need.content_hash == content_hash, Need.created_at >= cutoff)
        )
    )
    if existing.scalar_one_or_none():
        logger.info(f"Dedup tier-1 (hash): {content_hash[:12]}...")
        raise HTTPException(status_code=409, detail="Duplicate need report detected (exact match)")

    # Tier 2: Structural match (same type + same area)
    need_type = extracted.get("need_type")
    if need_type and lat is not None and lng is not None:
        structural = await db.execute(
            select(Need).where(
                and_(
                    Need.need_type == need_type,
                    Need.created_at >= cutoff,
                    Need.latitude.isnot(None),
                    Need.longitude.isnot(None),
                    # Within ~1km (0.01 degrees ≈ 1.1km)
                    func.abs(cast(Need.latitude, Numeric) - lat) < 0.01,
                    func.abs(cast(Need.longitude, Numeric) - lng) < 0.01,
                )
            ).limit(1)
        )
        if structural.scalar_one_or_none():
            logger.info(f"Dedup tier-2 (structural): {need_type} near ({lat:.3f},{lng:.3f})")
            raise HTTPException(
                status_code=409,
                detail=f"Similar {need_type} report already exists in this area within the last {settings.DEDUP_WINDOW_DAYS} days",
            )

    # Tier 3: Semantic match (cosine similarity via pgvector)
    if embedding is not None and lat is not None and lng is not None:
        from pgvector.sqlalchemy import Vector
        semantic = await db.execute(
            select(
                Need.id,
                Need.title,
                Need.embedding.cosine_distance(embedding).label("distance"),
            )
            .where(
                and_(
                    Need.created_at >= cutoff,
                    Need.embedding.isnot(None),
                    Need.latitude.isnot(None),
                    # Within ~5km
                    func.abs(cast(Need.latitude, Numeric) - lat) < 0.05,
                    func.abs(cast(Need.longitude, Numeric) - lng) < 0.05,
                )
            )
            .order_by("distance")
            .limit(1)
        )
        closest = semantic.first()
        if closest and (1.0 - closest.distance) >= settings.DEDUP_COSINE_THRESHOLD:
            similarity = 1.0 - closest.distance
            logger.info(
                f"Dedup tier-3 (semantic): {similarity:.3f} similarity with need {closest.id} "
                f"('{closest.title[:40]}')"
            )
            raise HTTPException(
                status_code=409,
                detail=f"Semantically similar report found (similarity: {similarity:.2f})",
            )


    # Step 5: Create need
    need = Need(
        title=extracted.get("title", raw_text[:100]),
        description=extracted.get("description", raw_text),
        need_type=extracted.get("need_type"),
        location_name=extracted.get("location_hint"),
        latitude=lat,
        longitude=lng,
        urgency_base=extracted.get("urgency", 0.5),
        urgency_current=extracted.get("urgency", 0.5),
        affected_count=extracted.get("affected_count"),
        required_skills=extracted.get("required_skills", []),
        status="new",
        source_channel=source_channel,
        language=extracted.get("original_language", language),
        content_hash=content_hash,
        embedding=embedding,
    )

    db.add(need)
    await db.flush()
    await db.refresh(need)

    logger.info(
        f"✅ Need ingested via {source_channel}: {need.title[:50]} "
        f"(type={need.need_type}, urgency={need.urgency_base})"
    )

    # Step 6: Disaster mode check — detect anomalous report rate
    try:
        from app.services.disaster_service import disaster_service
        disaster_info = await disaster_service.check_for_disaster(need, db)
        if disaster_info:
            logger.warning(f"🚨 Disaster mode triggered by need {need.id}")
    except Exception as e:
        logger.error(f"Disaster check failed (non-blocking): {e}")

    return need


# ─── WhatsApp Webhook ────────────────────────────────────────

@router.post("/ingest/whatsapp", response_model=NeedResponse, status_code=201)
@limiter.limit(RATE_INGESTION)
async def ingest_whatsapp(
    request: Request,
    data: WhatsAppIngest,
    db: AsyncSession = Depends(get_db),
):
    """
    WhatsApp webhook endpoint.
    Handles all message types end-to-end:
      - text: direct extraction
      - audio: auto-transcribed via SpeechService (Cloud Speech → Gemini fallback)
      - image: auto-captioned via Gemini Vision, or uses provided caption
    """
    from app.services.speech_service import speech_service

    raw_text = None

    if data.message_type == "text":
        raw_text = data.text

    elif data.message_type == "audio":
        # Priority: pre-transcribed text → auto-transcribe from URL → fail
        if data.text:
            raw_text = data.text
        elif data.audio_url and speech_service.is_available:
            logger.info(f"🎙️ Auto-transcribing audio from WhatsApp: {data.audio_url[:60]}")
            raw_text = await speech_service.transcribe_from_url(data.audio_url)
            if not raw_text:
                raise HTTPException(
                    status_code=422,
                    detail="Audio transcription failed — could not extract text from voice note",
                )
        else:
            raise HTTPException(
                status_code=400,
                detail="Audio message requires either pre-transcribed text or audio_url with Speech service configured",
            )

    elif data.message_type == "image":
        # Priority: Gemini vision from URL → provided caption → fail
        if data.image_url and gemini_service.is_available:
            logger.info(f"📸 Auto-captioning image from WhatsApp: {data.image_url[:60]}")
            raw_text = await _extract_text_from_image(data.image_url, data.text)
        elif data.text:
            raw_text = data.text
        else:
            raise HTTPException(
                status_code=400,
                detail="Image message requires either image_url with Gemini configured or a text caption",
            )

    if not raw_text or len(raw_text.strip()) < 5:
        raise HTTPException(
            status_code=400,
            detail="Could not extract meaningful text from the message",
        )

    return await _ingest_text(
        raw_text=raw_text,
        source_channel="whatsapp",
        location_hint=data.location,
        db=db,
    )


async def _extract_text_from_image(image_url: str, caption: Optional[str] = None) -> str:
    """
    Use Gemini Vision to extract a humanitarian need description from an image.
    If a caption is provided, it's included as additional context.
    """
    try:
        import httpx
        import asyncio
        import time

        # Download image
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(image_url)
            response.raise_for_status()
            image_bytes = response.content
            content_type = response.headers.get("content-type", "image/jpeg")

        logger.info(f"📥 Downloaded image: {len(image_bytes)} bytes ({content_type})")

        caption_context = f"\nUser caption: {caption}" if caption else ""

        prompt = (
            "You are a humanitarian need analyst for India. "
            "Analyze this image and extract a detailed description of any "
            "community need, disaster, or distress situation visible. "
            "Include: what the problem is, estimated severity, location clues "
            "visible in the image, and number of people potentially affected."
            f"{caption_context}\n\n"
            "Return a clear, factual description suitable for a need report."
        )

        start = time.time()
        response_ai = await asyncio.to_thread(
            gemini_service._model.generate_content,
            [
                prompt,
                {"mime_type": content_type, "data": image_bytes},
            ],
        )
        latency = int((time.time() - start) * 1000)

        text = response_ai.text.strip()
        logger.info(f"📸 Gemini Vision extraction ({latency}ms): '{text[:60]}...'")

        # Log for billing
        await gemini_service.log_gemini_call(
            task_type="vision",
            latency_ms=latency,
            success=True,
            input_tokens=len(image_bytes) // 750,  # rough image token estimate
            output_tokens=len(text) // 4,
        )

        return text

    except Exception as e:
        logger.error(f"Gemini Vision extraction failed: {e}")
        # Fall back to caption if available
        return caption or ""


# ─── Google Forms Webhook ────────────────────────────────────

@router.post("/ingest/forms", response_model=NeedResponse, status_code=201)
@limiter.limit(RATE_INGESTION)
async def ingest_google_form(
    request: Request,
    data: FormIngest,
    db: AsyncSession = Depends(get_db),
):
    """
    Google Forms webhook.
    Concatenates all form responses into a single text for extraction.
    """
    # Build text from form responses
    parts = []
    for question, answer in data.responses.items():
        if answer:
            parts.append(f"{question}: {answer}")

    if not parts:
        raise HTTPException(status_code=400, detail="No form responses provided")

    raw_text = "\n".join(parts)

    return await _ingest_text(
        raw_text=raw_text,
        source_channel="google_forms",
        db=db,
    )


# ─── CSV Bulk Upload ────────────────────────────────────────

@router.post("/ingest/csv", response_model=BulkIngest)
@limiter.limit(RATE_INGESTION)
async def ingest_csv(
    request: Request,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
):
    """
    Bulk import needs from a CSV file.
    Expected columns: title, description, need_type, location, urgency, affected_count, skills
    """
    if not file.filename.endswith(".csv"):
        raise HTTPException(status_code=400, detail="Only CSV files are accepted")

    content = await file.read()
    text = content.decode("utf-8-sig")  # Handle BOM
    reader = csv.DictReader(io.StringIO(text))

    total = 0
    processed = 0
    duplicates = 0
    errors = 0
    need_ids = []

    for row in reader:
        total += 1
        try:
            raw_text = f"{row.get('title', '')}. {row.get('description', '')}"
            if not raw_text.strip(". "):
                errors += 1
                continue

            need = await _ingest_text(
                raw_text=raw_text,
                source_channel="csv_upload",
                db=db,
            )
            need_ids.append(need.id)
            processed += 1

        except HTTPException as e:
            if e.status_code == 409:
                duplicates += 1
            else:
                errors += 1
                logger.warning(f"CSV row {total} failed: {e.detail}")
        except Exception as e:
            errors += 1
            logger.error(f"CSV row {total} error: {e}")

    logger.info(
        f"CSV upload complete: {processed}/{total} processed, "
        f"{duplicates} duplicates, {errors} errors"
    )

    return BulkIngest(
        total_rows=total,
        processed=processed,
        duplicates=duplicates,
        errors=errors,
        need_ids=need_ids,
    )


# ─── Raw Text Ingestion ─────────────────────────────────────

@router.post("/ingest/text", response_model=NeedResponse, status_code=201)
@limiter.limit(RATE_INGESTION)
async def ingest_raw_text(
    request: Request,
    text: str,
    language: str = "auto",
    source: str = "api",
    db: AsyncSession = Depends(get_db),
):
    """
    Direct text ingestion — for testing or API integrations.
    Accepts raw unstructured text and runs through the full pipeline.
    """
    if len(text.strip()) < 10:
        raise HTTPException(status_code=400, detail="Text too short (min 10 chars)")

    return await _ingest_text(
        raw_text=text,
        source_channel=source,
        language=language,
        db=db,
    )



# ─── Offline / Disaster Mode Ingestion ──────────────────────

from pydantic import BaseModel as _BaseModel

class OfflineNeedBody(_BaseModel):
    """JSON body schema for /api/ingest/offline."""
    title: Optional[str] = None
    description: Optional[str] = None
    need_type: Optional[str] = None
    location_name: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    urgency_base: Optional[float] = None
    affected_count: Optional[int] = None
    required_skills: Optional[list] = None
    source_channel: str = "offline"
    language: str = "auto"

    @property
    def as_text(self) -> str:
        parts = []
        if self.title:
            parts.append(self.title)
        if self.description:
            parts.append(self.description)
        return ". ".join(parts)


class RawTextBody(_BaseModel):
    text: str
    language: str = "auto"
    source: str = "api"


@router.post("/ingest/offline", status_code=202)
@limiter.limit(RATE_INGESTION)
async def ingest_offline(
    request: Request,
    body: OfflineNeedBody,
):
    """
    Offline / disaster mode ingestion endpoint.

    Use when:
      - Internet is down but the local server is reachable
      - Gemini API circuit breaker is open
      - Field devices need to submit reports without DB write confirmation

    Reports are:
      1. Immediately triaged by Gemma 4 (local, zero API cost)
      2. Stored in the offline queue (memory + disk)
      3. Synced to the database automatically when connectivity returns

    Returns 202 Accepted with Gemma triage results — no DB write on this call.
    """
    raw_text = body.as_text if hasattr(body, "as_text") else ""
    # Require at minimum a description (title-only is not enough for triage)
    if not body.description or len(body.description.strip()) < 5:
        raise HTTPException(status_code=422, detail="Field 'description' is required for offline ingestion")
    if len(raw_text.strip()) < 5:
        raise HTTPException(status_code=422, detail="Need description or title is required")

    from app.services.offline_queue import offline_queue

    location_hint = (
        {"lat": body.latitude, "lng": body.longitude}
        if body.latitude is not None and body.longitude is not None
        else None
    )

    report = await offline_queue.enqueue(
        raw_text=raw_text,
        source_channel=body.source_channel,
        location_hint=location_hint,
        language=body.language,
        media_type="text",
    )

    return {
        "status": "queued",
        "report_id": report.id,
        "triage_status": report.triage_status,
        "queue_depth": offline_queue.depth,
        "gemma_triage": report.gemma_extraction,
        "message": (
            "Report queued for offline processing. "
            "Will sync to database when connectivity is restored."
        ),
    }



@router.post("/ingest/offline/sync", status_code=200)
async def trigger_offline_sync():
    """
    Manually trigger a sync attempt for all queued offline reports.
    Called automatically when connectivity is restored, or manually by coordinators.
    """
    from app.services.offline_queue import offline_queue
    depth_before = offline_queue.depth
    await offline_queue._attempt_sync()
    return {
        "synced": depth_before - offline_queue.depth,
        "remaining": offline_queue.depth,
        "stats": offline_queue.stats,
    }


@router.get("/ingest/offline/pending")
async def get_offline_pending(limit: int = 50):
    """
    View reports currently in the offline queue (not yet synced to DB).
    Useful for field coordinators to verify reports are captured during outages.
    """
    from app.services.offline_queue import offline_queue
    return {
        "queue_depth": offline_queue.depth,
        "stats": offline_queue.stats,
        "pending_reports": offline_queue.get_pending(limit),
    }


# ─── Alias: /ingest/raw-text and /ingest/google-form ────────


@router.post("/ingest/raw-text", response_model=NeedResponse, status_code=201)
@limiter.limit(RATE_INGESTION)
async def ingest_raw_text_alias(
    request: Request,
    body: RawTextBody,
    db: AsyncSession = Depends(get_db),
):
    """Alias for /ingest/text that accepts a JSON body {text, language, source}."""
    if not body.text or len(body.text.strip()) < 10:
        raise HTTPException(status_code=400, detail="Text too short (min 10 chars)")
    return await _ingest_text(
        raw_text=body.text,
        source_channel=body.source,
        language=body.language,
        db=db,
    )


@router.post("/ingest/google-form", response_model=NeedResponse, status_code=201)
@limiter.limit(RATE_INGESTION)
async def ingest_google_form_alias(
    request: Request,
    data: FormIngest,
    db: AsyncSession = Depends(get_db),
):
    """Alias for /ingest/forms using the hyphenated URL expected by tests/frontend."""
    parts = []
    for question, answer in data.responses.items():
        if answer:
            parts.append(f"{question}: {answer}")
    if not parts:
        raise HTTPException(status_code=400, detail="No form responses provided")
    raw_text = "\n".join(parts)
    return await _ingest_text(
        raw_text=raw_text,
        source_channel="google_forms",
        db=db,
    )


@router.post("/ingest/offline-json", status_code=202)
@limiter.limit(RATE_INGESTION)
async def ingest_offline_json(
    request: Request,
    body: OfflineNeedBody,
):
    """
    JSON-body variant of /ingest/offline for test compatibility.
    Queues a structured need for offline processing.
    """
    raw_text = body.as_text
    if not raw_text or len(raw_text.strip()) < 5:
        raise HTTPException(status_code=422, detail="Need description or title is required")

    from app.services.offline_queue import offline_queue
    location_hint = (
        {"lat": body.latitude, "lng": body.longitude}
        if body.latitude is not None and body.longitude is not None
        else None
    )
    report = await offline_queue.enqueue(
        raw_text=raw_text,
        source_channel=body.source_channel,
        location_hint=location_hint,
        language=body.language,
        media_type="text",
    )
    return {
        "status": "queued",
        "report_id": report.id,
        "triage_status": report.triage_status,
        "queue_depth": offline_queue.depth,
        "message": "Report queued for offline processing.",
    }

