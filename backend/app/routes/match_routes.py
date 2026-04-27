"""
SevaSetu — Match & Assignment Routes
Matching, assignment creation, and lifecycle management.
"""

import logging
from uuid import UUID
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_

from app.database import get_db
from app.models.db_models import Need, Volunteer, Assignment
from pydantic import BaseModel, model_validator
from app.models.schemas import (
    AssignmentCreate,
    AssignmentResponse,
    MatchResult,
    ScoreBreakdown,
    VolunteerResponse,
)


class AssignmentStatusUpdate(BaseModel):
    """Body schema for PATCH /assignments/{id}/status."""
    status: str
    rating: Optional[float] = None
    feedback: Optional[str] = None

    @model_validator(mode="after")
    def validate_status(self):
        valid = {"accepted", "in_progress", "completed", "declined", "cancelled"}
        if self.status not in valid:
            raise ValueError(f"status must be one of {sorted(valid)}")
        if self.rating is not None and not (1 <= self.rating <= 5):
            raise ValueError("rating must be between 1 and 5")
        return self
from app.services.matching_engine import matching_engine
from app.services.gemini_service import gemini_service

logger = logging.getLogger(__name__)

router = APIRouter()


def _apply_rating_to_reliability(volunteer, rating: float) -> None:
    """Adjust volunteer reliability based on a numeric 1-5 rating (Gemini fallback)."""
    if volunteer is None or rating is None:
        return
    current = volunteer.reliability if volunteer.reliability is not None else 0.5
    if rating < 2.5:       # 1-2 = negative
        volunteer.reliability = max(0.0, current - 0.05)
    elif rating >= 3.5:    # 4-5 = positive
        volunteer.reliability = min(1.0, current + 0.05)
    # 3 = neutral, no change


# ─── PHASE 1: INSTANT SCORE MATCHES (no LLM) ────────────────

@router.get("/needs/{need_id}/matches")
@router.get("/matching/need/{need_id}", include_in_schema=False)  # alias used by tests
async def find_matches(
    need_id: UUID,
    max_results: int = Query(10, ge=1, le=50),
    radius_km: Optional[float] = Query(None, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
):
    """
    Phase 1: Run the 5-signal matching engine and return instant scores.
    No LLM calls — uses rule-based validation for preliminary verdict.
    Typically completes in < 500ms.
    """
    from app.services.match_cache import match_cache

    # Get the need
    result = await db.execute(select(Need).where(Need.id == need_id))
    need = result.scalar_one_or_none()
    if not need:
        raise HTTPException(status_code=404, detail="Need not found")

    # Run matching engine (scoring only — no LLM)
    matches = await matching_engine.find_matches(
        need=need, db=db, max_results=max_results, radius_km=radius_km
    )

    if not matches:
        return {
            "need_id": str(need_id),
            "matches": [],
            "total_candidates": 0,
            "message": "No available volunteers found in the search radius",
        }

    # Build results with rule-based preliminary validation
    match_results = []
    for m in matches:
        vol = m["volunteer"]
        breakdown = m["score_breakdown"]
        total = breakdown.get("total", 0)

        # Quick rule-based validation (no LLM call)
        skill_overlap = set(need.required_skills or []) & set(vol.skills or [])
        if total >= 0.55:
            prelim_validation = "Valid"
        elif total >= 0.35 or len(skill_overlap) >= 1:
            prelim_validation = "Weak"
        else:
            prelim_validation = "Poor"

        # Check if we have cached LLM analysis for this pair
        cached = match_cache.get(str(need_id), str(vol.id))

        match_results.append({
            "volunteer": {
                "id": str(vol.id),
                "name": vol.name,
                "skills": vol.skills,
                "languages": vol.languages,
                "latitude": vol.latitude,
                "longitude": vol.longitude,
                "reliability": vol.reliability,
                "has_vehicle": vol.has_vehicle,
                "status": vol.status,
            },
            "score": breakdown,
            "llm_analysis": cached["llm_analysis"] if cached else {
                "validation": prelim_validation,
                "confidence": None,
                "signal_explanations": {},
                "algorithm_flags": [],
                "overall_rationale": None,
                "suggested_improvements": None,
                "source": "rule-based (preliminary)",
            },
            "dispatch_brief": cached.get("dispatch_brief") if cached else None,
            "llm_validated": cached is not None,
        })

    # Update need status
    if need.status == "new" and match_results:
        need.status = "matched"
        need.matched_at = datetime.utcnow()
        await db.flush()

    return {
        "need_id": str(need_id),
        "matches": match_results,
        "total_candidates": len(matches),
    }


# ─── PHASE 2: ON-DEMAND LLM EXPLANATION (per volunteer) ─────

@router.get("/needs/{need_id}/matches/{volunteer_id}/explain")
async def explain_match(
    need_id: UUID,
    volunteer_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """
    Phase 2: Get LLM-validated explanation for a single volunteer-need match.
    Results are cached for 30 min — subsequent calls return instantly.
    Called when user clicks "Validate with AI" or expands match details.
    """
    from app.services.match_cache import match_cache

    # Check cache first
    cached = match_cache.get(str(need_id), str(volunteer_id))
    if cached:
        return cached

    # Load need and volunteer
    need_result = await db.execute(select(Need).where(Need.id == need_id))
    need = need_result.scalar_one_or_none()
    if not need:
        raise HTTPException(status_code=404, detail="Need not found")

    vol_result = await db.execute(select(Volunteer).where(Volunteer.id == volunteer_id))
    vol = vol_result.scalar_one_or_none()
    if not vol:
        raise HTTPException(status_code=404, detail="Volunteer not found")

    # Re-score this specific pair to get fresh breakdown
    score_breakdown = await matching_engine._score_volunteer(need, vol)
    from app.services.weight_calibrator import weight_calibrator
    weights = await weight_calibrator.get_weights(
        need_type=need.need_type or "UNKNOWN",
        urgency=need.urgency_current or need.urgency_base or 0.5,
        affected_count=need.affected_count or 0,
        disaster_mode=False,
    )
    total = sum(score_breakdown[s] * weights.get(s, 0) for s in weights)
    reliability_mult = 0.75 + ((vol.reliability or 0.5) * 0.25)
    total *= reliability_mult

    full_breakdown = {
        **{k: round(v, 3) for k, v in score_breakdown.items()},
        "reliability": round(vol.reliability or 0.5, 3),
        "total": round(total, 3),
    }

    # Call LLM for deep validation
    explanation = await gemini_service.validate_and_explain_match(
        need_title=need.title,
        need_type=need.need_type or "UNKNOWN",
        need_skills=need.required_skills or [],
        need_urgency=need.urgency_current or need.urgency_base,
        need_affected_count=need.affected_count,
        need_location=need.location_name or "",
        volunteer_name=vol.name,
        volunteer_skills=vol.skills or [],
        volunteer_languages=vol.languages or [],
        volunteer_reliability=vol.reliability or 0.5,
        volunteer_has_vehicle=vol.has_vehicle or False,
        score_breakdown=full_breakdown,
    )

    # Generate dispatch brief
    dispatch_brief = await gemini_service.generate_dispatch_brief(
        need_title=need.title,
        need_desc=need.description[:200],
        volunteer_name=vol.name,
        volunteer_skills=vol.skills or [],
        location=need.location_name or "Unknown",
        match_score=total,
    )

    result = {
        "llm_analysis": {
            "validation": explanation["validation"],
            "confidence": explanation.get("confidence"),
            "signal_explanations": explanation.get("signal_explanations", {}),
            "algorithm_flags": explanation.get("algorithm_flags", []),
            "overall_rationale": explanation.get("overall_rationale"),
            "suggested_improvements": explanation.get("suggested_improvements"),
            "source": explanation.get("source", "unknown"),
        },
        "dispatch_brief": dispatch_brief,
        "score": full_breakdown,
        "llm_validated": True,
    }

    # Cache for 30 minutes
    match_cache.set(str(need_id), str(volunteer_id), result)
    logger.info(f"✅ LLM explained match {vol.name} ↔ '{need.title[:40]}' (cached)")

    return result



# ─── CREATE ASSIGNMENT ───────────────────────────────────────

@router.post("/assignments", response_model=AssignmentResponse, status_code=201)
async def create_assignment(
    data: AssignmentCreate,
    db: AsyncSession = Depends(get_db),
):
    """
    Create an assignment linking a volunteer to a need.
    Uses SELECT ... FOR UPDATE to prevent double-booking race conditions.
    """
    # ── Lock volunteer row to prevent concurrent assignment ────────────
    # If two coordinators try to assign the same volunteer at the same time,
    # the second request will block here until the first commits.
    vol_result = await db.execute(
        select(Volunteer)
        .where(Volunteer.id == data.volunteer_id)
        .with_for_update()  # Row-level lock — prevents race condition
    )
    volunteer = vol_result.scalar_one_or_none()
    if not volunteer:
        raise HTTPException(status_code=404, detail="Volunteer not found")

    # Check after locking — if another request already assigned this volunteer
    if volunteer.status == "assigned":
        raise HTTPException(
            status_code=409,
            detail="Volunteer is already assigned to another need",
        )

    # ── Lock need row similarly ───────────────────────────────────────
    need_result = await db.execute(
        select(Need)
        .where(Need.id == data.need_id)
        .with_for_update()
    )
    need = need_result.scalar_one_or_none()
    if not need:
        raise HTTPException(status_code=404, detail="Need not found")

    # Check for existing active assignment (same pair)
    existing = await db.execute(
        select(Assignment).where(
            and_(
                Assignment.need_id == data.need_id,
                Assignment.volunteer_id == data.volunteer_id,
                Assignment.status.in_(["proposed", "accepted", "in_progress"]),
            )
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=409,
            detail="Active assignment already exists for this volunteer-need pair",
        )

    assignment = Assignment(
        need_id=data.need_id,
        volunteer_id=data.volunteer_id,
        match_score=data.match_score,
        score_breakdown=data.score_breakdown,
        dispatch_brief=data.dispatch_brief,
        status="proposed",
    )

    db.add(assignment)

    # Update volunteer status (we hold the lock, so this is safe)
    volunteer.status = "assigned"
    volunteer.total_tasks = (volunteer.total_tasks or 0) + 1

    # Update need status
    need.status = "assigned"

    await db.flush()
    await db.refresh(assignment)

    # ── Notify volunteer via FCM ──────────────────────────────────
    from app.services.notification_service import notification_service
    await notification_service.notify_assignment(
        volunteer_fcm_token=getattr(volunteer, 'fcm_token', None),
        volunteer_name=volunteer.name,
        need_title=need.title,
        need_type=need.need_type or "GENERAL",
        assignment_id=str(assignment.id),
        dispatch_brief=data.dispatch_brief,
    )

    return assignment




# ─── UPDATE ASSIGNMENT STATUS ────────────────────────────────

@router.patch("/assignments/{assignment_id}/status", response_model=AssignmentResponse)
async def update_assignment_status(
    assignment_id: UUID,
    body: AssignmentStatusUpdate,
    db: AsyncSession = Depends(get_db),
):
    status = body.status
    rating = body.rating
    feedback = body.feedback
    """Update assignment lifecycle: accepted → in_progress → completed."""
    result = await db.execute(
        select(Assignment).where(Assignment.id == assignment_id)
    )
    assignment = result.scalar_one_or_none()
    if not assignment:
        raise HTTPException(status_code=404, detail="Assignment not found")

    assignment.status = status

    if status == "accepted":
        assignment.accepted_at = datetime.utcnow()

    elif status == "completed":
        assignment.completed_at = datetime.utcnow()
        if rating:
            assignment.rating = rating
        if feedback:
            assignment.feedback = feedback

        # Update volunteer stats
        vol_result = await db.execute(
            select(Volunteer).where(Volunteer.id == assignment.volunteer_id)
        )
        volunteer = vol_result.scalar_one_or_none()

        # ── Feedback Analysis — close the learning loop ───────────────────
        # Gemini reads free-text feedback and extracts structured signals:
        # - Was the skill match actually correct? (overrides tag overlap signal)
        # - Non-skill issues: language barrier, equipment gap, distance too far
        # - Reliability signal: positive/negative/neutral
        # max 200 output tokens, cached 2h per assignment
        need_result = await db.execute(
            select(Need).where(Need.id == assignment.need_id)
        )
        need_for_analysis = need_result.scalar_one_or_none()

        feedback_signals = None
        if feedback and volunteer and need_for_analysis:
            from app.services.feedback_analyzer import feedback_analyzer
            feedback_signals = await feedback_analyzer.analyze(
                assignment_id=str(assignment.id),
                feedback_text=feedback,
                rating=rating or 3.0,
                need_type=need_for_analysis.need_type or "",
                need_skills=need_for_analysis.required_skills or [],
                volunteer_skills=volunteer.skills or [],
                volunteer_name=volunteer.name,
            )
            logger.info(
                f"Feedback analysis: skill_match={feedback_signals.get('skill_match_correct')}, "
                f"reliability={feedback_signals.get('volunteer_reliability_signal')}, "
                f"issues={feedback_signals.get('non_skill_issues')}"
            )

        # ── Fix 2: Close the learning loop ────────────────────────────────
        # Pipe feedback_analyzer's weight adjustment suggestion into the
        # weight calibrator's learning loop. This means REAL field outcomes
        # drive the self-improvement, not just LLM opinions about weights.
        if feedback_signals and need_for_analysis:
            adj = feedback_signals.get("suggested_weight_adjustment", {})
            signal_name = adj.get("signal")
            direction = adj.get("direction")

            if signal_name and direction:
                from app.services.weight_calibrator import weight_calibrator
                # Convert "increase geo_proximity" → delta {geo_proximity: +0.03}
                delta_value = 0.03 if direction == "increase" else -0.03
                context_key = weight_calibrator._context_key(
                    need_for_analysis.need_type or "UNKNOWN",
                    need_for_analysis.urgency_current or need_for_analysis.urgency_base or 0.5,
                    False,  # disaster mode not stored per-need
                )
                weight_calibrator._record_adjustment(
                    context_key,
                    {signal_name: delta_value}
                )
                logger.info(
                    f"📊 Feedback → weight calibrator: {signal_name} {direction} "
                    f"(delta={delta_value:+.3f}) for context '{context_key}'"
                )

        if volunteer:
            volunteer.completed_tasks = (volunteer.completed_tasks or 0) + 1
            volunteer.status = "available"
            # Adjust reliability based on feedback signals, anchored to current value
            current_reliability = volunteer.reliability if volunteer.reliability is not None else 0.5

            # Primary: use Gemini-extracted reliability signal
            if feedback_signals and feedback_signals.get("volunteer_reliability_signal") == "positive":
                current_reliability = min(1.0, current_reliability + 0.05)
            elif feedback_signals and feedback_signals.get("volunteer_reliability_signal") == "negative":
                current_reliability = max(0.0, current_reliability - 0.05)
            # Fallback: use numeric rating when Gemini is unavailable
            elif rating is not None:
                if rating < 2.5:
                    current_reliability = max(0.0, current_reliability - 0.05)  # poor rating
                elif rating >= 3.5:
                    current_reliability = min(1.0, current_reliability + 0.05)  # good rating
            # Else: no feedback signals, no rating → keep existing reliability

            volunteer.reliability = current_reliability



        # Update need status
        need_result = await db.execute(
            select(Need).where(Need.id == assignment.need_id)
        )
        need = need_result.scalar_one_or_none()
        if need:
            need.status = "completed"
            need.resolved_at = datetime.utcnow()

    elif status in ("declined", "cancelled"):
        # Free volunteer
        vol_result = await db.execute(
            select(Volunteer).where(Volunteer.id == assignment.volunteer_id)
        )
        volunteer = vol_result.scalar_one_or_none()
        if volunteer:
            volunteer.status = "available"

    await db.flush()
    await db.refresh(assignment)
    return assignment


# ─── LIST ASSIGNMENTS ────────────────────────────────────────

@router.get("/assignments", response_model=list[AssignmentResponse])
async def list_assignments(
    status: Optional[str] = Query(None),
    need_id: Optional[UUID] = Query(None),
    volunteer_id: Optional[UUID] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """List assignments with optional filters."""
    query = select(Assignment)
    filters = []

    if status:
        filters.append(Assignment.status == status)
    if need_id:
        filters.append(Assignment.need_id == need_id)
    if volunteer_id:
        filters.append(Assignment.volunteer_id == volunteer_id)

    if filters:
        query = query.where(and_(*filters))

    offset = (page - 1) * page_size
    query = query.order_by(Assignment.proposed_at.desc()).offset(offset).limit(page_size)

    result = await db.execute(query)
    return result.scalars().all()


# ─── GET SINGLE ASSIGNMENT ───────────────────────────────────

@router.get("/assignments/{assignment_id}", response_model=AssignmentResponse)
async def get_assignment(
    assignment_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Get a single assignment by ID."""
    result = await db.execute(select(Assignment).where(Assignment.id == assignment_id))
    assignment = result.scalar_one_or_none()
    if not assignment:
        raise HTTPException(status_code=404, detail="Assignment not found")
    return assignment


# ─── SUBMIT FEEDBACK ON ASSIGNMENT ───────────────────────────

class AssignmentFeedbackBody(BaseModel):
    """Body schema for PATCH /assignments/{id}/feedback."""
    rating: float
    feedback: str = ""

    @model_validator(mode="after")
    def validate_rating(self):
        if not (1 <= self.rating <= 5):
            raise ValueError("rating must be between 1 and 5")
        return self


@router.patch("/assignments/{assignment_id}/feedback", response_model=AssignmentResponse)
async def submit_assignment_feedback(
    assignment_id: UUID,
    body: AssignmentFeedbackBody,
    db: AsyncSession = Depends(get_db),
):
    """Submit feedback and rating for a completed assignment, updating volunteer reliability."""
    result = await db.execute(select(Assignment).where(Assignment.id == assignment_id))
    assignment = result.scalar_one_or_none()
    if not assignment:
        raise HTTPException(status_code=404, detail="Assignment not found")

    assignment.rating = body.rating
    if body.feedback:
        assignment.feedback = body.feedback

    # Update volunteer reliability based on feedback
    vol_result = await db.execute(
        select(Volunteer).where(Volunteer.id == assignment.volunteer_id)
    )
    volunteer = vol_result.scalar_one_or_none()

    need_result = await db.execute(
        select(Need).where(Need.id == assignment.need_id)
    )
    need = need_result.scalar_one_or_none()

    if volunteer and need and body.feedback:
        from app.services.feedback_analyzer import feedback_analyzer
        feedback_signals = await feedback_analyzer.analyze(
            assignment_id=str(assignment.id),
            feedback_text=body.feedback,
            rating=body.rating,
            need_type=need.need_type or "",
            need_skills=need.required_skills or [],
            volunteer_skills=volunteer.skills or [],
            volunteer_name=volunteer.name,
        )
        if feedback_signals:
            signal = feedback_signals.get("volunteer_reliability_signal", "neutral")
            current_reliability = volunteer.reliability if volunteer.reliability is not None else 0.5
            if signal == "positive":
                current_reliability = min(1.0, current_reliability + 0.05)
            elif signal == "negative":
                current_reliability = max(0.0, current_reliability - 0.05)
            volunteer.reliability = current_reliability
        else:
            # Gemini unavailable — fall back to numeric rating
            _apply_rating_to_reliability(volunteer, body.rating)
    elif volunteer and body.rating is not None:
        # No feedback text → still apply rating-based adjustment
        _apply_rating_to_reliability(volunteer, body.rating)

    await db.flush()
    await db.refresh(assignment)
    return assignment
