"""
SevaSetu — Feedback Analyzer
Extracts actionable scoring signals from completed assignment feedback.

Problem:
  Rating is a 1-5 float — no nuance.
  Free-text feedback is stored but never analyzed.
  "Nurse came but didn't have the right equipment" →
    - skill match was correct (nursing) ✓
    - resource gap (equipment) was missed ✗
    → future score should weight "has_vehicle/equipment" higher for this need type

What this does:
  After each assignment completes (status=completed), Gemini reads the
  feedback text and extracts:
  1. Was the actual skill match correct? (true/false, overrides tag overlap signal)
  2. What non-skill factors affected the outcome? (language barrier, distance, equipment)
  3. Reliability signal update for the volunteer
  4. Score adjustment suggestions for future matches of this need type

Cost: 1 call per completed assignment, max 200 output tokens.
      Cached for 2h to avoid re-analysis on repeated requests.
"""

import json
import logging
from typing import Dict, Any, Optional
from app.services.llm_cache import llm_cache
from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class FeedbackAnalyzer:
    """Analyzes completed assignment feedback into structured scoring signals."""

    async def analyze(
        self,
        assignment_id: str,
        feedback_text: str,
        rating: float,
        need_type: str,
        need_skills: list,
        volunteer_skills: list,
        volunteer_name: str,
    ) -> Dict[str, Any]:
        """
        Analyze feedback and extract machine-readable scoring signals.
        Returns a structured dict used to update volunteer reliability
        and inform future weight calibration for this need type.
        """
        if not feedback_text or not feedback_text.strip():
            return self._empty_analysis(rating)

        cache_key = f"{assignment_id}:{feedback_text}"
        cached = llm_cache.get("feedback_analysis", cache_key)
        if cached:
            return cached

        from app.services.gemini_service import gemini_service
        if gemini_service.is_available:
            result = await self._gemini_analyze(
                feedback_text, rating, need_type,
                need_skills, volunteer_skills, volunteer_name
            )
        else:
            result = self._rule_based_analyze(feedback_text, rating)

        result["assignment_id"] = assignment_id
        llm_cache.set("feedback_analysis", cache_key, result)
        return result

    async def _gemini_analyze(
        self,
        feedback: str,
        rating: float,
        need_type: str,
        need_skills: list,
        vol_skills: list,
        vol_name: str,
    ) -> Dict[str, Any]:
        """
        Extract structured signals from free-text feedback.
        max_output_tokens=200 — structured JSON response, concise by design.
        """
        prompt = f"""You are analyzing volunteer assignment feedback for a humanitarian platform.
Extract machine-readable signals to improve future matching.

Assignment context:
  Need type: {need_type}
  Required skills: {need_skills}
  Volunteer: {vol_name}, skills: {vol_skills}
  Rating: {rating}/5.0

Feedback text:
  "{feedback}"

Return ONLY this JSON:
{{
  "skill_match_correct": true/false,
  "actual_gap": "what was missing if anything, or null",
  "non_skill_issues": ["language_barrier" | "equipment_gap" | "distance_too_far" | "availability_mismatch" | "other: ..."],
  "volunteer_reliability_signal": "positive" | "negative" | "neutral",
  "suggested_weight_adjustment": {{
    "signal": "geo_proximity" | "skill_tags" | "availability" | null,
    "direction": "increase" | "decrease" | null,
    "reason": "short reason or null"
  }},
  "summary": "one sentence"
}}"""

        try:
            import asyncio
            from app.services.gemini_service import gemini_service
            response = await asyncio.to_thread(
                gemini_service._model.generate_content,
                prompt,
                generation_config={"max_output_tokens": 200}
            )
            text = response.text.strip()
            if text.startswith("```"):
                text = text.split("\n", 1)[1].rsplit("```", 1)[0]
            result = json.loads(text)
            result["source"] = "gemini-1.5-flash"
            logger.info(f"Feedback analysis complete: skill_match={result.get('skill_match_correct')}")
            return result
        except Exception as e:
            logger.error(f"Feedback analysis failed: {e}")
            return self._rule_based_analyze(feedback, rating)

    def _rule_based_analyze(self, feedback: str, rating: float) -> Dict[str, Any]:
        """Simple keyword-based fallback analysis."""
        text = feedback.lower()
        issues = []
        if any(w in text for w in ["language", "hindi", "marathi", "couldn't understand"]):
            issues.append("language_barrier")
        if any(w in text for w in ["far", "late", "distance", "travel"]):
            issues.append("distance_too_far")
        if any(w in text for w in ["equipment", "tools", "medicine", "supplies"]):
            issues.append("equipment_gap")
        if any(w in text for w in ["unavailable", "schedule", "time", "didn't show"]):
            issues.append("availability_mismatch")

        reliability = "positive" if rating >= 4 else ("negative" if rating <= 2 else "neutral")
        # Only flag as skill mismatch when feedback contains explicitly negative skill phrases.
        # Positive mentions like "Excellent nursing skills displayed" should NOT trigger False.
        _negative_skill_phrases = ("wrong skill", "wrong skills", "didn't know", "no skill")
        skill_ok = rating >= 3.5 and not any(p in text for p in _negative_skill_phrases)

        return {
            "skill_match_correct": skill_ok,
            "actual_gap": None,
            "non_skill_issues": issues,
            "volunteer_reliability_signal": reliability,
            "suggested_weight_adjustment": {"signal": None, "direction": None, "reason": None},
            "summary": f"Rating {rating}/5. Issues: {', '.join(issues) or 'none detected'}.",
            "source": "rule-based fallback",
        }

    def _empty_analysis(self, rating: float) -> Dict[str, Any]:
        return {
            "skill_match_correct": rating >= 3.5,
            "actual_gap": None,
            "non_skill_issues": [],
            "volunteer_reliability_signal": "positive" if rating >= 4 else "neutral",
            "suggested_weight_adjustment": {"signal": None, "direction": None, "reason": None},
            "summary": f"No feedback text provided. Rating: {rating}/5.",
            "source": "empty-feedback",
        }


# Singleton
feedback_analyzer = FeedbackAnalyzer()
