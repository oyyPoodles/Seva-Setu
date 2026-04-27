"""
SevaSetu — Hybrid Weight Calibrator
A true hybrid model: static rules + LLM validation + self-improving feedback loop.

Current system (TIERED — NOT hybrid):
  Context → Static hit? → YES: return static (done)
                        → NO:  Gemini generates from scratch

Problem with tiered:
  - When Gemini fires, it generates 5 numbers from zero context about what the
    static rules encoded. High variance, more tokens, no continuity.
  - Static rules and Gemini reasoning are disconnected — neither learns from
    what the other has done.

True Hybrid Architecture:
  ┌─────────────────────────────────────────────────┐
  │  STATIC   always computes a base answer          │
  │    ↓                                             │
  │  LLM      receives base + context, responds:     │
  │           • "ENDORSED" (base is correct)         │
  │           • or delta adjustments                 │
  │    ↓                                             │
  │  Final = base + LLM delta                        │
  │    ↓                                             │
  │  LEARNING: If delta for same context recurs      │
  │  ≥ N times → update the static map itself        │
  └─────────────────────────────────────────────────┘

Why this is better than purely tiered:
  1. LLM's reasoning is grounded ("adjust from 0.35, not guess 0.35")
  2. Smaller prompts → fewer tokens → lower variance
  3. Static map becomes smarter over time through LLM feedback
  4. If LLM is down, static base weights still valid (graceful fallback)
  5. Endorsement response is shorter than generation (saves tokens)
"""

import json
import logging
from collections import defaultdict
from typing import Dict, List, Tuple

from app.config import get_settings
from app.services.llm_cache import llm_cache

logger = logging.getLogger(__name__)
settings = get_settings()

SIGNALS = ["skill_embedding", "skill_tags", "geo_proximity", "urgency", "availability"]

# ─── Base static weights ──────────────────────────────────────────────────────
# These are the STARTING POINT for every calibration.
# LLM adjusts from here; never from zero.

DEFAULT_WEIGHTS: Dict[str, float] = {
    "skill_embedding": settings.MATCH_WEIGHT_SKILL_EMBEDDING,
    "skill_tags":      settings.MATCH_WEIGHT_SKILL_TAGS,
    "geo_proximity":   settings.MATCH_WEIGHT_GEO_PROXIMITY,
    "urgency":         settings.MATCH_WEIGHT_URGENCY,
    "availability":    settings.MATCH_WEIGHT_AVAILABILITY,
}

STATIC_CONTEXT_WEIGHTS: Dict[str, Dict[str, float]] = {
    "critical_disaster": {
        "skill_embedding": 0.20,
        "skill_tags":      0.30,
        "geo_proximity":   0.35,
        "urgency":         0.10,
        "availability":    0.05,
    },
    "high_normal": {
        "skill_embedding": 0.25,
        "skill_tags":      0.30,
        "geo_proximity":   0.25,
        "urgency":         0.12,
        "availability":    0.08,
    },
    "HEALTHCARE_moderate": {
        "skill_embedding": 0.35,
        "skill_tags":      0.35,
        "geo_proximity":   0.15,
        "urgency":         0.10,
        "availability":    0.05,
    },
    "EDUCATION_moderate": {
        "skill_embedding": 0.25,
        "skill_tags":      0.25,
        "geo_proximity":   0.15,
        "urgency":         0.10,
        "availability":    0.25,
    },
    "FOOD_critical": {
        "skill_embedding": 0.15,
        "skill_tags":      0.25,
        "geo_proximity":   0.35,
        "urgency":         0.15,
        "availability":    0.10,
    },
    "WATER_SANITATION_critical": {
        "skill_embedding": 0.20,
        "skill_tags":      0.35,
        "geo_proximity":   0.25,
        "urgency":         0.12,
        "availability":    0.08,
    },
}

# ─── Adjustment memory for self-improvement ───────────────────────────────────
# Tracks LLM deltas per context key.
# When the same adjustment recurs ≥ LEARNING_THRESHOLD times,
# the static map is updated in-place.
LEARNING_THRESHOLD = 5

# Sliding window: keep at most this many entries per context key.
# Once a learning event fires (threshold met → static map updated),
# that key's history is cleared entirely.
# Between learning events, old entries are dropped as new ones arrive.
# Bounded at: max_contexts(42) × WINDOW_SIZE(10) × ~120 bytes = ~50KB forever.
WINDOW_SIZE = LEARNING_THRESHOLD * 2  # 10 entries max per context

# Persistence paths (inside the backend directory, next to .env)
import os
_BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
LEARNING_STATE_PATH = os.path.join(_BACKEND_DIR, "data", "learning_state.json")
LEARNED_WEIGHTS_PATH = os.path.join(_BACKEND_DIR, "data", "learned_weights.json")


class WeightCalibrator:
    """
    Hybrid model: static base → LLM validate/adjust → static map auto-updates.
    Learning state persists to disk with bounded sliding window.
    """

    def __init__(self):
        self._adjustment_history: Dict[str, List[Dict[str, float]]] = defaultdict(list)
        self._load_state()  # Restore learning progress from disk

    # ─── Persistence ──────────────────────────────────────────────────────────

    def _ensure_data_dir(self) -> None:
        os.makedirs(os.path.dirname(LEARNING_STATE_PATH), exist_ok=True)

    def _load_state(self) -> None:
        """
        Load persisted learning state and evolved weights on startup.
        If the file is corrupted or missing, start fresh — no crash.
        Also runs compaction to enforce the sliding window on stale data.
        """
        # Load adjustment history
        if os.path.exists(LEARNING_STATE_PATH):
            try:
                with open(LEARNING_STATE_PATH, "r") as f:
                    raw = json.load(f)
                # Enforce window size on load (compaction)
                for key, entries in raw.items():
                    self._adjustment_history[key] = entries[-WINDOW_SIZE:]
                total_entries = sum(len(v) for v in self._adjustment_history.values())
                logger.info(
                    f"📂 Loaded learning state: {len(self._adjustment_history)} contexts, "
                    f"{total_entries} total entries (window={WINDOW_SIZE})"
                )
            except Exception as e:
                logger.warning(f"⚠️ Failed to load learning state: {e} — starting fresh")
                self._adjustment_history = defaultdict(list)

        # Load evolved static weights (overrides the hardcoded defaults)
        if os.path.exists(LEARNED_WEIGHTS_PATH):
            try:
                with open(LEARNED_WEIGHTS_PATH, "r") as f:
                    learned = json.load(f)
                updated = 0
                for map_key, weights in learned.items():
                    # Only apply if all 5 signals are present and sum ~1.0
                    if set(SIGNALS).issubset(weights.keys()):
                        total = sum(weights[k] for k in SIGNALS)
                        if 0.95 <= total <= 1.05:
                            STATIC_CONTEXT_WEIGHTS[map_key] = {
                                k: round(weights[k], 3) for k in SIGNALS
                            }
                            updated += 1
                if updated:
                    logger.info(f"📂 Loaded {updated} learned weight contexts from disk")
            except Exception as e:
                logger.warning(f"⚠️ Failed to load learned weights: {e} — using hardcoded")

    def _save_state(self) -> None:
        """
        Persist current learning state to disk.
        Called after every adjustment recording and every learning event.
        Enforces sliding window before saving to keep file bounded.
        """
        self._ensure_data_dir()
        try:
            # Compact before saving: enforce window per key
            compacted = {
                key: entries[-WINDOW_SIZE:]
                for key, entries in self._adjustment_history.items()
                if entries  # skip empty keys
            }
            with open(LEARNING_STATE_PATH, "w") as f:
                json.dump(compacted, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save learning state: {e}")

    def _save_learned_weights(self) -> None:
        """
        Persist the evolved static context weights.
        Called only when a learning event fires (threshold met).
        """
        self._ensure_data_dir()
        try:
            with open(LEARNED_WEIGHTS_PATH, "w") as f:
                json.dump(STATIC_CONTEXT_WEIGHTS, f, indent=2)
            logger.info("📂 Saved evolved static weights to disk")
        except Exception as e:
            logger.error(f"Failed to save learned weights: {e}")

    # ─── Helpers ─────────────────────────────────────────────────────────────

    def _urgency_tier(self, urgency: float) -> str:
        if urgency >= 0.95: return "critical"
        if urgency >= 0.70: return "high"
        return "moderate"

    def _context_key(self, need_type: str, urgency: float, disaster: bool) -> str:
        return f"{need_type}:{self._urgency_tier(urgency)}:{'disaster' if disaster else 'normal'}"

    def _get_static_base(self, need_type: str, urgency: float, disaster: bool) -> Tuple[Dict[str, float], str]:
        """
        ALWAYS returns a base weight set.
        Returns (weights, source_label) — source_label for audit trail.
        """
        tier = self._urgency_tier(urgency)

        if disaster and urgency >= 0.85:
            return STATIC_CONTEXT_WEIGHTS["critical_disaster"], "critical_disaster"
        if tier == "high":
            return STATIC_CONTEXT_WEIGHTS["high_normal"], "high_normal"

        type_key = f"{need_type}_{tier}"
        if type_key in STATIC_CONTEXT_WEIGHTS:
            return STATIC_CONTEXT_WEIGHTS[type_key], type_key

        return DEFAULT_WEIGHTS, "default"

    def _apply_delta(self, base: Dict[str, float], delta: Dict[str, float]) -> Dict[str, float]:
        """
        Add LLM delta adjustments to the static base.
        Re-normalizes to ensure sum = 1.0 after applying delta.
        """
        adjusted = {k: max(0.0, base[k] + delta.get(k, 0.0)) for k in SIGNALS}
        total = sum(adjusted.values())
        if total > 0:
            adjusted = {k: round(v / total, 3) for k, v in adjusted.items()}
        return adjusted

    # ─── Learning loop (bounded + persistent) ─────────────────────────────────

    def _record_adjustment(self, context_key: str, delta: Dict[str, float]) -> None:
        """
        Store LLM delta with bounded sliding window.

        Memory bound:
          max 42 context keys × 10 entries × ~120 bytes = ~50KB
          Can NEVER grow past this regardless of runtime duration.

        Persistence:
          Saved to disk after every recording.
          Loaded on startup → survives restarts.

        Learning event:
          When same signal is nudged in the same direction ≥ LEARNING_THRESHOLD
          times → static map updates, history for that key is CLEARED (shrinks file).
        """
        history = self._adjustment_history[context_key]

        # ── Sliding window: drop oldest if at capacity ────────────────────
        if len(history) >= WINDOW_SIZE:
            self._adjustment_history[context_key] = history[-(WINDOW_SIZE - 1):]
            history = self._adjustment_history[context_key]

        history.append(delta)
        self._save_state()  # Persist immediately

        if len(history) < LEARNING_THRESHOLD:
            return

        # ── Check for consistent direction (learning event) ───────────────
        recent = history[-LEARNING_THRESHOLD:]
        learned_something = False

        for signal in SIGNALS:
            values = [d.get(signal, 0.0) for d in recent]
            all_positive = all(v > 0.005 for v in values)
            all_negative = all(v < -0.005 for v in values)

            if all_positive or all_negative:
                # Find the right static map entry to update
                for map_key in STATIC_CONTEXT_WEIGHTS:
                    if map_key in context_key or context_key in map_key:
                        old = STATIC_CONTEXT_WEIGHTS[map_key][signal]
                        avg_delta = sum(values) / len(values)
                        new_val = round(max(0.02, min(0.60, old + avg_delta)), 3)
                        STATIC_CONTEXT_WEIGHTS[map_key][signal] = new_val
                        # Re-normalize the entire context entry
                        total = sum(STATIC_CONTEXT_WEIGHTS[map_key].values())
                        STATIC_CONTEXT_WEIGHTS[map_key] = {
                            k: round(v / total, 3)
                            for k, v in STATIC_CONTEXT_WEIGHTS[map_key].items()
                        }
                        logger.info(
                            f"🧠 Self-calibration: static[{map_key}][{signal}] "
                            f"{old:.3f} → {new_val:.3f} "
                            f"(after {LEARNING_THRESHOLD} consistent LLM adjustments)"
                        )
                        learned_something = True
                        break

        if learned_something:
            # Clear history for this context — it has been absorbed
            self._adjustment_history[context_key] = []
            self._save_state()
            # Persist the evolved static weights — survives restarts
            self._save_learned_weights()
            # Invalidate cache so next call uses updated weights
            llm_cache.invalidate("dynamic_weights")


    # ─── Main API ─────────────────────────────────────────────────────────────

    async def get_weights(
        self,
        need_type: str,
        urgency: float,
        affected_count: int,
        disaster_mode: bool = False,
    ) -> Dict[str, float]:
        """
        Hybrid calibration pipeline:
          1. Cache check — 0 tokens if hit
          2. Static base — always computed, 0 tokens
          3. LLM validate/adjust — small delta prompt, cached 30min
          4. Apply delta to base → final weights
          5. Record delta for learning loop
        """
        context_key = self._context_key(need_type, urgency, disaster_mode)
        cached = llm_cache.get("dynamic_weights", context_key)
        if cached:
            return cached

        # Step 1: Static always gives us a base (never empty handed)
        base_weights, base_source = self._get_static_base(need_type, urgency, disaster_mode)
        logger.debug(f"Hybrid calibration base: '{base_source}' for '{context_key}'")

        # Step 2: LLM validates and optionally adjusts
        from app.services.gemini_service import gemini_service
        if not gemini_service.is_available:
            # No LLM — static base is still a valid answer
            llm_cache.set("dynamic_weights", context_key, base_weights)
            return base_weights

        final_weights, delta = await self._llm_validate_and_adjust(
            base_weights, base_source, need_type, urgency, affected_count, disaster_mode
        )

        # Step 3: Record delta for the learning loop
        if any(abs(v) > 0.005 for v in delta.values()):
            self._record_adjustment(context_key, delta)

        llm_cache.set("dynamic_weights", context_key, final_weights)
        return final_weights

    async def _llm_validate_and_adjust(
        self,
        base: Dict[str, float],
        base_source: str,
        need_type: str,
        urgency: float,
        affected_count: int,
        disaster_mode: bool,
    ) -> Tuple[Dict[str, float], Dict[str, float]]:
        """
        The HYBRID prompt:
        'Here are the static base weights we computed. Do you endorse them
        or should any signal be adjusted for this specific context?'

        Key difference from the tiered approach:
        - LLM is NOT generating weights from zero
        - LLM is VALIDATING a concrete proposal and returning a small delta
        - Smaller prompt, smaller response, lower variance, fewer tokens
        - Endorsement = {"endorse": true} → just a few tokens
        """
        tier = self._urgency_tier(urgency)
        prompt = f"""You are validating pre-computed matching weights for a humanitarian system in India.

Context:
  Need type:     {need_type}
  Urgency tier:  {tier} ({urgency:.2f}/1.0)
  Affected:      {affected_count or 'unknown'} people
  Disaster mode: {'YES' if disaster_mode else 'No'}

Our static rule engine computed these base weights (they sum to 1.0):
  skill_embedding (semantic similarity): {base['skill_embedding']:.3f}
  skill_tags      (Jaccard tag overlap):  {base['skill_tags']:.3f}
  geo_proximity   (travel time decay):    {base['geo_proximity']:.3f}
  urgency         (need criticality):     {base['urgency']:.3f}
  availability    (schedule overlap):     {base['availability']:.3f}
  [source: {base_source}]

Do these weights make sense for this specific context?
If YES, return: {{"endorse": true}}
If NO, return small adjustments (each delta between -0.15 and +0.15):
{{"endorse": false, "adjustments": {{"signal_name": delta_value, ...}}}}

Only include signals you want to adjust. Deltas will be added to the base values.
Return ONLY JSON."""

        try:
            import asyncio
            from app.services.gemini_service import gemini_service
            response = await asyncio.to_thread(
                gemini_service._model.generate_content,
                prompt,
                generation_config={"max_output_tokens": 80}  # Much smaller than generation
            )
            text = response.text.strip()
            if text.startswith("```"):
                text = text.split("\n", 1)[1].rsplit("```", 1)[0]

            result = json.loads(text)

            if result.get("endorse") is True:
                logger.info(f"Hybrid weights: LLM ENDORSED static base '{base_source}' for '{need_type}:{tier}'")
                return base, {}  # No delta — base is correct

            # LLM disagrees — apply the delta adjustments
            delta = {k: float(v) for k, v in result.get("adjustments", {}).items() if k in SIGNALS}
            final = self._apply_delta(base, delta)

            logger.info(
                f"Hybrid weights: LLM ADJUSTED '{base_source}' for '{need_type}:{tier}' "
                f"→ delta={delta}, final={final}"
            )
            return final, delta

        except Exception as e:
            logger.error(f"LLM weight validation failed: {e} — using static base")
            return base, {}

    def get_static_map_snapshot(self) -> Dict:
        """Return current state of the static map — shows self-learning progress."""
        return {
            "static_context_weights": STATIC_CONTEXT_WEIGHTS,
            "default_weights": DEFAULT_WEIGHTS,
            "adjustment_history_counts": {
                k: len(v) for k, v in self._adjustment_history.items()
            },
            "learning_threshold": LEARNING_THRESHOLD,
        }


# Singleton
weight_calibrator = WeightCalibrator()
