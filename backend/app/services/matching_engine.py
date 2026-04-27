"""
SevaSetu — 5-Signal Matching Engine
Matches volunteers to needs using a weighted multi-signal scoring system.

Signals:
  1. Skill Embedding (30%) — Cosine similarity of pgvector embeddings
  2. Skill Tags (25%)     — Jaccard overlap of explicit skill/need tags
  3. Geo Proximity (20%)  — Inverse of travel time (actual or estimated)
  4. Urgency Weight (15%) — Higher urgency needs get priority boost
  5. Availability (10%)   — Schedule overlap with current time
"""

import logging
import math
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_

from app.config import get_settings
from app.models.db_models import Need, Volunteer, Assignment
from app.services.embedding_service import embedding_service
from app.services.geocoding_service import geocoding_service
from app.services.gemini_service import gemini_service
from app.services.weight_calibrator import weight_calibrator, DEFAULT_WEIGHTS
from app.services.skill_normalizer import skill_normalizer

logger = logging.getLogger(__name__)
settings = get_settings()


class MatchingEngine:
    """5-signal volunteer-need matching with LLM-calibrated dynamic weights."""

    def __init__(self):
        # Default weights — overridden per-need by weight_calibrator
        self.weights = DEFAULT_WEIGHTS

    # ─── Main Match Pipeline ─────────────────────────────────

    async def find_matches(
        self,
        need: Need,
        db: AsyncSession,
        max_results: int = 10,
        radius_km: float = None,
    ) -> List[Dict[str, Any]]:
        """
        Find the best volunteer matches for a given need.
        Returns a ranked list of {volunteer, score_breakdown, total_score}.
        """
        radius = radius_km or settings.DEFAULT_SEARCH_RADIUS_KM

        # Step 1: Get candidate volunteers (available + within radius)
        candidates = await self._get_candidates(need, db, radius)
        if not candidates:
            logger.info(f"No candidates found within {radius}km for need {need.id}")
            return []

        logger.info(f"Found {len(candidates)} candidates for need {need.id}")

        # Step 2: Get context-appropriate weights for THIS need
        # Low-cardinality cache key: (need_type, urgency_tier, disaster_mode)
        # Static context map covers ~80% of cases at 0 token cost
        active_weights = await weight_calibrator.get_weights(
            need_type=need.need_type or "UNKNOWN",
            urgency=need.urgency_current or need.urgency_base or 0.5,
            affected_count=need.affected_count or 0,
            disaster_mode=False,  # TODO: wire disaster_mode from system state
        )
        logger.debug(f"Using weights for {need.need_type}: {active_weights}")

        # Step 3: Score each candidate (parallel — geo calls are concurrent)
        import asyncio

        async def _score_one(volunteer):
            breakdown = await self._score_volunteer(need, volunteer)
            total = sum(
                breakdown[signal] * active_weights.get(signal, 0)
                for signal in active_weights
            )
            # Apply reliability multiplier (0.5-1.0 range → 0.75-1.0 multiplier)
            reliability_mult = 0.75 + (volunteer.reliability * 0.25)
            total *= reliability_mult
            return {
                "volunteer": volunteer,
                "score_breakdown": {
                    "skill_embedding": round(breakdown["skill_embedding"], 3),
                    "skill_tags": round(breakdown["skill_tags"], 3),
                    "geo_proximity": round(breakdown["geo_proximity"], 3),
                    "urgency": round(breakdown["urgency"], 3),
                    "availability": round(breakdown["availability"], 3),
                    "reliability": round(volunteer.reliability, 3),
                    "total": round(total, 3),
                    "weights_used": active_weights,  # expose for transparency
                },
                "total_score": round(total, 3),
            }

        scored = await asyncio.gather(*[_score_one(v) for v in candidates])
        scored = list(scored)

        # Step 4: Sort by total descending and limit
        scored.sort(key=lambda x: x["total_score"], reverse=True)
        return scored[:max_results]

    # ─── Candidate Selection ─────────────────────────────────

    async def _get_candidates(
        self, need: Need, db: AsyncSession, radius_km: float
    ) -> List[Volunteer]:
        """Get available volunteers within a geographic bounding box."""
        query = select(Volunteer).where(Volunteer.status == "available")

        # Geo bounding box if need has coordinates
        if need.latitude and need.longitude:
            deg_per_km = 0.009
            lat_range = radius_km * deg_per_km
            lng_range = radius_km * deg_per_km / max(0.1, math.cos(math.radians(need.latitude)))

            query = query.where(
                and_(
                    Volunteer.latitude.isnot(None),
                    Volunteer.longitude.isnot(None),
                    Volunteer.latitude.between(
                        need.latitude - lat_range,
                        need.latitude + lat_range,
                    ),
                    Volunteer.longitude.between(
                        need.longitude - lng_range,
                        need.longitude + lng_range,
                    ),
                )
            )

        query = query.limit(settings.MAX_MATCH_CANDIDATES)
        result = await db.execute(query)
        return list(result.scalars().all())

    # ─── Signal Scoring ──────────────────────────────────────

    async def _score_volunteer(self, need: Need, volunteer: Volunteer) -> Dict[str, float]:
        """Calculate all 5 signal scores for a volunteer-need pair."""
        return {
            "skill_embedding": self._score_skill_embedding(need, volunteer),
            "skill_tags": self._score_skill_tags(need, volunteer),
            "geo_proximity": await self._score_geo_proximity(need, volunteer),
            "urgency": self._score_urgency(need),
            "availability": self._score_availability(volunteer),
        }

    def _score_skill_embedding(self, need: Need, volunteer: Volunteer) -> float:
        """
        Signal 1: Cosine similarity of skill embeddings (0-1).
        Uses pgvector embeddings if available, otherwise computes on-the-fly.
        """
        # Use stored embeddings if available
        if need.embedding and volunteer.embedding:
            need_vec = list(need.embedding) if hasattr(need.embedding, '__iter__') else []
            vol_vec = list(volunteer.embedding) if hasattr(volunteer.embedding, '__iter__') else []
            if need_vec and vol_vec:
                return max(0, embedding_service.cosine_similarity(need_vec, vol_vec))

        # Compute on-the-fly
        need_text = f"{need.need_type or ''} {' '.join(need.required_skills or [])}"
        vol_text = f"{' '.join(volunteer.skills or [])} {volunteer.experience_text or ''}"

        if not need_text.strip() or not vol_text.strip():
            return 0.0

        need_vec = embedding_service.encode(need_text)
        vol_vec = embedding_service.encode(vol_text)
        return max(0, embedding_service.cosine_similarity(need_vec, vol_vec))

    def _score_skill_tags(self, need: Need, volunteer: Volunteer) -> float:
        """
        Signal 2: Normalized Jaccard similarity of explicit skill tags (0-1).
        Synonyms are resolved before comparison — "pipe_repair" == "plumbing".
        """
        return skill_normalizer.normalized_jaccard(
            need_skills=need.required_skills or [],
            vol_skills=volunteer.skills or [],
        )

    async def _score_geo_proximity(self, need: Need, volunteer: Volunteer) -> float:
        """
        Signal 3: Inverse of travel time, normalized to 0-1.
        1.0 = same location, 0.0 = beyond reasonable distance.
        """
        if not (need.latitude and need.longitude and
                volunteer.latitude and volunteer.longitude):
            return 0.5  # Unknown location — neutral score

        travel_time = await geocoding_service.get_travel_time(
            (volunteer.latitude, volunteer.longitude),
            (need.latitude, need.longitude),
        )

        if travel_time is None:
            # Fallback: straight-line distance
            travel_time = geocoding_service._fallback_travel_time(
                (volunteer.latitude, volunteer.longitude),
                (need.latitude, need.longitude),
            )

        # Normalize: 0 min → 1.0, 60+ min → ~0.0
        # Using exponential decay: score = e^(-travel_time/30)
        return math.exp(-travel_time / 30)

    def _score_urgency(self, need: Need) -> float:
        """
        Signal 4: Urgency weight (0-1).
        Higher urgency needs get higher scores to prioritize matching.
        """
        return need.urgency_current or need.urgency_base or 0.5

    def _score_availability(self, volunteer: Volunteer) -> float:
        """
        Signal 5: Schedule overlap with current time (0-1).
        1.0 = available right now, 0.5 = available today but not now, 0.0 = not available today.
        """
        if not volunteer.availability:
            return 0.7  # No schedule set → assume generally available

        now = datetime.utcnow()
        day_name = now.strftime("%a").lower()[:3]  # mon, tue, etc.
        current_hour = now.hour

        day_schedule = volunteer.availability.get(day_name)
        if not day_schedule or len(day_schedule) < 2:
            return 0.0  # Not available today

        start_hour, end_hour = day_schedule[0], day_schedule[1]
        if start_hour <= current_hour <= end_hour:
            return 1.0  # Available right now
        elif abs(current_hour - start_hour) <= 2 or abs(current_hour - end_hour) <= 2:
            return 0.6  # Close to availability window
        return 0.3  # Available today but far from current time

    # ─── Validation ──────────────────────────────────────────

    async def validate_match(
        self, need: Need, volunteer: Volunteer, score: float
    ) -> str:
        """Get AI-powered match quality assessment."""
        return await gemini_service.validate_match(
            need_type=need.need_type or "",
            need_skills=need.required_skills or [],
            volunteer_skills=volunteer.skills or [],
            score=score,
        )

    # ─── Urgency Decay ───────────────────────────────────────

    def compute_urgency_decay(self, need: Need) -> float:
        """
        Compute urgency decay: unaddressed needs become MORE urgent over time.
        Formula: urgency_current = urgency_base + decay_rate × hours_elapsed
        Capped at 1.0.
        """
        if not need.created_at:
            return need.urgency_base

        hours_elapsed = (datetime.utcnow() - need.created_at).total_seconds() / 3600
        decayed = need.urgency_base + (settings.URGENCY_DECAY_RATE * (hours_elapsed / 24))
        return min(1.0, decayed)


# Singleton
matching_engine = MatchingEngine()
