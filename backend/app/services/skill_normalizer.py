"""
SevaSetu — Skill Normalizer (Hybrid + Self-Improving)
Resolves skill synonyms to canonical vocabulary before Jaccard scoring.

Hybrid architecture:
  1. Base synonym map (hardcoded, 0 API cost) — handles common aliases
  2. LLM resolution for unknowns — grounded in what the base map already knows
  3. Auto-update: LLM mappings AND conflict corrections are applied to the
     in-memory map + persisted to disk

Self-improving:
  - New LLM-resolved mappings get added to the live map → no repeat calls
  - LLM-detected conflicts (wrong base map entries) get corrected in-place
  - Persisted to data/learned_skills.json → survives restarts
  - Bounded naturally: skill vocabulary grows slowly (~10 new aliases/month)
"""

import json
import logging
import os
from typing import Dict, List, Set
from app.services.llm_cache import llm_cache

logger = logging.getLogger(__name__)

# Persistence path
_BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
LEARNED_SKILLS_PATH = os.path.join(_BACKEND_DIR, "data", "learned_skills.json")

# ─── Base synonym map (rule-based, zero API cost) ────────────────────────────
SKILL_SYNONYMS: Dict[str, str] = {
    # Healthcare
    "rn": "nursing", "registered_nurse": "nursing", "nurse": "nursing",
    "emt": "first_aid", "paramedic": "first_aid", "emergency_medical": "first_aid",
    "doctor": "medical", "physician": "medical", "gp": "medical",
    "counsellor": "counseling", "therapist": "counseling", "psychologist": "counseling",

    # Water & Infrastructure
    "pipe_repair": "plumbing", "pipe_fitting": "plumbing", "plumber": "plumbing",
    "water_treatment": "water_purification", "water_testing": "water_purification",
    "electrician": "electrical", "electric_work": "electrical",
    "mason": "construction", "bricklayer": "construction", "carpenter": "carpentry",

    # Education
    "teacher": "teaching", "tutor": "teaching", "instructor": "teaching",
    "trainer": "teaching",

    # Logistics / General
    "driver": "driving", "vehicle_operator": "driving",
    "data_entry_operator": "data_entry", "typist": "data_entry",
    "cook": "cooking", "chef": "cooking",
    "translator": "translation", "interpreter": "translation",

    # Hindi/regional synonyms → English canonical
    "swasthya": "medical", "prathmik_chikitsa": "first_aid",
    "paani": "water_purification", "nalkoop": "plumbing",
}


class SkillNormalizer:
    """
    Normalizes raw skill strings to canonical vocabulary.
    Base map first → LLM for unknowns → auto-update map from LLM results.
    """

    def __init__(self):
        self._load_learned_skills()

    # ─── Persistence ──────────────────────────────────────────────────────────

    def _load_learned_skills(self) -> None:
        """
        Load previously learned skill mappings from disk on startup.
        These override/extend the hardcoded SKILL_SYNONYMS.
        """
        if os.path.exists(LEARNED_SKILLS_PATH):
            try:
                with open(LEARNED_SKILLS_PATH, "r") as f:
                    learned = json.load(f)
                count = 0
                for alias, canonical in learned.items():
                    if alias and canonical:
                        SKILL_SYNONYMS[alias.lower()] = canonical.lower()
                        count += 1
                if count:
                    logger.info(f"📂 Loaded {count} learned skill mappings from disk")
            except Exception as e:
                logger.warning(f"⚠️ Failed to load learned skills: {e}")

    def _save_learned_skills(self, new_mappings: Dict[str, str]) -> None:
        """
        Persist newly learned mappings to disk (append to sidecar file).
        Only stores LLM-discovered mappings, not the base hardcoded ones.
        """
        os.makedirs(os.path.dirname(LEARNED_SKILLS_PATH), exist_ok=True)
        try:
            existing = {}
            if os.path.exists(LEARNED_SKILLS_PATH):
                with open(LEARNED_SKILLS_PATH, "r") as f:
                    existing = json.load(f)
            existing.update(new_mappings)
            with open(LEARNED_SKILLS_PATH, "w") as f:
                json.dump(existing, f, indent=2)
            logger.info(f"📂 Saved {len(new_mappings)} new skill mappings to disk")
        except Exception as e:
            logger.error(f"Failed to save learned skills: {e}")

    # ─── Core normalization ───────────────────────────────────────────────────

    def normalize_skill(self, skill: str) -> str:
        """
        Map a single skill string to its canonical form.
        Order: exact match → lowercase in map → as-is
        """
        clean = skill.strip().lower().replace(" ", "_")
        return SKILL_SYNONYMS.get(clean, clean)

    def normalize_skill_set(self, skills: List[str]) -> Set[str]:
        """Normalize a full list and return a deduplicated set."""
        return {self.normalize_skill(s) for s in (skills or [])}

    async def normalize_with_llm(
        self, unknown_skills: List[str], canonical_vocabulary: List[str]
    ) -> Dict[str, str]:
        """
        Hybrid resolution for unknown skills.
        LLM sees the base map + unknowns. Returns mappings AND conflict flags.
        New mappings and corrections are auto-applied to SKILL_SYNONYMS in-memory
        AND persisted to disk for future calls.
        """
        if not unknown_skills:
            return {}

        cache_key = f"{sorted(unknown_skills)}:{sorted(canonical_vocabulary)}"
        cached = llm_cache.get("skill_synonyms", cache_key)
        if cached:
            return cached

        from app.services.gemini_service import gemini_service
        if not gemini_service.is_available:
            logger.debug("Gemini unavailable for skill normalization — using as-is")
            return {s: s for s in unknown_skills}

        base_map_sample = dict(list(SKILL_SYNONYMS.items())[:20])

        prompt = f"""You are validating a skill synonym resolver for a humanitarian volunteer platform in India.

Our base synonym map already handles common cases. Here's a sample:
{json.dumps(base_map_sample, indent=2)}

Canonical vocabulary in the system: {json.dumps(canonical_vocabulary)}

New unknown skills to resolve (not in our base map):
{json.dumps(unknown_skills)}

For each unknown skill:
1. If it maps to something in our canonical vocabulary → use that
2. If it's a Hindi/regional language term → translate and map to canonical
3. If genuinely unknown → return as-is

Also flag if any of the unknown skills CONFLICT with our existing base map
(e.g., a regional term we've mapped incorrectly).

Return ONLY JSON:
{{
  "mappings": {{"unknown_skill": "canonical_or_self"}},
  "conflicts": [{{"skill": "...", "our_mapping": "...", "suggested_correction": "..."}}]
}}"""

        try:
            import asyncio
            response = await asyncio.to_thread(
                gemini_service._model.generate_content,
                prompt,
                generation_config={"max_output_tokens": 400}
            )
            text = response.text.strip()
            if text.startswith("```"):
                text = text.split("\n", 1)[1].rsplit("```", 1)[0]

            result = json.loads(text)
            mapping = result.get("mappings", {s: s for s in unknown_skills})
            conflicts = result.get("conflicts", [])

            # ── Auto-update: apply new mappings to the live map ───────────
            new_learned = {}
            for alias, canonical in mapping.items():
                clean_alias = alias.strip().lower().replace(" ", "_")
                clean_canonical = canonical.strip().lower().replace(" ", "_")
                if clean_alias != clean_canonical and clean_alias not in SKILL_SYNONYMS:
                    SKILL_SYNONYMS[clean_alias] = clean_canonical
                    new_learned[clean_alias] = clean_canonical

            # ── Auto-correct: apply conflict corrections ──────────────────
            for conflict in conflicts:
                skill = conflict.get("skill", "").strip().lower().replace(" ", "_")
                correction = conflict.get("suggested_correction", "").strip().lower().replace(" ", "_")
                if skill and correction and skill in SKILL_SYNONYMS:
                    old_mapping = SKILL_SYNONYMS[skill]
                    SKILL_SYNONYMS[skill] = correction
                    new_learned[skill] = correction
                    logger.warning(
                        f"🔧 Skill map auto-corrected: '{skill}': "
                        f"'{old_mapping}' → '{correction}' (LLM conflict fix)"
                    )

            # Persist all new/corrected mappings
            if new_learned:
                self._save_learned_skills(new_learned)
                logger.info(
                    f"Skill map updated: {len(new_learned)} new/corrected entries "
                    f"(total map size: {len(SKILL_SYNONYMS)})"
                )

            llm_cache.set("skill_synonyms", cache_key, mapping)
            return mapping

        except Exception as e:
            logger.error(f"Skill hybrid normalization failed: {e}")
            return {s: s for s in unknown_skills}

    def normalized_jaccard(self, need_skills: List[str], vol_skills: List[str]) -> float:
        """
        Compute Jaccard similarity after normalizing both skill sets.
        Replaces the raw Jaccard in matching_engine._score_skill_tags.
        """
        norm_need = self.normalize_skill_set(need_skills)
        norm_vol = self.normalize_skill_set(vol_skills)

        if not norm_need or not norm_vol:
            return 0.0

        intersection = norm_need & norm_vol
        union = norm_need | norm_vol
        return len(intersection) / len(union) if union else 0.0

    def get_map_snapshot(self) -> Dict:
        """Return current state of the skill synonym map for monitoring."""
        return {
            "total_entries": len(SKILL_SYNONYMS),
            "learned_file_exists": os.path.exists(LEARNED_SKILLS_PATH),
            "sample": dict(list(SKILL_SYNONYMS.items())[:15]),
        }


# Singleton
skill_normalizer = SkillNormalizer()

