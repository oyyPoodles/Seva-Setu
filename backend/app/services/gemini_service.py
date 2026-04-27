"""
SevaSetu — Gemini AI Service
Need extraction, validation, and dispatch brief generation via Google Gemini.
Falls back to rule-based extraction when API key is not configured.
"""

import json
import logging
import time
from datetime import datetime
from typing import Dict, Any, Optional, List
from uuid import uuid4

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class GeminiService:
    """Google Gemini AI integration for intelligent need processing."""

    # Circuit breaker config
    MAX_CONSECUTIVE_FAILURES = 5
    CIRCUIT_RESET_SECONDS = 300  # 5 minutes

    def __init__(self):
        self._model = None
        self._available = False

        # Circuit breaker state
        self._consecutive_failures = 0
        self._circuit_open_since = None
        self._total_calls = 0
        self._total_failures = 0
        self._total_fallbacks = 0
        self._last_error = None

        if settings.GEMINI_API_KEY:
            try:
                import google.generativeai as genai
                genai.configure(api_key=settings.GEMINI_API_KEY)
                # gemini-2.5-flash is available on this project's free tier
                # (gemini-2.0-flash shows limit:0 for this key)
                self._model = genai.GenerativeModel("gemini-2.5-flash")
                self._available = True
                logger.info("✅ Gemini AI service initialized (gemini-2.5-flash)")
            except Exception as e:
                logger.warning(f"⚠️ Gemini init failed: {e}. Using rule-based fallback.")
        else:
            logger.info("ℹ️ No GEMINI_API_KEY — using rule-based extraction")

    @property
    def is_available(self) -> bool:
        """Check if Gemini is available AND circuit is not open."""
        if not self._available:
            return False
        if self._circuit_open_since:
            elapsed = time.time() - self._circuit_open_since
            if elapsed < self.CIRCUIT_RESET_SECONDS:
                return False  # Circuit still open
            # Auto-reset: try again after cooldown
            self._circuit_open_since = None
            self._consecutive_failures = 0
            logger.info("🔄 Gemini circuit breaker reset — retrying API calls")
        return True

    @property
    def health_metrics(self) -> dict:
        """Expose health metrics for the /health endpoint."""
        return {
            "configured": self._available,
            "circuit_open": self._circuit_open_since is not None,
            "consecutive_failures": self._consecutive_failures,
            "total_calls": self._total_calls,
            "total_failures": self._total_failures,
            "total_fallbacks": self._total_fallbacks,
            "last_error": str(self._last_error)[:100] if self._last_error else None,
        }

    def _record_success(self):
        """Reset failure counter on successful call."""
        self._consecutive_failures = 0
        self._total_calls += 1

    def _record_failure(self, error: Exception):
        """Track failure and potentially trip circuit breaker."""
        self._consecutive_failures += 1
        self._total_failures += 1
        self._total_calls += 1
        self._total_fallbacks += 1
        self._last_error = error

        if self._consecutive_failures >= self.MAX_CONSECUTIVE_FAILURES:
            self._circuit_open_since = time.time()
            logger.critical(
                f"🚨 GEMINI CIRCUIT BREAKER TRIPPED — {self._consecutive_failures} "
                f"consecutive failures. Falling back to rule-based for "
                f"{self.CIRCUIT_RESET_SECONDS}s. Last error: {error}"
            )

    async def log_gemini_call(
        self,
        task_type: str,
        latency_ms: int,
        success: bool,
        input_tokens: int = 0,
        output_tokens: int = 0,
        error_message: Optional[str] = None,
    ):
        """
        Persist a GeminiCall record to the database for billing tracking.
        Fire-and-forget — failures are logged but never block the request.
        """
        try:
            from app.database import AsyncSessionLocal
            from app.models.db_models import GeminiCall

            async with AsyncSessionLocal() as session:
                call = GeminiCall(
                    model="gemini-1.5-flash",
                    task_type=task_type,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    latency_ms=latency_ms,
                    success=success,
                    error_message=error_message[:500] if error_message else None,
                )
                session.add(call)
                await session.commit()
        except Exception as e:
            # Never let logging break the main flow
            logger.debug(f"GeminiCall log failed (non-blocking): {e}")

    # ─── Need Extraction ─────────────────────────────────────

    async def extract_need(self, raw_text: str, language: str = "auto") -> Dict[str, Any]:
        """
        Extract structured need data from unstructured text.
        Input: WhatsApp message, form response, or free text.
        Output: {title, description, need_type, urgency, skills, location_hint, affected_count}
        """
        if self.is_available:
            return await self._gemini_extract(raw_text, language)
        # Tier 2: Gemma 4 local (zero cost, offline capable)
        from app.services.gemma_service import gemma_service
        if gemma_service.is_available:
            result = await gemma_service.extract_need(raw_text)
            if result:
                return result
        # Tier 3: keyword rules
        return self._fallback_extract(raw_text)

    async def _gemini_extract(self, raw_text: str, language: str) -> Dict[str, Any]:
        """Use Gemini to extract structured need data."""
        prompt = f"""You are a humanitarian need classifier for India.
Extract structured information from this community report.

Report text: "{raw_text}"
Detected language: {language}

Return ONLY valid JSON with these fields:
{{
  "title": "short descriptive title (max 100 chars, in English)",
  "description": "detailed description (in English)",
  "need_type": "one of: HEALTHCARE, EDUCATION, WATER_SANITATION, SHELTER, FOOD, INFRASTRUCTURE, LIVELIHOOD",
  "urgency": 0.0 to 1.0 (1.0 = life-threatening emergency),
  "required_skills": ["skill1", "skill2"],
  "location_hint": "location mentioned in text or null",
  "affected_count": estimated number of people affected or null,
  "original_language": "detected language code (hi, en, mr, ta, etc.)"
}}"""

        start = time.time()
        try:
            import asyncio
            response = await asyncio.to_thread(
                self._model.generate_content, prompt
            )
            latency = int((time.time() - start) * 1000)

            # Parse JSON from response
            text = response.text.strip()
            if text.startswith("```"):
                text = text.split("\n", 1)[1].rsplit("```", 1)[0]

            result = json.loads(text)
            self._record_success()
            logger.info(f"Gemini extraction completed in {latency}ms")
            await self.log_gemini_call(
                task_type="extract", latency_ms=latency, success=True,
                input_tokens=len(prompt) // 4, output_tokens=len(text) // 4,
            )
            return result

        except Exception as e:
            latency = int((time.time() - start) * 1000)
            self._record_failure(e)
            logger.error(f"Gemini extraction failed: {e}")
            await self.log_gemini_call(
                task_type="extract", latency_ms=latency, success=False,
                error_message=str(e),
            )
            # Tier 2: try Gemma before keyword rules
            from app.services.gemma_service import gemma_service
            if gemma_service.is_available:
                result = await gemma_service.extract_need(raw_text)
                if result:
                    return result
            return self._fallback_extract(raw_text)


    def _fallback_extract(self, raw_text: str) -> Dict[str, Any]:
        """Rule-based extraction when Gemini is unavailable."""
        text_lower = raw_text.lower()

        # Detect need type from keywords
        type_keywords = {
            "HEALTHCARE": ["hospital", "doctor", "medicine", "health", "medical", "nurse",
                          "sick", "disease", "fever", "injury", "ambulance", "clinic"],
            "EDUCATION": ["school", "teacher", "education", "study", "books", "tutor",
                         "student", "learning", "exam", "college"],
            "WATER_SANITATION": ["water", "toilet", "sanitation", "drain", "sewage",
                                "pump", "bore", "well", "pipeline", "tap"],
            "SHELTER": ["shelter", "house", "roof", "home", "building", "wall",
                       "collapse", "homeless", "tent", "displaced"],
            "FOOD": ["food", "hunger", "meal", "ration", "grain", "rice", "nutrition",
                    "starvation", "feeding", "kitchen"],
            "INFRASTRUCTURE": ["road", "bridge", "electricity", "power", "light",
                              "repair", "construction", "damaged"],
            "LIVELIHOOD": ["job", "work", "employment", "skill", "training", "income",
                          "livelihood", "business", "loan"],
        }

        need_type = "INFRASTRUCTURE"  # default
        max_matches = 0
        for ntype, keywords in type_keywords.items():
            matches = sum(1 for kw in keywords if kw in text_lower)
            if matches > max_matches:
                max_matches = matches
                need_type = ntype

        # Estimate urgency from keywords
        urgency = 0.5
        critical_words = ["emergency", "urgent", "dying", "critical", "flood",
                         "fire", "collapse", "immediate", "danger", "life"]
        high_words = ["broken", "damaged", "disrupted", "no supply", "stuck"]
        urgency_hits = sum(1 for w in critical_words if w in text_lower)
        if urgency_hits >= 2:
            urgency = 0.95
        elif urgency_hits == 1:
            urgency = 0.85
        elif any(w in text_lower for w in high_words):
            urgency = 0.7

        # Extract skills needed
        skill_map = {
            "HEALTHCARE": ["nursing", "first_aid", "medical"],
            "WATER_SANITATION": ["plumbing", "water_purification"],
            "SHELTER": ["carpentry", "construction"],
            "FOOD": ["cooking", "driving"],
            "EDUCATION": ["teaching", "counseling"],
            "INFRASTRUCTURE": ["electrical", "construction"],
            "LIVELIHOOD": ["counseling", "data_entry"],
        }

        # Extract numbers for affected count
        import re
        numbers = re.findall(r'\b(\d+)\s*(?:people|families|persons|affected|households)', text_lower)
        affected = int(numbers[0]) if numbers else None

        title = raw_text[:100].strip()
        if len(raw_text) > 100:
            title = title[:97] + "..."

        return {
            "title": title,
            "description": raw_text,
            "need_type": need_type,
            "urgency": urgency,
            "required_skills": skill_map.get(need_type, []),
            "location_hint": None,
            "affected_count": affected,
            "original_language": "en",
        }

    # ─── Dispatch Brief Generation ───────────────────────────

    async def generate_dispatch_brief(
        self,
        need_title: str,
        need_desc: str,
        volunteer_name: str,
        volunteer_skills: List[str],
        location: str,
        match_score: float,
    ) -> str:
        """Generate a concise dispatch briefing for a volunteer."""
        if self._available:
            return await self._gemini_dispatch(
                need_title, need_desc, volunteer_name,
                volunteer_skills, location, match_score
            )
        # Tier 2: Gemma 4 local
        from app.services.gemma_service import gemma_service
        if gemma_service.is_available:
            brief = await gemma_service.generate_dispatch_brief(
                need_title, need_desc, volunteer_name,
                volunteer_skills, location, match_score
            )
            if brief:
                return brief
        # Tier 3: template
        return self._fallback_dispatch(
            need_title, volunteer_name, volunteer_skills, location
        )

    async def _gemini_dispatch(
        self, title: str, desc: str, vol_name: str,
        skills: List[str], location: str, score: float,
    ) -> str:
        prompt = f"""Generate a brief, actionable dispatch message for a volunteer.

Need: {title}
Details: {desc}
Volunteer: {vol_name}
Skills: {', '.join(skills)}
Location: {location}
Match confidence: {score:.0%}

Write 2-3 sentences: what the situation is, what they should do, and any safety notes.
Keep it under 200 characters. Be direct and practical."""

        start = time.time()
        try:
            import asyncio
            response = await asyncio.to_thread(
                self._model.generate_content, prompt
            )
            latency = int((time.time() - start) * 1000)
            result_text = response.text.strip()
            self._record_success()
            await self.log_gemini_call(
                task_type="dispatch", latency_ms=latency, success=True,
                input_tokens=len(prompt) // 4, output_tokens=len(result_text) // 4,
            )
            return result_text
        except Exception as e:
            latency = int((time.time() - start) * 1000)
            self._record_failure(e)
            logger.error(f"Dispatch brief generation failed: {e}")
            await self.log_gemini_call(
                task_type="dispatch", latency_ms=latency, success=False,
                error_message=str(e),
            )
            from app.services.gemma_service import gemma_service
            if gemma_service.is_available:
                brief = await gemma_service.generate_dispatch_brief(
                    title, desc, vol_name, skills, location, score
                )
                if brief:
                    return brief
            return self._fallback_dispatch(title, vol_name, skills, location)

    def _fallback_dispatch(
        self, title: str, vol_name: str,
        skills: List[str], location: str,
    ) -> str:
        skill_str = ", ".join(skills[:2]) if skills else "general assistance"
        loc_str = f" at {location}" if location else ""
        return f"Hi {vol_name}, you've been matched to: {title}{loc_str}. Your skills in {skill_str} are needed. Please confirm availability."

    # ─── Deep Score Validation + Explanation ─────────────────
    # This is where the LLM does REAL work — it receives the full
    # numeric score breakdown and reasons about each signal, then
    # either endorses or overrides the algorithmic match.

    async def validate_and_explain_match(
        self,
        need_title: str,
        need_type: str,
        need_skills: List[str],
        need_urgency: float,
        need_affected_count: Optional[int],
        need_location: str,
        volunteer_name: str,
        volunteer_skills: List[str],
        volunteer_languages: List[str],
        volunteer_reliability: float,
        volunteer_has_vehicle: bool,
        score_breakdown: Dict[str, float],
    ) -> Dict[str, Any]:
        """
        The LLM receives the actual numeric score breakdown and every
        relevant field. It must:
          1. Validate the overall match ("Valid" | "Weak" | "Poor")
          2. Explain WHY each signal is high or low in plain English
          3. Flag any data inconsistencies the algorithm missed
          4. Suggest what additional info would strengthen this match

        This is grounded reasoning over the real data, not narrative.
        """
        if self._available:
            return await self._gemini_validate_deep(
                need_title, need_type, need_skills, need_urgency,
                need_affected_count, need_location,
                volunteer_name, volunteer_skills, volunteer_languages,
                volunteer_reliability, volunteer_has_vehicle,
                score_breakdown,
            )
        # Tier 2: Gemma 4 local validation
        from app.services.gemma_service import gemma_service
        if gemma_service.is_available:
            result = await gemma_service.validate_match(
                need_title, need_type, need_skills, need_urgency,
                volunteer_skills, volunteer_reliability,
                volunteer_has_vehicle, score_breakdown,
            )
            if result:
                return result
        # Tier 3: rule-based
        return self._fallback_validate_deep(need_skills, volunteer_skills, score_breakdown)

    async def _gemini_validate_deep(
        self,
        need_title: str, need_type: str, need_skills: List[str],
        need_urgency: float, need_affected_count: Optional[int], need_location: str,
        vol_name: str, vol_skills: List[str], vol_languages: List[str],
        vol_reliability: float, vol_has_vehicle: bool,
        scores: Dict[str, float],
    ) -> Dict[str, Any]:
        """
        Send all factual data to Gemini and ask it to reason about
        the algorithmic scoring — validating and explaining it.
        """
        prompt = f"""You are a helpful field coordinator assistant for SevaSetu, a humanitarian aid platform in India.
The system matched a volunteer to a community need. Your job is to explain this match in simple, plain language
that a non-technical coordinator can understand. DO NOT use technical terms like "Jaccard", "cosine similarity",
"semantic score", "embedding", "algorithm", or raw numbers like "0.45/1.0". Write like you're advising a colleague.

=== THE NEED ===
Title: {need_title}
Type: {need_type}
Required Skills: {', '.join(need_skills) or 'None specified'}
How urgent: {self._urgency_label(need_urgency)}
People affected: {need_affected_count or 'Unknown'}
Location: {need_location or 'Unknown'}

=== THE VOLUNTEER ===
Name: {vol_name}
Skills: {', '.join(vol_skills) or 'None listed'}
Languages: {', '.join(vol_languages) or 'Unknown'}
Track record: {vol_reliability:.0%} tasks completed successfully
Has vehicle: {'Yes' if vol_has_vehicle else 'No'}

=== SYSTEM MATCH SCORES (for your reference, do NOT expose these numbers to the user) ===
Skills relevance: {scores.get('skill_embedding', 0):.0%}
Direct skill match: {scores.get('skill_tags', 0):.0%}
Distance/proximity: {scores.get('geo_proximity', 0):.0%}
Urgency level: {scores.get('urgency', 0):.0%}
Availability: {scores.get('availability', 0):.0%}
Overall match: {scores.get('total', 0):.0%}

=== YOUR TASK ===
Return ONLY valid JSON with these fields. All text must be in simple, friendly language:
{{
  "validation": "Valid" | "Weak" | "Poor",
  "confidence": 0.0 to 1.0,
  "signal_explanations": {{
    "skill_embedding": "explain in plain words whether this volunteer's experience fits the need",
    "skill_tags": "explain which specific skills they share (or don't) with what's needed",
    "geo_proximity": "explain roughly how far away they are and what that means for response time",
    "urgency": "explain how urgent this need is and whether quick response matters here",
    "availability": "explain whether this volunteer is free and ready to help right now"
  }},
  "algorithm_flags": ["list concerns in plain language — e.g., 'They don't speak the local language', 'No vehicle but the location is remote'"],
  "overall_rationale": "2-3 simple sentences explaining WHY this is a good/weak/poor match, like advice to a colleague",
  "suggested_improvements": "what extra info would help make a better decision"
}}"""

        start = time.time()
        try:
            import asyncio
            response = await asyncio.to_thread(
                self._model.generate_content, prompt
            )
            latency = int((time.time() - start) * 1000)

            text = response.text.strip()
            if text.startswith("```"):
                text = text.split("\n", 1)[1].rsplit("```", 1)[0]

            result = json.loads(text)
            result["latency_ms"] = latency
            result["source"] = "gemini-1.5-flash"
            self._record_success()
            logger.info(
                f"Gemini deep validation: {result.get('validation')} "
                f"(confidence={result.get('confidence'):.2f}) in {latency}ms"
            )
            await self.log_gemini_call(
                task_type="validate", latency_ms=latency, success=True,
                input_tokens=len(prompt) // 4, output_tokens=len(text) // 4,
            )
            return result

        except Exception as e:
            latency = int((time.time() - start) * 1000)
            self._record_failure(e)
            logger.error(f"Gemini deep validation failed: {e}")
            await self.log_gemini_call(
                task_type="validate", latency_ms=latency, success=False,
                error_message=str(e),
            )
            from app.services.gemma_service import gemma_service
            if gemma_service.is_available:
                result = await gemma_service.validate_match(
                    need_title, need_type,
                    need_skills if need_skills else [],
                    need_urgency,
                    vol_skills if vol_skills else [],
                    vol_reliability, vol_has_vehicle, scores,
                )
                if result:
                    return result
            return self._fallback_validate_deep(
                need_skills if need_skills else [],
                vol_skills if vol_skills else [],
                scores
            )

    def _urgency_label(self, urgency: float) -> str:
        if urgency >= 0.95: return "CRITICAL — life threatening"
        if urgency >= 0.85: return "HIGH — immediate action needed"
        if urgency >= 0.70: return "ELEVATED — action within hours"
        if urgency >= 0.50: return "MODERATE — action within days"
        return "LOW — can queue"

    def _fallback_validate_deep(
        self,
        need_skills: List[str],
        vol_skills: List[str],
        scores: Dict[str, float],
    ) -> Dict[str, Any]:
        """
        Rule-based fallback when Gemini is unavailable.
        Generates plain-language explanations for non-technical coordinators.
        """
        skill_overlap = set(need_skills) & set(vol_skills)
        total = scores.get("total", 0)
        geo = scores.get("geo_proximity", 0)
        tag_score = scores.get("skill_tags", 0)
        urgency = scores.get("urgency", 0)
        avail = scores.get("availability", 0)
        skill_emb = scores.get("skill_embedding", 0)

        # Determine validation tier
        if total >= 0.55 and len(skill_overlap) >= 1:
            validation = "Valid"
        elif total >= 0.55:
            validation = "Valid"  # 55%+ even without exact tag match is still valid
        elif total >= 0.35 or len(skill_overlap) >= 1:
            validation = "Weak"
        else:
            validation = "Poor"

        # ── Human-friendly explanations per signal ──
        # Skills — experience match
        if skill_emb > 0.7:
            skill_emb_text = "This volunteer's experience is a strong match for what's needed."
        elif skill_emb > 0.4:
            skill_emb_text = "This volunteer has some relevant experience, but not a perfect fit."
        else:
            skill_emb_text = "This volunteer's background doesn't closely match the required skills."

        # Skills — direct overlap
        if skill_overlap:
            overlap_list = ", ".join(skill_overlap)
            if tag_score > 0.5:
                skill_tag_text = f"Great news — they have direct skills in: {overlap_list}."
            else:
                skill_tag_text = f"They share some skills ({overlap_list}), but the need requires more."
        else:
            skill_tag_text = "No direct skill overlap found. Their experience may still be relevant — check their profile."

        # Proximity — travel time
        est_minutes = int((1 - geo) * 60)
        if geo > 0.8:
            geo_text = f"Very close by — roughly {est_minutes} min away. Can reach quickly."
        elif geo > 0.5:
            geo_text = f"Moderate distance — about {est_minutes} min travel time."
        elif geo > 0.3:
            geo_text = f"Somewhat far — around {est_minutes} min away. May cause delays."
        else:
            geo_text = f"Far away — estimated {est_minutes}+ min travel. Consider someone closer if possible."

        # Urgency
        if urgency >= 0.85:
            urgency_text = "This is a high-urgency need — immediate action is needed."
        elif urgency >= 0.6:
            urgency_text = "Moderate urgency — should be addressed within a few hours."
        else:
            urgency_text = "Lower urgency — can be scheduled for later."

        # Availability
        if avail > 0.7:
            avail_text = "This volunteer is available and ready to help."
        elif avail > 0.3:
            avail_text = "Partially available — their schedule may have some conflicts."
        else:
            avail_text = "Limited availability right now — they may not be able to respond immediately."

        # ── Overall rationale (human-readable) ──
        if validation == "Valid":
            rationale = (
                f"This looks like a good match. "
                f"{'They have the right skills (' + ', '.join(skill_overlap) + ')' if skill_overlap else 'Their experience aligns reasonably'}"
                f" and they're close enough to respond quickly."
            )
        elif validation == "Weak":
            reasons = []
            if not skill_overlap:
                reasons.append("no direct skill match")
            if geo < 0.5:
                reasons.append("they're somewhat far away")
            if avail < 0.5:
                reasons.append("limited availability")
            rationale = (
                f"This is a possible match, but has some concerns: {', '.join(reasons) if reasons else 'scores are borderline'}. "
                f"Consider this volunteer if no better option is available."
            )
        else:
            rationale = (
                "This doesn't appear to be a strong match. "
                "The volunteer may lack the required skills or be too far away to respond in time. "
                "We recommend looking for alternatives."
            )

        # ── Flags (plain language) ──
        flags = []
        if not skill_overlap:
            flags.append("This volunteer doesn't have any of the specifically requested skills")
        if geo < 0.3:
            flags.append("They are quite far from the location — response time could be long")
        if avail == 0:
            flags.append("They may not be available right now")

        return {
            "validation": validation,
            "confidence": round(min(0.9, total + 0.1), 2),
            "signal_explanations": {
                "skill_embedding": skill_emb_text,
                "skill_tags": skill_tag_text,
                "geo_proximity": geo_text,
                "urgency": urgency_text,
                "availability": avail_text,
            },
            "algorithm_flags": flags,
            "overall_rationale": rationale,
            "suggested_improvements": "Getting the volunteer's exact location, verified skill certificates, and real-time availability would help make better matches.",
            "source": "rule-based fallback",
        }

    # ─── Legacy simple validation (backward compat) ──────────

    async def validate_match(
        self, need_type: str, need_skills: List[str],
        volunteer_skills: List[str], score: float,
    ) -> str:
        """Simple 3-tier validation — use validate_and_explain_match for full reasoning."""
        skill_overlap = len(set(need_skills) & set(volunteer_skills))
        if score >= 0.7 and skill_overlap >= 1:
            return "Valid"
        elif score >= 0.4 or skill_overlap >= 1:
            return "Weak"
        return "Poor"


# Singleton
gemini_service = GeminiService()

