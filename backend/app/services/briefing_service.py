"""
SevaSetu — Proactive Regional Briefing Service
Shifts the system from reactive dispatch to predictive resource planning.

What it does:
  Analyzes active needs grouped by geographic region (ward/zone) and:
  1. Detects skill gaps (high demand for skills with few available volunteers)
  2. Predicts which regions will hit critical urgency in the next 12-24h
  3. Identifies need type concentrations (5 HEALTHCARE in the same ward → trend)
  4. Surfaces "quiet zones" where no needs have been reported (potential blind spots)
  5. Generates coordinator action briefings

Triggered:
  - Every 6 hours via POST /api/system/regional-briefing
  - Manually by coordinators from the dashboard
  - Automatically when disaster mode activates

Cost:
  - Uses gemini-1.5-pro (better reasoning for complex analysis)
  - 1 call per 6h per region cluster
  - Cached for 6h (TTL = 21600s)
  - Token budget: 800 output tokens
"""

import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from collections import defaultdict

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_

from app.models.db_models import Need, Volunteer
from app.services.llm_cache import llm_cache
from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

# Geographic clustering: round to 0.1° ≈ 10km cells
GEO_RESOLUTION = 0.1


class BriefingService:
    """Generates proactive coordinator briefings based on need corpus patterns."""

    def __init__(self):
        self._pro_model = None
        if settings.GEMINI_API_KEY:
            try:
                import google.generativeai as genai
                # Use Pro model for complex regional reasoning (low frequency call)
                self._pro_model = genai.GenerativeModel("gemini-1.5-flash")
                logger.info("✅ Briefing service: gemini-1.5-flash initialized")
            except Exception as e:
                logger.warning(f"⚠️ Briefing model init failed: {e}")

    async def generate_regional_briefing(self, db: AsyncSession) -> Dict[str, Any]:
        """
        Main entry point — analyze corpus and generate coordinator briefings.
        Returns structured briefing with alerts, predictions, and actions.
        """
        # ── Step 1: Gather corpus metrics ────────────────────────────────────
        metrics = await self._compute_corpus_metrics(db)

        # ── Step 2: Cache key = snapshot hash, TTL = 6h ──────────────────────
        cache_key = json.dumps(
            {k: v for k, v in metrics.items() if k != "geo_clusters"},
            sort_keys=True, default=str
        )
        cached = llm_cache.get("area_briefing", cache_key)
        if cached:
            logger.info("Briefing cache hit — returning cached analysis")
            return cached

        # ── Step 3: LLM analysis or rule-based fallback ───────────────────────
        if self._pro_model:
            briefing = await self._gemini_briefing(metrics)
        else:
            briefing = self._rule_based_briefing(metrics)

        briefing["generated_at"] = datetime.utcnow().isoformat()
        briefing["corpus_snapshot"] = {
            "total_active": metrics["total_active"],
            "critical": metrics["critical_count"],
            "regions_analyzed": len(metrics["geo_clusters"]),
        }

        llm_cache.set("area_briefing", cache_key, briefing)
        return briefing

    async def _compute_corpus_metrics(self, db: AsyncSession) -> Dict[str, Any]:
        """Pull aggregate statistics from the DB without calling the LLM."""
        # Active unresolved needs
        needs_result = await db.execute(
            select(Need).where(Need.status.in_(["new", "matched"]))
        )
        active_needs = needs_result.scalars().all()

        # Available volunteers
        vols_result = await db.execute(
            select(Volunteer).where(Volunteer.status == "available")
        )
        volunteers = vols_result.scalars().all()

        # ── Geographic clustering ─────────────────────────────────────────────
        geo_clusters: Dict[str, List[Dict]] = defaultdict(list)
        type_counts: Dict[str, int] = defaultdict(int)
        critical_count = 0
        skill_demand: Dict[str, int] = defaultdict(int)

        for n in active_needs:
            if n.need_type:
                type_counts[n.need_type] += 1
            if n.urgency_current and n.urgency_current >= settings.URGENCY_CRITICAL_THRESHOLD:
                critical_count += 1
            for skill in (n.required_skills or []):
                skill_demand[skill] += 1

            # Group by geo cell
            if n.latitude and n.longitude:
                cell = (
                    round(n.latitude / GEO_RESOLUTION) * GEO_RESOLUTION,
                    round(n.longitude / GEO_RESOLUTION) * GEO_RESOLUTION,
                )
                geo_clusters[str(cell)].append({
                    "id": str(n.id),
                    "type": n.need_type,
                    "urgency": round(n.urgency_current or n.urgency_base, 2),
                    "affected": n.affected_count,
                    "age_hours": round(
                        (datetime.utcnow() - n.created_at).total_seconds() / 3600, 1
                    ) if n.created_at else None,
                })

        # ── Skill supply vs demand gap ────────────────────────────────────────
        skill_supply: Dict[str, int] = defaultdict(int)
        for v in volunteers:
            for skill in (v.skills or []):
                skill_supply[skill] += 1

        skill_gaps = {
            skill: {"demand": demand, "supply": skill_supply.get(skill, 0)}
            for skill, demand in skill_demand.items()
            if skill_supply.get(skill, 0) < demand
        }

        return {
            "total_active": len(active_needs),
            "critical_count": critical_count,
            "total_volunteers_available": len(volunteers),
            "type_distribution": dict(type_counts),
            "skill_gaps": skill_gaps,
            "geo_clusters": {
                cell: {
                    "need_count": len(needs),
                    "needs": needs[:5],  # sample for LLM, not full list
                    "avg_urgency": round(
                        sum(n["urgency"] for n in needs) / len(needs), 2
                    ) if needs else 0,
                }
                for cell, needs in geo_clusters.items()
            },
        }

    async def _gemini_briefing(self, metrics: Dict) -> Dict[str, Any]:
        """
        Generate actionable coordinator briefing using Gemini Pro.
        Token budget: 800 output tokens.
        """
        # Prepare a condensed summary to keep the prompt small
        top_clusters = sorted(
            metrics["geo_clusters"].items(),
            key=lambda x: x[1]["avg_urgency"] * x[1]["need_count"],
            reverse=True
        )[:5]  # Top 5 hotspot regions only

        prompt = f"""You are a humanitarian coordination analyst for India.
Analyze this data snapshot from SevaSetu's active need corpus and generate a coordinator briefing.

=== SNAPSHOT ===
Active needs: {metrics['total_active']}
Critical (urgency ≥ 0.95): {metrics['critical_count']}
Available volunteers: {metrics['total_volunteers_available']}
Need types: {json.dumps(metrics['type_distribution'])}

Top 5 geographic hotspots (cell_coords: {{need_count, avg_urgency}}):
{json.dumps({cell: {'needs': info['need_count'], 'avg_urgency': info['avg_urgency']} for cell, info in top_clusters}, indent=2)}

Skill gaps (demand > supply):
{json.dumps(metrics['skill_gaps'], indent=2)}

=== GENERATE ===
Return ONLY valid JSON:
{{
  "priority_alerts": [
    {{"region": "description", "issue": "what's wrong", "action": "what to do now", "urgency": "critical|high|medium"}}
  ],
  "skill_gap_alerts": [
    {{"skill": "skill_name", "demand": 0, "supply": 0, "recommendation": "recruit X more nurses for Y area"}}
  ],
  "trend_observations": ["observation 1", "observation 2"],
  "predicted_escalations": [
    {{"description": "what will likely become critical", "timeframe": "within Xh"}}
  ],
  "coordinator_actions": ["specific action 1", "specific action 2"]
}}"""

        try:
            import asyncio
            response = await asyncio.to_thread(
                self._pro_model.generate_content,
                prompt,
                generation_config={"max_output_tokens": 800}
            )
            text = response.text.strip()
            if text.startswith("```"):
                text = text.split("\n", 1)[1].rsplit("```", 1)[0]
            result = json.loads(text)
            result["source"] = "gemini-1.5-flash"
            logger.info("Regional briefing generated by Gemini")
            return result
        except Exception as e:
            logger.error(f"Gemini briefing failed: {e}")
            return self._rule_based_briefing(metrics)

    def _rule_based_briefing(self, metrics: Dict) -> Dict[str, Any]:
        """Fallback briefing built purely from metrics — no LLM required."""
        alerts = []
        if metrics["critical_count"] > 0:
            alerts.append({
                "region": "System-wide",
                "issue": f"{metrics['critical_count']} needs have reached critical urgency",
                "action": "Immediate coordinator review required",
                "urgency": "critical",
            })

        skill_alerts = [
            {
                "skill": skill,
                "demand": info["demand"],
                "supply": info["supply"],
                "recommendation": f"Recruit {info['demand'] - info['supply']} more {skill} volunteers",
            }
            for skill, info in metrics["skill_gaps"].items()
        ]

        dominant_type = max(
            metrics["type_distribution"].items(), key=lambda x: x[1], default=("UNKNOWN", 0)
        )

        return {
            "priority_alerts": alerts,
            "skill_gap_alerts": skill_alerts[:5],
            "trend_observations": [
                f"Highest volume need type: {dominant_type[0]} ({dominant_type[1]} active needs)",
                f"Total active: {metrics['total_active']}, available volunteers: {metrics['total_volunteers_available']}",
            ],
            "predicted_escalations": [],
            "coordinator_actions": [
                f"Address {metrics['critical_count']} critical needs immediately" if metrics["critical_count"] else "No critical needs at this time",
                "Review skill gap roster and recruit accordingly",
            ],
            "source": "rule-based fallback",
        }


# Singleton
briefing_service = BriefingService()
